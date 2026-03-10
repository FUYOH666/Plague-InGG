#!/usr/bin/env python3
"""Telegram entry point — receive messages, run loop, reply."""

from __future__ import annotations

import asyncio
import html
import os
import re
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")
sys.path.insert(0, str(Path(__file__).resolve().parent))

from telegram import Update
from telegram.error import Conflict
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters


def load_system_prompt() -> str:
    seed_dir = Path(__file__).resolve().parent
    prompt_path = seed_dir / "prompts" / "ENTRY.md"
    if prompt_path.exists():
        return prompt_path.read_text(encoding="utf-8").strip()
    return ""


def run_agent_sync(
    user_message: str,
    system_prompt: str,
    summary_queue: asyncio.Queue | None = None,
    chat_id: int | None = None,
    resume_state: dict | None = None,
    human_reply: str | None = None,
) -> str:
    """Run the sync loop in a thread."""
    from router import ModelRouter
    from loop import run_loop

    router = ModelRouter()
    try:
        return run_loop(
            router=router,
            system_prompt=system_prompt,
            user_message=user_message,
            max_rounds=int(os.getenv("MAX_ROUNDS", "0")),
            verbose=True,
            summary_queue=summary_queue,
            chat_id=chat_id,
            resume_state=resume_state,
            human_reply=human_reply,
        )
    finally:
        router.close()


PAUSED_SESSION_PATH = Path(__file__).resolve().parent.parent / "data" / "memory" / "paused_session.json"
PAUSED_MAGIC = "__PAUSED__"


def _to_telegram_html(text: str) -> str:
    """Convert Markdown-style **bold** to Telegram HTML. Escapes entities. Falls back to plain on error."""
    try:
        escaped = html.escape(text)
        return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", escaped)
    except Exception:
        return text


async def _send_formatted(update: Update, text: str) -> None:
    """Send message with HTML formatting. Fallback to plain if parse fails."""
    if not update.message:
        return
    html_text = _to_telegram_html(text)
    try:
        await update.message.reply_text(html_text, parse_mode="HTML")
    except Exception:
        await update.message.reply_text(text)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.text:
        return
    text = update.message.text.strip()
    if not text:
        return

    chat_id = update.message.chat.id if update.message else None
    print(f"Got: {text[:80]}{'...' if len(text) > 80 else ''}", file=sys.stderr)
    await update.message.chat.send_action("typing")
    system_prompt = load_system_prompt()

    summary_queue: asyncio.Queue = asyncio.Queue()

    async def send_summaries() -> None:
        while True:
            msg = await summary_queue.get()
            if msg is None:
                break
            try:
                if isinstance(msg, tuple) and len(msg) == 2 and msg[0] == "__ASK_HUMAN__":
                    body = f"Reply to this message to continue:\n\n{msg[1]}"
                    await _send_formatted(update, body)
                else:
                    await _send_formatted(update, msg)
            except Exception:
                pass

    sender_task = asyncio.create_task(send_summaries())
    try:
        resume_state = None
        human_reply = None
        user_message = text

        if PAUSED_SESSION_PATH.exists():
            import json
            try:
                state = json.loads(PAUSED_SESSION_PATH.read_text(encoding="utf-8"))
                if state.get("chat_id") == chat_id:
                    resume_state = state
                    human_reply = text
                    user_message = state.get("user_message", text)
                    PAUSED_SESSION_PATH.unlink()
            except Exception:
                pass

        response = await asyncio.to_thread(
            run_agent_sync,
            user_message,
            system_prompt,
            summary_queue,
            chat_id,
            resume_state,
            human_reply,
        )
        if response == PAUSED_MAGIC:
            pass
        else:
            if not (response and response.strip()):
                response = "Извини, не удалось сформулировать ответ. Попробуй переформулировать."
            elif len(response) > 4000:
                response = response[:4000] + "\n\n[... truncated]"
            await _send_formatted(update, response)
            print("Replied.", file=sys.stderr)
    except Exception as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        await update.message.reply_text(f"[ERROR] {e}")
    finally:
        summary_queue.put_nowait(None)
        await sender_task


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message:
        await update.message.reply_text("Running.")


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    err = context.error
    if isinstance(err, Conflict):
        print(
            "\n[!] Conflict: another bot instance is running with the same token.\n"
            "    Stop the other process and try again.",
            file=sys.stderr,
        )
        raise SystemExit(1)
    print(f"[ERROR] {err}", file=sys.stderr)
    if update and isinstance(update, Update) and update.effective_message:
        try:
            await update.effective_message.reply_text(f"[ERROR] {err}")
        except Exception:
            pass


async def post_init(app: Application) -> None:
    """Delete webhook before polling — webhook and getUpdates are mutually exclusive."""
    await app.bot.delete_webhook(drop_pending_updates=True)
    print("  Webhook cleared (if any).", file=sys.stderr)


def check_llm_ready() -> bool:
    """Verify at least one LLM is reachable before accepting messages."""
    from router import ModelRouter

    router = ModelRouter()
    try:
        status = router.status()
        healthy = sum(1 for s in status if s["healthy"])
        for s in status:
            h = "OK" if s["healthy"] else "DOWN"
            print(f"  [{h}] {s['name']}", file=sys.stderr)
        router.close()
        return healthy > 0
    except Exception as e:
        print(f"  LLM check failed: {e}", file=sys.stderr)
        return False


def main() -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("telegram_bot_token")
    if not token:
        print("ERROR: TELEGRAM_BOT_TOKEN or telegram_bot_token not set in .env", file=sys.stderr)
        sys.exit(1)

    print("Checking LLM...", file=sys.stderr)
    if not check_llm_ready():
        print("\n[!] No LLM available. Check TailScale and LLM endpoints.", file=sys.stderr)
        sys.exit(1)

    app = Application.builder().token(token).post_init(post_init).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_error_handler(error_handler)

    print("\nTelegram bot running. Send a message in Telegram.", file=sys.stderr)
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)


if __name__ == "__main__":
    main()
