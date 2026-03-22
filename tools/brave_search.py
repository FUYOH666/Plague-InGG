"""Search the web via Brave Search API. The agent's window to the world."""

import os
import httpx
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

TOOL_SPEC = {
    "name": "brave_search",
    "description": "Search the web. Returns top results with titles and snippets.",
    "params": {"query": "Search query", "count": "Number of results (default 5)"},
}

API_KEY = os.getenv("BRAVE_API_KEY", "")


def execute(params: dict) -> str:
    query = params.get("query", "")
    count = int(params.get("count", 5))
    if not query:
        return "No query provided."
    if not API_KEY:
        return "BRAVE_API_KEY not set in .env"

    try:
        resp = httpx.get(
            "https://api.search.brave.com/res/v1/web/search",
            params={"q": query, "count": count},
            headers={"X-Subscription-Token": API_KEY, "Accept": "application/json"},
            timeout=15.0,
        )
        resp.raise_for_status()
        data = resp.json()
        results = data.get("web", {}).get("results", [])
        if not results:
            return "No results found."
        out = []
        for r in results[:count]:
            out.append(f"**{r.get('title', '')}**\n{r.get('url', '')}\n{r.get('description', '')}\n")
        return "\n".join(out)
    except Exception as e:
        return f"Search error: {e}"
