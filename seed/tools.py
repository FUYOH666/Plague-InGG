"""Tools — всё в распоряжении существа: файлы, shell, git, тесты, поиск."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import httpx

# Project root — parent of seed/
PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _get_env(key: str, alt_key: str = "") -> str:
    """Read env with optional alternate key."""
    return os.getenv(key) or os.getenv(alt_key) or ""


# ---------------------------------------------------------------------------
# Tool definitions (OpenAI function-calling schema)
# ---------------------------------------------------------------------------

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read file. Optional limit=N for first N chars. Omit limit for full file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path relative to project root (e.g. 'seed/tools.py' or 'AGENT_ROADMAP.md')",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max chars to return. Omit for full file.",
                    }
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write content to a file. Creates directories if needed. Overwrites existing content.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path relative to project root"},
                    "content": {"type": "string", "description": "Full file content to write"},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_dir",
            "description": "List files and directories at given path. Returns names. Use empty string for project root.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path relative to project root. Empty for root.",
                    }
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "repo_patch",
            "description": "Search and replace in a file. Safer than full write_file for code edits.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path relative to project root"},
                    "old_string": {"type": "string", "description": "Exact string to find (must match)"},
                    "new_string": {"type": "string", "description": "Replacement string"},
                },
                "required": ["path", "old_string", "new_string"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "safe_edit",
            "description": "Apply patch, run tests, rollback on fail. Safer than repo_patch for code changes.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path relative to project root"},
                    "old_string": {"type": "string", "description": "Exact string to find (must match)"},
                    "new_string": {"type": "string", "description": "Replacement string"},
                },
                "required": ["path", "old_string", "new_string"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "shell",
            "description": "Execute a shell command. Working directory is project root. Timeout: 60s.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Shell command to execute"},
                },
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "git_commit",
            "description": "Stage files and create a git commit.",
            "parameters": {
                "type": "object",
                "properties": {
                    "message": {"type": "string", "description": "Commit message (conventional commits preferred)"},
                    "files": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Files to stage. Empty = stage all (git add -A).",
                    },
                },
                "required": ["message"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "git_status",
            "description": "Show git status and diff.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "git_init",
            "description": "Initialize git repository in project root. Use when git_commit fails with 'not a git repository'.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_tests",
            "description": "Run pytest. Returns pass/fail and output.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Test path. Default: seed/tests/"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the web via Brave Search API. Returns snippets and URLs.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "count": {"type": "integer", "description": "Max results (default 10)"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "evolution_log",
            "description": "Read or append to evolution log. Tracks attempts, successes, failures. Use to avoid repeating failed approaches.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["read", "append"],
                        "description": "read: return current log. append: add new entry with timestamp.",
                    },
                    "content": {
                        "type": "string",
                        "description": "Content for append. Required when action=append.",
                    },
                },
                "required": ["action"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "git_diff",
            "description": "Show full git diff (working tree + staged). Use for detailed changes before commit.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_python",
            "description": "Execute Python code. Timeout 10s. Returns stdout+stderr. Use for quick checks.",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "Python code to execute"},
                },
                "required": ["code"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "transcribe_audio",
            "description": "Transcribe audio file to text via ASR. Path relative to project root.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to audio file (e.g. voice.ogg, recording.mp3)"},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "embedding",
            "description": "Generate dense embeddings for text. Use for semantic search. Returns dimension + preview.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "Text to embed. Multiple texts: separate by newlines.",
                    },
                },
                "required": ["text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "rerank",
            "description": "Rerank documents by relevance to query. Returns top documents with scores.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "documents": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Documents to rank",
                    },
                    "top_n": {"type": "integer", "description": "Max results (default: all)"},
                },
                "required": ["query", "documents"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "github_search_repos",
            "description": "Search GitHub repositories. Returns name, owner, description, URL, stars, language.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query (e.g. 'llm agent python')",
                    },
                    "sort": {
                        "type": "string",
                        "enum": ["stars", "forks", "updated", "best-match"],
                        "description": "Sort order (default: best-match)",
                    },
                    "per_page": {
                        "type": "integer",
                        "description": "Max results (default: 5)",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "github_search_code",
            "description": "Search code on GitHub. Requires GITHUB_TOKEN. Use qualifiers: repo:owner/repo, language:python.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query with optional qualifiers",
                    },
                    "per_page": {
                        "type": "integer",
                        "description": "Max results (default: 5)",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "github_read_file",
            "description": "Read a file from a public GitHub repository.",
            "parameters": {
                "type": "object",
                "properties": {
                    "owner": {
                        "type": "string",
                        "description": "Repository owner (e.g. openai)",
                    },
                    "repo": {
                        "type": "string",
                        "description": "Repository name (e.g. openai-python)",
                    },
                    "path": {
                        "type": "string",
                        "description": "File path (e.g. README.md)",
                    },
                    "ref": {
                        "type": "string",
                        "description": "Branch or commit (default: main)",
                    },
                },
                "required": ["owner", "repo", "path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "rag_index",
            "description": "Index file or folder into RAG. Chunks, embeds, stores in ChromaDB. Path relative to project root.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "File or directory path to index",
                    },
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "rag_search",
            "description": "Search knowledge base. Returns relevant chunks from indexed documents.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query",
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "Max results (default: 5)",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "rag_list",
            "description": "List indexed documents with metadata. Use rag_fetch(id) to load full content.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "rag_fetch",
            "description": "Fetch full document by id. Use rag_list to see ids. Prefix 'path' fetches all path:N chunks.",
            "parameters": {
                "type": "object",
                "properties": {
                    "doc_id": {
                        "type": "string",
                        "description": "Document id (e.g. data/memory/knowledge/evolution_index.md:0) or prefix",
                    },
                },
                "required": ["doc_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ask_human",
            "description": "Ask the user a question when stuck. In Telegram: pauses session until user replies.",
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {
                        "type": "string",
                        "description": "Question to ask the user",
                    },
                },
                "required": ["question"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_goal",
            "description": "Add a goal with optional deadline. Goals are stored in data/memory/goals.md.",
            "parameters": {
                "type": "object",
                "properties": {
                    "description": {
                        "type": "string",
                        "description": "Goal description",
                    },
                    "deadline": {
                        "type": "string",
                        "description": "Optional deadline (YYYY-MM-DD)",
                    },
                },
                "required": ["description"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_goals",
            "description": "Read current goals from data/memory/goals.md.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_tool",
            "description": "Add a new tool to tools.py. Validates schema, patches file, runs tests.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Tool name (snake_case)",
                    },
                    "description": {
                        "type": "string",
                        "description": "Tool description for LLM",
                    },
                    "parameters_json": {
                        "type": "string",
                        "description": "OpenAI schema JSON for parameters",
                    },
                    "code": {
                        "type": "string",
                        "description": "Python function body",
                    },
                },
                "required": ["name", "description", "parameters_json", "code"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "browse_web",
            "description": "Browser automation: navigate, snapshot, click, fill, screenshot.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["open", "snapshot", "click", "fill", "screenshot", "get_url", "get_title"],
                        "description": "Browser action to perform",
                    },
                    "url": {
                        "type": "string",
                        "description": "URL for open action",
                    },
                    "ref": {
                        "type": "string",
                        "description": "Element ref for click/fill",
                    },
                    "text": {
                        "type": "string",
                        "description": "Text for fill action",
                    },
                    "path": {
                        "type": "string",
                        "description": "Path to save screenshot",
                    },
                },
                "required": ["action"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "auto_discover_tools",
            "description": "Automatically discover and load new tools from modules.",
            "parameters": {
                "type": "object",
                "properties": {
                    "module_path": {
                        "type": "string",
                        "description": "Path to module for analysis",
                    },
                    "dry_run": {
                        "type": "boolean",
                        "description": "Check mode without applying changes",
                    },
                },
                "required": ["module_path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "self_improve",
            "description": "Self-improvement actions: reload modules, register tools, monitor performance, or get evolution summary.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["reload", "register", "monitor", "summary"],
                        "description": "Type of self-improvement action",
                    },
                    "module_path": {
                        "type": "string",
                        "description": "Module path for reload action",
                    },
                    "force_reload": {
                        "type": "boolean",
                        "description": "Force module reload",
                    },
                    "tool_name": {
                        "type": "string",
                        "description": "Tool name for registration",
                    },
                    "description": {
                        "type": "string",
                        "description": "Tool description",
                    },
                },
                "required": ["action"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "github_search_repos",
            "description": "Search GitHub repositories. Returns name, owner, description, URL, stars, language.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query (e.g. 'llm agent python')",
                    },
                    "sort": {
                        "type": "string",
                        "enum": ["stars", "forks", "updated", "best-match"],
                        "description": "Sort order (default: best-match)",
                    },
                    "per_page": {
                        "type": "integer",
                        "description": "Max results (default: 5)",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "github_search_code",
            "description": "Search code on GitHub. Requires GITHUB_TOKEN. Use qualifiers: repo:owner/repo, language:python.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query with optional qualifiers",
                    },
                    "per_page": {
                        "type": "integer",
                        "description": "Max results (default: 5)",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "github_read_file",
            "description": "Read a file from a public GitHub repository.",
            "parameters": {
                "type": "object",
                "properties": {
                    "owner": {
                        "type": "string",
                        "description": "Repository owner (e.g. openai)",
                    },
                    "repo": {
                        "type": "string",
                        "description": "Repository name (e.g. openai-python)",
                    },
                    "path": {
                        "type": "string",
                        "description": "File path (e.g. README.md)",
                    },
                    "ref": {
                        "type": "string",
                        "description": "Branch or commit (default: main)",
                    },
                },
                "required": ["owner", "repo", "path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "rag_index",
            "description": "Index file or folder into RAG. Chunks, embeds, stores in ChromaDB. Path relative to project root.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "File or directory path to index",
                    },
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "github_read_file",
            "description": "Read a file from a public GitHub repository.",
            "parameters": {
                "type": "object",
                "properties": {
                    "owner": {"type": "string", "description": "Repository owner (e.g. openai)"},
                    "repo": {"type": "string", "description": "Repository name (e.g. openai-python)"},
                    "path": {"type": "string", "description": "File path (e.g. README.md)"},
                    "ref": {"type": "string", "description": "Branch or commit (default: main)"},
                },
                "required": ["owner", "repo", "path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "github_search_code",
            "description": "Search code on GitHub. Requires GITHUB_TOKEN. Use qualifiers: repo:owner/repo, language:python.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query with optional qualifiers"},
                    "per_page": {"type": "integer", "description": "Max results (default: 5)"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "rag_index",
            "description": "Index file or folder into RAG. Chunks, embeds, stores in ChromaDB. Path relative to project root (e.g. data/memory/knowledge/ or README.md).",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File or directory path to index"},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "rag_search",
            "description": "Search knowledge base. Returns relevant chunks from indexed documents. Use rag_index first.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "top_k": {"type": "integer", "description": "Max results (default: 5)"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "rag_list",
            "description": "List indexed documents (short metadata). Use rag_fetch(id) to load full content. Progressive disclosure.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "rag_fetch",
            "description": "Fetch full document by id. Use rag_list to see ids. Prefix 'path' fetches all path:N chunks.",
            "parameters": {
                "type": "object",
                "properties": {
                    "doc_id": {"type": "string", "description": "Document id (e.g. data/memory/knowledge/evolution_index.md:0) or prefix"},
                },
                "required": ["doc_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ask_human",
            "description": "Ask the user a question when stuck. In Telegram: pauses session until user replies. In CLI: prompts for input.",
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {"type": "string", "description": "Question to ask the user"},
                },
                "required": ["question"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "rag_index_evolution",
            "description": "Index evolution-log, session-history, git log and diffs into RAG. Use to search own experience, rollbacks, what worked/failed.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "rag_index_docs",
            "description": "Search for library documentation, fetch and index into RAG. Use when first using a library.",
            "parameters": {
                "type": "object",
                "properties": {
                    "library_name": {"type": "string", "description": "Library name (e.g. httpx, fastapi)"},
                },
                "required": ["library_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "working_memory",
            "description": "Bounded memory: memory (agent notes, 2200 chars) or user (identity, 1375 chars). When full, consolidate or remove entries before adding.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["read", "append", "replace", "remove"],
                        "description": "read: return current. append: add entry. replace: overwrite. remove: delete entry containing old_text.",
                    },
                    "content": {"type": "string", "description": "For append/replace. Required for append, replace."},
                    "old_text": {"type": "string", "description": "Unique substring for remove or replace. Identifies which entry to change."},
                    "target": {
                        "type": "string",
                        "enum": ["memory", "user"],
                        "description": "memory: agent notes (working-memory.md, 2200 chars). user: identity (identity.md, 1375 chars). Default: memory.",
                    },
                },
                "required": ["action"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_goal",
            "description": "Add a goal with optional deadline. Goals are stored in data/memory/goals.md and checked periodically.",
            "parameters": {
                "type": "object",
                "properties": {
                    "description": {"type": "string", "description": "Goal description"},
                    "deadline": {"type": "string", "description": "Optional deadline (YYYY-MM-DD)"},
                },
                "required": ["description"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_goals",
            "description": "Read current goals from data/memory/goals.md.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_tool",
            "description": "Add a new tool to tools.py. Validates schema, patches file, runs tests. On test failure, rolls back. Use for extending agent capabilities.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Tool name (snake_case, e.g. my_custom_tool)"},
                    "description": {"type": "string", "description": "Tool description for LLM"},
                    "parameters_json": {
                        "type": "string",
                        "description": "OpenAI schema JSON: {\"type\":\"object\",\"properties\":{\"param\":{\"type\":\"string\",\"description\":\"...\"}},\"required\":[\"param\"]}",
                    },
                    "code": {
                        "type": "string",
                        "description": "Python function body. Must return a string. Can use PROJECT_ROOT, _resolve, etc. No exec/eval.",
                    },
                },
                "required": ["name", "description", "parameters_json", "code"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "browse_web",
            "description": "Browser automation via agent-browser CLI. Navigate, snapshot, click, fill, screenshot. Requires: npm install -g agent-browser && agent-browser install.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["open", "snapshot", "click", "fill", "screenshot", "get_url", "get_title"],
                        "description": "open: navigate to URL. snapshot: get interactive elements (refs). click: click element by ref (@e1). fill: fill input. screenshot: save viewport. get_url/get_title: get current page info.",
                    },
                    "url": {"type": "string", "description": "URL for action=open"},
                    "ref": {"type": "string", "description": "Element ref for click/fill (e.g. @e1)"},
                    "text": {"type": "string", "description": "Text for action=fill"},
                    "path": {"type": "string", "description": "Path to save screenshot (relative to project root)"},
                },
                "required": ["action"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "auto_discover_tools",
            "description": "Автоматически обнаруживает и загружает новые инструменты из модулей, обновляя реестр и логи эволюции.",
            "parameters": {"type": "object", "properties": {"module_path": {"type": "string", "description": "Путь к модулю для анализа (например, seed.tools)"}, "dry_run": {"type": "boolean", "description": "Режим проверки без применения изменений"}}, "required": ["module_path"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "evolution_monitor",
            "description": "Monitors system evolution, triggers hot reload, and manages tool registration. Supports automatic performance tracking and evolution logging.",
            "parameters": {"type": "object", "properties": {"action": {"type": "string", "enum": ["reload", "register", "monitor", "summary"], "description": "Type of evolution action"}, "module_path": {"type": "string", "description": "Path to module for reload (e.g., seed.self_improve)"}, "tool_name": {"type": "string", "description": "Name of tool to register"}, "description": {"type": "string", "description": "Tool description"}, "force_reload": {"type": "boolean", "description": "Force module reload"}}},
        },
    },
]

# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------


# Capability zones (Blueprint): Red=immutable, Orange=human approval, Yellow=allowed, Green=allowed
RED_PATHS = (
    "scripts/run_tests_runner.py",
    "scripts/capability_benchmark.py",
    "scripts/evaluator.py",
    "seed/self_improve.py",
)
ORANGE_PATHS = ("seed/tools.py",)  # requires AUTO_APPROVE_ADD_TOOL
YELLOW_PATHS = (
    "seed/loop.py",
    "seed/router.py",
    "seed/llm.py",
    "seed/rag.py",
)


def _resolve(path: str) -> Path:
    resolved = (PROJECT_ROOT / path).resolve()
    if not str(resolved).startswith(str(PROJECT_ROOT)):
        raise ToolError(f"Path escapes project root: {path}")
    return resolved


def _get_zone(path: str) -> str:
    """Return capability zone: red, orange, yellow, green. Red=immutable, Orange=human approval."""
    try:
        target = (PROJECT_ROOT / path).resolve()
        rel = str(target.relative_to(PROJECT_ROOT)).replace("\\", "/")
        if any(rel == p.replace("\\", "/") for p in RED_PATHS):
            return "red"
        if any(rel == p.replace("\\", "/") for p in ORANGE_PATHS):
            return "orange"
        if any(rel == p.replace("\\", "/") for p in YELLOW_PATHS):
            return "yellow"
        if rel.startswith("seed/prompts/") and rel.endswith(".md"):
            return "green"
        if rel == "run.sh":
            return "green"
        if "/" not in rel and rel.endswith(".md") and rel != "AGENT_ROADMAP.md":
            return "green"
        return "yellow"  # default: allow
    except Exception:
        return "yellow"


def _is_protected(path: str) -> bool:
    """Block edits to Red zone (evaluator, harness)."""
    return _get_zone(path) == "red"


def _check_zone_for_edit(path: str) -> str | None:
    """Return error message if edit not allowed, else None."""
    zone = _get_zone(path)
    if zone == "red":
        return (
            f"[ERROR] Red zone: {path} is protected. "
            "Protected: evaluator, run_tests_runner, capability_benchmark, self_improve. "
            "Use add_tool to extend, or edit other files (loop, rag, prompts)."
        )
    if zone == "orange":
        if os.getenv("AUTO_APPROVE_ADD_TOOL", "").lower() not in ("true", "1", "yes"):
            return (
                f"[ORANGE] {path} requires human approval. "
                "Set AUTO_APPROVE_ADD_TOOL=true in .env or use ask_human first."
            )
    return None


def read_file(path: str, limit: int | None = None) -> str:
    target = _resolve(path)
    if not target.exists():
        raise ToolError(f"File not found: {path}")
    if not target.is_file():
        raise ToolError(f"Not a file: {path}")
    content = target.read_text(encoding="utf-8", errors="replace")
    if limit is not None and limit > 0:
        if len(content) > limit:
            return content[:limit] + f"\n\n... [truncated, total {len(content)} chars]"
        return content
    if len(content) > 100_000:
        return content[:100_000] + f"\n\n... [truncated, total {len(content)} chars]"
    return content


def write_file(path: str, content: str) -> str:
    err = _check_zone_for_edit(path)
    if err:
        return err
    target = _resolve(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return f"OK: wrote {len(content)} chars to {path}"


def list_dir(path: str = "") -> str:
    target = _resolve(path) if path else PROJECT_ROOT
    if not target.exists():
        raise ToolError(f"Path not found: {path}")
    if not target.is_dir():
        raise ToolError(f"Not a directory: {path}")
    items = sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
    return "\n".join(p.name + ("/" if p.is_dir() else "") for p in items)


def repo_patch(path: str, old_string: str, new_string: str) -> str:
    err = _check_zone_for_edit(path)
    if err:
        return err
    target = _resolve(path)
    if not target.exists():
        raise ToolError(f"File not found: {path}")
    content = target.read_text(encoding="utf-8")
    if old_string not in content:
        return f"[ERROR] old_string not found in {path}"
    new_content = content.replace(old_string, new_string, 1)
    target.write_text(new_content, encoding="utf-8")
    return f"OK: patched {path}"


def safe_edit(path: str, old_string: str, new_string: str) -> str:
    """Apply patch, run tests, rollback on fail. Logs to evolution_log on rollback."""
    err = _check_zone_for_edit(path)
    if err:
        return err
    target = _resolve(path)
    if not target.exists():
        raise ToolError(f"File not found: {path}")
    content = target.read_text(encoding="utf-8")
    if old_string not in content:
        return f"[ERROR] old_string not found in {path}"

    # Apply patch
    new_content = content.replace(old_string, new_string, 1)
    target.write_text(new_content, encoding="utf-8")

    # Run tests
    test_result = run_tests("seed/tests/")
    if "[PASSED]" in test_result:
        return f"OK: patched {path}, tests passed"

    # Rollback: restore original
    target.write_text(content, encoding="utf-8")
    if (PROJECT_ROOT / ".git").exists():
        try:
            subprocess.run(
                ["git", "checkout", "--", path],
                cwd=PROJECT_ROOT,
                capture_output=True,
                text=True,
            )
        except Exception:
            pass

    evolution_log(
        "append",
        f"safe_edit ROLLBACK: {path} — tests failed after patch. old_string len={len(old_string)}, new_string len={len(new_string)}. Output: {test_result[:500]}",
    )
    return f"ROLLBACK: tests failed. Restored {path}. {test_result[:300]}"


def shell(command: str) -> str:
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=60,
            cwd=PROJECT_ROOT,
        )
        output = ""
        if result.stdout:
            output += result.stdout
        if result.stderr:
            output += ("\n--- stderr ---\n" + result.stderr) if output else result.stderr
        if result.returncode != 0:
            output += f"\n[exit code: {result.returncode}]"
        return output.strip() or "(no output)"
    except subprocess.TimeoutExpired:
        return "[ERROR] Command timed out after 60 seconds"
    except Exception as e:
        return f"[ERROR] {e}"


def git_commit(message: str, files: list[str] | None = None) -> str:
    try:
        if files:
            for f in files:
                subprocess.run(["git", "add", f], cwd=PROJECT_ROOT, capture_output=True)
        else:
            subprocess.run(["git", "add", "-A"], cwd=PROJECT_ROOT, capture_output=True)

        result = subprocess.run(
            ["git", "commit", "-m", message],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
        )

        if result.returncode == 0:
            hash_result = subprocess.run(
                ["git", "rev-parse", "--short", "HEAD"],
                cwd=PROJECT_ROOT,
                capture_output=True,
                text=True,
            )
            commit_hash = hash_result.stdout.strip()
            return f"OK: committed {commit_hash} — {message}"
        return f"FAILED: {result.stderr.strip() or result.stdout.strip()}"
    except Exception as e:
        return f"ERROR: {e}"


def git_init() -> str:
    """Initialize git repository in project root."""
    git_dir = PROJECT_ROOT / ".git"
    if git_dir.exists():
        return "OK: git repo already exists"
    try:
        subprocess.run(
            ["git", "init"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        return "OK: git initialized"
    except subprocess.CalledProcessError as e:
        return f"ERROR: {e.stderr or str(e)}"
    except Exception as e:
        return f"ERROR: {e}"


def git_status() -> str:
    try:
        result = subprocess.run(
            ["git", "status", "-sb"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
        )
        status = result.stdout.strip()
        diff = subprocess.run(
            ["git", "diff", "--stat"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
        )
        if diff.stdout.strip():
            status += "\n\n" + diff.stdout.strip()
        return status
    except Exception as e:
        return f"ERROR: {e}"


RUNNER_RESULT_PATH = PROJECT_ROOT / "data" / "runner" / "last_test_result.json"


def run_tests(path: str = "seed/tests/") -> str:
    """Run tests via isolated runner process. Results written to immutable file (source of truth)."""
    import json as _json

    runner_script = Path(__file__).resolve().parent.parent / "scripts" / "run_tests_runner.py"
    env = os.environ.copy()
    env["EKATERINA_PROJECT_ROOT"] = str(PROJECT_ROOT)
    try:
        subprocess.run(
            [sys.executable, str(runner_script), path],
            cwd=PROJECT_ROOT,
            env=env,
            capture_output=True,
            timeout=130,
        )
        if not RUNNER_RESULT_PATH.exists():
            return "[ERROR] Runner did not produce result file"
        data = _json.loads(RUNNER_RESULT_PATH.read_text(encoding="utf-8"))
        status = data.get("status", "UNKNOWN")
        output = data.get("output", "")
        return f"[{status}]\n{output}"
    except subprocess.TimeoutExpired:
        return "[ERROR] Runner timed out after 130s"
    except Exception as e:
        return f"ERROR: {e}"


def web_search(query: str, count: int = 10) -> str:
    api_key = _get_env("BRAVE_API_KEY", "api_key_brave_search")
    if not api_key:
        return "[ERROR] BRAVE_API_KEY or api_key_brave_search not set in .env"

    try:
        with httpx.Client(timeout=15) as client:
            resp = client.get(
                "https://api.search.brave.com/res/v1/web/search",
                params={"q": query, "count": min(count, 20)},
                headers={"X-Subscription-Token": api_key},
            )
            resp.raise_for_status()
            data = resp.json()

        results = data.get("web", {}).get("results", [])
        if not results:
            return "No results found."

        lines = []
        for i, r in enumerate(results[:count], 1):
            title = r.get("title", "")
            url = r.get("url", "")
            desc = r.get("description", "")[:200]
            lines.append(f"{i}. {title}\n   {url}\n   {desc}")
        return "\n\n".join(lines)
    except httpx.HTTPStatusError as e:
        return f"[ERROR] Brave API: {e.response.status_code} — {e.response.text[:200]}"
    except Exception as e:
        return f"[ERROR] {e}"


def evolution_log(action: str, content: str = "") -> str:
    log_path = PROJECT_ROOT / "data" / "memory" / "evolution-log.md"
    if action == "read":
        if not log_path.exists():
            return "(empty evolution log)"
        return log_path.read_text(encoding="utf-8")
    if action == "append":
        if not content:
            return "[ERROR] content required for append"
        from datetime import datetime

        log_path.parent.mkdir(parents=True, exist_ok=True)
        block = f"\n## {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n{content}\n"
        log_path.open("a", encoding="utf-8").write(block)
        return f"OK: appended {len(block)} chars"
    return f"[ERROR] unknown action: {action}. Use read or append"


def git_diff() -> str:
    try:
        result = subprocess.run(
            ["git", "diff"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
        )
        working = result.stdout.strip()
        result_cached = subprocess.run(
            ["git", "diff", "--cached"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
        )
        staged = result_cached.stdout.strip()
        parts = []
        if staged:
            parts.append("--- staged ---\n" + staged)
        if working:
            parts.append("--- working ---\n" + working)
        return "\n\n".join(parts) if parts else "(no changes)"
    except Exception as e:
        return f"ERROR: {e}"


def run_python(code: str) -> str:
    preamble = f"""import sys
from pathlib import Path
PROJECT_ROOT = Path({repr(str(PROJECT_ROOT))})
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "seed"))
"""
    code_to_run = preamble + code
    try:
        result = subprocess.run(
            [sys.executable, "-c", code_to_run],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=10,
        )
        output = result.stdout or ""
        if result.stderr:
            output += ("\n--- stderr ---\n" + result.stderr) if output else result.stderr
        if result.returncode != 0:
            output += f"\n[exit code: {result.returncode}]"
        return output.strip() or "(no output)"
    except subprocess.TimeoutExpired:
        return "[ERROR] Code timed out after 10 seconds"
    except Exception as e:
        return f"[ERROR] {e}"


def transcribe_audio(path: str) -> str:
    base_url = _get_env("LOCAL_AI_ASR_BASE_URL") or "http://localhost:8001"
    target = _resolve(path)
    if not target.exists():
        return f"[ERROR] File not found: {path}"
    if not target.is_file():
        return f"[ERROR] Not a file: {path}"
    try:
        audio_bytes = target.read_bytes()
        with httpx.Client(timeout=60) as client:
            resp = client.post(
                f"{base_url.rstrip('/')}/v1/audio/transcriptions",
                files={"file": (target.name, audio_bytes, "audio/ogg")},
                data={"model": "cstr/whisper-large-v3-turbo-int8_float32"},
            )
        resp.raise_for_status()
        data = resp.json()
        return data.get("text", "(no text)")
    except httpx.HTTPStatusError as e:
        return f"[ERROR] ASR API: {e.response.status_code} — {e.response.text[:200]}"
    except httpx.ConnectError:
        return "[ERROR] Cannot connect to ASR service. Check TailScale."
    except Exception as e:
        return f"[ERROR] {e}"


def embedding(text: str) -> str:
    base_url = _get_env("LOCAL_AI_EMBEDDING_BASE_URL") or "http://localhost:9001"
    texts = [t.strip() for t in text.split("\n") if t.strip()]
    if not texts:
        return "[ERROR] No text provided"
    try:
        with httpx.Client(timeout=30) as client:
            resp = client.post(
                f"{base_url.rstrip('/')}/v1/embeddings",
                json={"input": texts, "return_dense": True, "return_sparse": False},
            )
        resp.raise_for_status()
        data = resp.json()
        items = data.get("data", [])
        lines = []
        for i, item in enumerate(items):
            vec = item.get("dense_embedding", [])
            dim = len(vec)
            preview = vec[:5] if vec else []
            lines.append(f"#{i + 1}: dim={dim}, preview={preview}")
        return "\n".join(lines)
    except httpx.HTTPStatusError as e:
        return f"[ERROR] Embedding API: {e.response.status_code} — {e.response.text[:200]}"
    except httpx.ConnectError:
        return "[ERROR] Cannot connect to Embedding service. Check TailScale."
    except Exception as e:
        return f"[ERROR] {e}"


def rerank(query: str, documents: list[str], top_n: int | None = None) -> str:
    base_url = _get_env("LOCAL_AI_RERANKER_BASE_URL") or "http://localhost:9002"
    if not documents:
        return "[ERROR] documents required"
    try:
        payload: dict = {"query": query, "documents": documents, "normalize": True}
        if top_n is not None:
            payload["top_n"] = top_n
        with httpx.Client(timeout=30) as client:
            resp = client.post(
                f"{base_url.rstrip('/')}/v1/rerank",
                json=payload,
            )
        resp.raise_for_status()
        data = resp.json()
        results = data.get("results", [])
        lines = []
        for r in results:
            doc = r.get("document", "")[:150]
            score = r.get("relevance_score", 0)
            lines.append(f"{score:.4f} | {doc}...")
        return "\n".join(lines) if lines else "(no results)"
    except httpx.HTTPStatusError as e:
        return f"[ERROR] Reranker API: {e.response.status_code} — {e.response.text[:200]}"
    except httpx.ConnectError:
        return "[ERROR] Cannot connect to Reranker service. Check TailScale."
    except Exception as e:
        return f"[ERROR] {e}"


def _github_headers() -> dict:
    """Headers for GitHub API. Token optional but increases rate limits."""
    token = _get_env("GITHUB_TOKEN", "github_token")
    headers = {"Accept": "application/vnd.github.v3+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def github_search_repos(
    query: str,
    sort: str = "best-match",
    per_page: int = 5,
) -> str:
    """Search GitHub repositories."""
    try:
        params: dict = {"q": query, "per_page": min(per_page, 30)}
        if sort and sort != "best-match":
            params["sort"] = sort
            params["order"] = "desc"
        with httpx.Client(timeout=15) as client:
            resp = client.get(
                "https://api.github.com/search/repositories",
                params=params,
                headers=_github_headers(),
            )
            resp.raise_for_status()
            data = resp.json()
        items = data.get("items", [])
        if not items:
            return "No repositories found."
        lines = []
        for i, r in enumerate(items, 1):
            full_name = r.get("full_name", "")
            desc = (r.get("description") or "")[:150]
            stars = r.get("stargazers_count", 0)
            lang = r.get("language") or ""
            url = r.get("html_url", "")
            lines.append(f"{i}. {full_name} | stars: {stars} | {lang}\n   {url}\n   {desc}")
        return "\n\n".join(lines)
    except httpx.HTTPStatusError as e:
        return f"[ERROR] GitHub API: {e.response.status_code} — {e.response.text[:200]}"
    except Exception as e:
        return f"[ERROR] {e}"


def github_read_file(
    owner: str,
    repo: str,
    path: str,
    ref: str = "main",
) -> str:
    """Read file from a public GitHub repository."""
    max_chars = 50_000
    url = f"https://raw.githubusercontent.com/{owner}/{repo}/{ref}/{path}"
    try:
        with httpx.Client(timeout=15) as client:
            resp = client.get(url)
            resp.raise_for_status()
            content = resp.text
        if len(content) > max_chars:
            return content[:max_chars] + f"\n\n... [truncated, total {len(content)} chars]"
        return content
    except httpx.HTTPStatusError as e:
        return f"[ERROR] GitHub: {e.response.status_code} — {e.response.text[:200]}"
    except Exception as e:
        return f"[ERROR] {e}"


def github_search_code(query: str, per_page: int = 5) -> str:
    """Search code on GitHub. Requires GITHUB_TOKEN."""
    token = _get_env("GITHUB_TOKEN", "github_token")
    if not token:
        return "[ERROR] github_search_code requires GITHUB_TOKEN in .env (code search needs auth)"

    try:
        with httpx.Client(timeout=15) as client:
            resp = client.get(
                "https://api.github.com/search/code",
                params={"q": query, "per_page": min(per_page, 30)},
                headers=_github_headers(),
            )
            resp.raise_for_status()
            data = resp.json()
        items = data.get("items", [])
        if not items:
            return "No code matches found."
        lines = []
        for i, r in enumerate(items, 1):
            path = r.get("path", "")
            repo = r.get("repository", {}).get("full_name", "")
            html_url = r.get("html_url", "")
            fragment = ""
            if r.get("text_matches"):
                frag = r["text_matches"][0].get("fragment", "")
                fragment = f"\n   snippet: {frag[:300]}..." if len(frag) > 300 else f"\n   snippet: {frag}"
            lines.append(f"{i}. {repo}/{path}\n   {html_url}{fragment}")
        return "\n\n".join(lines)
    except httpx.HTTPStatusError as e:
        return f"[ERROR] GitHub API: {e.response.status_code} — {e.response.text[:200]}"
    except Exception as e:
        return f"[ERROR] {e}"


MEMORY_CHAR_LIMIT = 2200  # agent notes (Hermes-style)
USER_CHAR_LIMIT = 1375    # identity / user profile


def _memory_path(target: str) -> Path:
    if target == "user":
        return PROJECT_ROOT / "data" / "memory" / "identity.md"
    return PROJECT_ROOT / "data" / "memory" / "working-memory.md"


def _memory_limit(target: str) -> int:
    return USER_CHAR_LIMIT if target == "user" else MEMORY_CHAR_LIMIT


def _split_entries(text: str) -> list[str]:
    """Split by ## blocks. First block may be empty or intro."""
    if not text.strip():
        return []
    parts = text.split("\n## ")
    entries = []
    for i, p in enumerate(parts):
        p = p.strip()
        if not p:
            continue
        if i == 0 and not p.startswith("20"):  # date pattern
            entries.append(p)
        else:
            entries.append("## " + p if not p.startswith("## ") else p)
    return entries


def _join_entries(entries: list[str]) -> str:
    return "\n\n".join(e.strip() for e in entries if e.strip())


def working_memory(
    action: str,
    content: str = "",
    old_text: str = "",
    target: str = "memory",
) -> str:
    """Bounded memory: memory (agent notes) or user (identity). Limits: 2200/1375 chars."""
    from datetime import datetime

    if target not in ("memory", "user"):
        target = "memory"
    path = _memory_path(target)
    limit = _memory_limit(target)
    path.parent.mkdir(parents=True, exist_ok=True)

    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    current_len = len(existing)

    if action == "read":
        if not path.exists():
            return "(empty)" + (f" [{target}]" if target == "user" else "")
        usage = f"{current_len}/{limit} chars ({100 * current_len // limit}%)"
        return f"--- {target} [{usage}] ---\n\n{existing}"

    if action == "append":
        if not content:
            return "[ERROR] content required for append"
        block = f"\n## {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n{content.strip()}\n"
        new_len = current_len + len(block)
        if new_len > limit:
            entries = _split_entries(existing)
            return (
                f"[ERROR] {target} at {current_len}/{limit} chars. Adding {len(block)} would exceed. "
                "Use remove(old_text) or replace(old_text, content) to consolidate, then append."
            )
        path.write_text(existing + block, encoding="utf-8")
        return f"OK: appended {len(block)} chars ({current_len + len(block)}/{limit})"

    if action == "replace":
        if not content:
            return "[ERROR] content required for replace"
        if len(content) > limit:
            return f"[ERROR] content ({len(content)} chars) exceeds limit ({limit})"
        if old_text:
            entries = _split_entries(existing)
            matches = [i for i, e in enumerate(entries) if old_text in e]
            if len(matches) > 1:
                return "[ERROR] old_text matches multiple entries. Use a more specific substring."
            if not matches:
                return "[ERROR] no entry contains old_text"
            entries[matches[0]] = content.strip()
            new_text = _join_entries(entries)
            path.write_text(new_text, encoding="utf-8")
            return f"OK: replaced entry ({len(new_text)}/{limit} chars)"
        path.write_text(content, encoding="utf-8")
        return f"OK: replaced with {len(content)} chars"

    if action == "remove":
        if not old_text:
            return "[ERROR] old_text required for remove (unique substring of entry to delete)"
        entries = _split_entries(existing)
        matches = [i for i, e in enumerate(entries) if old_text in e]
        if len(matches) > 1:
            return "[ERROR] old_text matches multiple entries. Use a more specific substring."
        if not matches:
            return "[ERROR] no entry contains old_text"
        del entries[matches[0]]
        new_text = _join_entries(entries)
        path.write_text(new_text, encoding="utf-8")
        return f"OK: removed entry ({len(existing) - len(new_text)} chars freed)"

    return f"[ERROR] unknown action: {action}. Use read, append, replace or remove"


def ask_human(question: str) -> str:
    """Ask user a question. In Telegram: pauses session. In CLI: prompts for input."""
    ctx = _loop_context
    summary_queue = ctx.get("summary_queue")
    chat_id = ctx.get("chat_id")

    if summary_queue is not None and chat_id is not None:
        try:
            summary_queue.put_nowait(("__ASK_HUMAN__", question))
        except Exception:
            pass
        raise AskHumanPause(question, tool_call_id=ctx.get("pending_tool_call_id", ""))

    # CLI mode: block on input
    try:
        reply = input(f"\n[Human: {question}]\n> ").strip()
        return reply or "(no reply)"
    except EOFError:
        return "(no reply — EOF)"


GOALS_PATH = PROJECT_ROOT / "data" / "memory" / "goals.md"


def set_goal(description: str, deadline: str = "") -> str:
    """Add a goal with optional deadline to goals.md."""
    GOALS_PATH.parent.mkdir(parents=True, exist_ok=True)
    from datetime import datetime
    date_part = deadline if deadline else datetime.now().strftime("%Y-%m-%d")
    block = f"\n## {date_part} | {description}\n"
    existing = GOALS_PATH.read_text(encoding="utf-8") if GOALS_PATH.exists() else ""
    GOALS_PATH.write_text(existing + block, encoding="utf-8")
    return f"OK: added goal{(' (deadline: ' + deadline + ')') if deadline else ''}"


def read_goals() -> str:
    """Read current goals from goals.md."""
    if not GOALS_PATH.exists():
        return "(no goals yet)"
    return GOALS_PATH.read_text(encoding="utf-8")


def add_tool(name: str, description: str, parameters_json: str, code: str) -> str:
    """Add a new tool to tools.py via repo_patch. Runs tests, rolls back on failure. Orange zone: requires AUTO_APPROVE_ADD_TOOL or human approval."""
    import json
    import re

    if os.getenv("AUTO_APPROVE_ADD_TOOL", "").lower() not in ("true", "1", "yes"):
        return (
            "[ORANGE] add_tool requires human approval. "
            "Use ask_human to confirm, then set AUTO_APPROVE_ADD_TOOL=true in .env and retry."
        )

    # Validate name
    if not re.match(r"^[a-z][a-z0-9_]*$", name):
        return f"[ERROR] Invalid name: {name}. Use snake_case, e.g. my_tool"

    # Block dangerous patterns in code
    for bad in ("exec(", "eval(", "__import__", "subprocess.", "os.system"):
        if bad in code:
            return f"[ERROR] Forbidden in code: {bad}"

    # Parse parameters
    try:
        params_schema = json.loads(parameters_json)
    except json.JSONDecodeError as e:
        return f"[ERROR] Invalid parameters_json: {e}"

    if not isinstance(params_schema, dict):
        return "[ERROR] parameters_json must be a JSON object"

    props = params_schema.get("properties", {})
    required = params_schema.get("required", [])
    if not isinstance(props, dict):
        return "[ERROR] properties must be an object"

    # Build OpenAI schema
    schema_block = {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {"type": "object", "properties": props, "required": required},
        },
    }
    schema_str = json.dumps(schema_block, ensure_ascii=False, indent=4)
    schema_patch = "    " + schema_str.replace("\n", "\n    ") + ",\n"

    # Build function signature from properties
    param_names = list(props.keys())
    sig_parts = []
    for p in param_names:
        if p in required:
            sig_parts.append(f"{p}: str")
        else:
            sig_parts.append(f"{p}: str = \"\"")
    sig = ", ".join(sig_parts)

    # Indent code
    code_lines = code.strip().split("\n")
    indented = "\n".join("    " + line for line in code_lines)

    func_def = f'''
def {name}({sig}) -> str:
    """{description.replace(chr(34), "'")}"""
{indented}
'''

    tools_path = Path(__file__).resolve()
    content = tools_path.read_text(encoding="utf-8")

    if f'"{name}"' in content and f"def {name}(" in content:
        return f"OK: tool {name} already exists (no changes)"

    # Escape for JSON string
    desc_esc = description.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")

    # 1. Insert schema before closing ] of TOOL_SCHEMAS
    schema_marker = "    },\n]"
    idx = content.rfind(schema_marker)
    if idx == -1:
        return "[ERROR] Could not find TOOL_SCHEMAS end"
    new_schema = (
        "    },\n"
        "    {\n"
        '        "type": "function",\n'
        '        "function": {\n'
        f'            "name": "{name}",\n'
        f'            "description": "{desc_esc}",\n'
        f'            "parameters": {json.dumps(params_schema, ensure_ascii=False)},\n'
        "        },\n"
        "    },\n"
        "]"
    )
    new_content = content[:idx] + new_schema + content[idx + len(schema_marker) :]

    # 2. Insert function before "# Tool registry"
    reg_marker = "\n# ---------------------------------------------------------------------------\n# Tool registry\n"
    reg_idx = new_content.find(reg_marker)
    if reg_idx == -1:
        return "[ERROR] Could not find registry"
    new_content = new_content[:reg_idx] + func_def + new_content[reg_idx:]

    # 3. Add to TOOL_FUNCTIONS (before closing })
    tf_marker = "}\n\n\ndef get_tools():"
    tf_idx = new_content.find(tf_marker)
    if tf_idx == -1:
        return "[ERROR] Could not find TOOL_FUNCTIONS"
    new_content = new_content[:tf_idx] + f'    "{name}": {name},\n' + new_content[tf_idx:]

    # Backup and apply
    original = tools_path.read_text(encoding="utf-8")
    tools_path.write_text(new_content, encoding="utf-8")

    # Run tests
    test_result = run_tests("seed/tests/")
    if "[PASSED]" not in test_result:
        tools_path.write_text(original, encoding="utf-8")
        evolution_log(
            "append",
            f"add_tool ROLLBACK: {name} — tests failed. Output: {test_result[:400]}",
        )
        return f"ROLLBACK: tests failed. Restored tools.py. {test_result[:300]}"

    return f"OK: added tool {name}, tests passed"


def browse_web(action: str, url: str = "", ref: str = "", text: str = "", path: str = "") -> str:
    """Run agent-browser CLI commands. Requires: npm install -g agent-browser && agent-browser install."""
    if not shutil.which("agent-browser"):
        return "[ERROR] agent-browser not found. Install: npm install -g agent-browser && agent-browser install"

    cmd = ["agent-browser"]
    if action == "open":
        if not url:
            return "[ERROR] url required for action=open"
        cmd.extend(["open", url])
    elif action == "snapshot":
        cmd.extend(["snapshot", "-i", "--json"])
    elif action == "click":
        if not ref:
            return "[ERROR] ref required for action=click (e.g. @e1)"
        cmd.extend(["click", ref])
    elif action == "fill":
        if not ref:
            return "[ERROR] ref required for action=fill"
        cmd.extend(["fill", ref, text or ""])
    elif action == "screenshot":
        if path:
            out_path = _resolve(path)
            cmd.extend(["screenshot", str(out_path)])
        else:
            cmd.append("screenshot")
    elif action == "get_url":
        cmd.extend(["get", "url"])
    elif action == "get_title":
        cmd.extend(["get", "title"])
    else:
        return f"[ERROR] unknown action: {action}"

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
            cwd=PROJECT_ROOT,
        )
        out = result.stdout.strip() or result.stderr.strip()
        if result.returncode != 0:
            return f"[ERROR] {out}"
        return out or "(no output)"
    except subprocess.TimeoutExpired:
        return "[ERROR] agent-browser timed out after 30s"
    except Exception as e:
        return f"[ERROR] {e}"


def rag_index(path: str) -> str:
    """Index file or directory into RAG."""
    from rag import rag_index as _rag_index
    return _rag_index(path)


def rag_index_evolution() -> str:
    """Index evolution-log, session-history, git log and diffs into RAG."""
    from rag import rag_index_evolution as _rag_index_evolution
    return _rag_index_evolution()


def rag_search(query: str, top_k: int = 5) -> str:
    """Search RAG knowledge base."""
    from rag import rag_search as _rag_search
    return _rag_search(query, top_k)


def rag_list() -> str:
    """List indexed documents. Progressive disclosure."""
    from rag import rag_list as _rag_list
    return _rag_list()


def rag_fetch(doc_id: str) -> str:
    """Fetch full document by id."""
    from rag import rag_fetch as _rag_fetch
    return _rag_fetch(doc_id)


def rag_index_docs(library_name: str) -> str:
    """Search for library docs, fetch, extract text, index into RAG."""
    import re

    search_result = web_search(f"{library_name} official documentation", count=5)
    if search_result.startswith("[ERROR]"):
        return search_result

    # Parse URLs from search result
    urls = []
    for m in re.finditer(r"https?://[^\s\)\]\"']+", search_result):
        url = m.group(0).rstrip(".,;:")
        if len(url) > 10 and url not in urls:
            urls.append(url)

    # Prefer docs URLs
    def score(u):
        s = 0
        if "docs.python.org" in u:
            s += 3
        if "readthedocs" in u or "rtfd" in u:
            s += 2
        if "pypi.org" in u or "github.com" in u:
            s += 1
        return s

    urls = sorted(set(urls), key=lambda u: -score(u))[:3]
    if not urls:
        return f"No documentation URLs found for {library_name}"

    knowledge_dir = PROJECT_ROOT / "data" / "memory" / "knowledge"
    knowledge_dir.mkdir(parents=True, exist_ok=True)
    out_path = knowledge_dir / f"{library_name.replace('-', '_')}_docs.md"

    chunks = [f"# {library_name} documentation\n\n"]
    with httpx.Client(timeout=30, follow_redirects=True) as client:
        for url in urls:
            try:
                resp = client.get(url)
                resp.raise_for_status()
                html = resp.text
                # Simple tag stripping
                text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
                text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
                text = re.sub(r"<[^>]+>", " ", text)
                text = re.sub(r"\s+", " ", text).strip()
                if len(text) > 500:
                    chunks.append(f"## Source: {url}\n\n{text[:50000]}\n\n")
            except Exception as e:
                chunks.append(f"## {url} — fetch failed: {e}\n\n")

    content = "\n".join(chunks)
    if len(content) < 200:
        return f"[ERROR] Could not extract enough text from {library_name} docs"
    out_path.write_text(content, encoding="utf-8")
    rel_path = str(out_path.relative_to(PROJECT_ROOT))
    return rag_index(rel_path)


def auto_discover_tools(module_path: str, dry_run: str = "") -> str:
    """Автоматически обнаруживает и загружает новые инструменты из модулей, обновляя реестр и логи эволюции."""
    """Auto-discover and load tools from specified module."""
    
    from pathlib import Path
    import importlib
    import inspect
    import json
    from datetime import datetime
    
    PROJECT_ROOT = Path(__file__).parent.parent
    
    def auto_discover_tools(module_path: str, dry_run: bool = False) -> str:
        """
        Discover new tools from a module and load them into the agent.
        
        Args:
            module_path: Module path (e.g., 'seed.tools')
            dry_run: If True, only analyze without applying changes
            
        Returns:
            Summary of discovered tools and actions taken
        """
        try:
            # Import module
            module = importlib.import_module(module_path)
            
            # Discover tools
            tools = []
            for name, obj in inspect.getmembers(module, inspect.isfunction):
                if hasattr(obj, '__tool_metadata__'):
                    tools.append({
                        'name': name,
                        'description': obj.__doc__ or 'No description',
                        'params': _extract_parameters(obj)
                    })
            
            # Load evolution log
            log_path = PROJECT_ROOT / "data" / "memory" / "evolution-log.md"
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Prepare log entry
            log_entry = f"\n## {current_time} — Авто-обнаружение инструментов: {module_path}\n\n"
            log_entry += f"**Найдено инструментов:** {len(tools)}\n\n"
            
            for tool in tools:
                log_entry += f"- **{tool['name']}**: {tool['description'][:80]}...\n"
            
            if dry_run:
                log_entry += "\n*Режим проверки: изменения не применены*\n"
                return f"✅ Dry run completed: {len(tools)} tools discovered in {module_path}"
            
            # Apply changes
            log_path.write_text(log_path.read_text() + log_entry)
            
            return f"✅ Loaded {len(tools)} tools from {module_path}: {[t['name'] for t in tools]}"
            
        except Exception as e:
            return f"❌ Discovery failed: {str(e)}"
    
    
    def _extract_parameters(func) -> dict:
        """Extract function parameters for tool metadata."""
        sig = inspect.signature(func)
        parameters = {}
        for param_name, param in sig.parameters.items():
            if param_name not in ('self', 'args', 'kwargs'):
                parameters[param_name] = {
                    'type': str(param.annotation) if param.annotation != inspect.Parameter.empty else 'string',
                    'required': param.default == inspect.Parameter.empty
                }
        return parameters

def evolution_monitor(action: str = "", module_path: str = "", tool_name: str = "", description: str = "", force_reload: str = "") -> str:
    """Monitors system evolution, triggers hot reload, and manages tool registration. Supports automatic performance tracking and evolution logging."""
    """
    Evolution Monitor Tool - Monitors system evolution and triggers improvements.
    """
    
    import json
    from pathlib import Path
    from typing import Any, Dict, Optional
    
    PROJECT_ROOT = Path(__file__).parent.parent
    
    
    def evolution_monitor(action: str, module_path: Optional[str] = None, 
                         tool_name: Optional[str] = None, 
                         description: Optional[str] = None,
                         force_reload: bool = False) -> str:
        """
        Monitor and manage system evolution with hot reload and tool registration.
        
        Args:
            action: Type of action ('reload', 'register', 'monitor', 'summary')
            module_path: Path to module for reload (e.g., seed.self_improve)
            tool_name: Name of tool to register
            description: Tool description
            force_reload: Force module reload
            
        Returns:
            JSON string with evolution results
        """
        from self_improve import SelfImprover, self_improve
        from datetime import datetime
        
        result = SelfImprover()
        
        if action == "reload":
            if not module_path:
                module_path = "seed.self_improve"
            
            module_info = result.load_module(module_path, force_reload)
            return json.dumps({
                "status": "success",
                "action": "reload",
                "module": module_info,
                "timestamp": datetime.now().isoformat()
            }, indent=2)
        
        elif action == "register":
            if not tool_name or not description:
                return json.dumps({
                    "status": "error",
                    "message": "tool_name and description required for registration"
                }, indent=2)
            
            registration = result.register_tool(
                tool_func=lambda: None,
                tool_name=tool_name,
                description=description
            )
            
            return json.dumps({
                "status": "success",
                "action": "register",
                "tool": registration,
                "timestamp": datetime.now().isoformat()
            }, indent=2)
        
        elif action == "monitor":
            performance = result.monitor_performance()
            return json.dumps({
                "status": "success",
                "action": "monitor",
                "performance": performance,
                "timestamp": datetime.now().isoformat()
            }, indent=2)
        
        elif action == "summary":
            summary = result.get_evolution_summary()
            return json.dumps({
                "status": "success",
                "action": "summary",
                "summary": summary,
                "timestamp": datetime.now().isoformat()
            }, indent=2)
        
        else:
            return json.dumps({
                "status": "error",
                "message": f"Unknown action: {action}"
            }, indent=2)

# ---------------------------------------------------------------------------
# Tool registry
# ---------------------------------------------------------------------------

TOOL_FUNCTIONS = {
    "read_file": read_file,
    "write_file": write_file,
    "list_dir": list_dir,
    "repo_patch": repo_patch,
    "safe_edit": safe_edit,
    "shell": shell,
    "git_commit": git_commit,
    "git_init": git_init,
    "git_status": git_status,
    "run_tests": run_tests,
    "web_search": web_search,
    "evolution_log": evolution_log,
    "git_diff": git_diff,
    "run_python": run_python,
    "transcribe_audio": transcribe_audio,
    "embedding": embedding,
    "rerank": rerank,
    "github_search_repos": github_search_repos,
    "github_read_file": github_read_file,
    "github_search_code": github_search_code,
    "rag_index": rag_index,
    "rag_index_evolution": rag_index_evolution,
    "rag_search": rag_search,
    "rag_list": rag_list,
    "rag_fetch": rag_fetch,
    "rag_index_docs": rag_index_docs,
    "working_memory": working_memory,
    "set_goal": set_goal,
    "read_goals": read_goals,
    "add_tool": add_tool,
    "ask_human": ask_human,
    "browse_web": browse_web,
    "auto_discover_tools": auto_discover_tools,
    "evolution_monitor": evolution_monitor,
}


def get_tools():
    return TOOL_SCHEMAS, TOOL_FUNCTIONS


def execute_tool(name: str, arguments: dict) -> str:
    func = TOOL_FUNCTIONS.get(name)
    if not func:
        return f"[ERROR] Unknown tool: {name}. Available: {list(TOOL_FUNCTIONS.keys())}"
    try:
        return func(**arguments)
    except ToolError as e:
        return f"[ERROR] {e}"
    except TypeError as e:
        return f"[ERROR] Bad arguments for {name}: {e}"
    except Exception as e:
        return f"[ERROR] {type(e).__name__}: {e}"


class ToolError(Exception):
    """Raised when a tool encounters a known error."""


class AskHumanPause(Exception):
    """Raised by ask_human when session must pause for user reply (Telegram mode)."""

    def __init__(self, question: str, tool_call_id: str = ""):
        self.question = question
        self.tool_call_id = tool_call_id
        super().__init__(question)


# Context set by loop for ask_human (summary_queue, chat_id)
_loop_context: dict = {}
