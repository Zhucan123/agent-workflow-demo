import re
from typing import Any

import httpx

from .registry import Tool

_RESULT_CLEAN = re.compile(r"<[^>]+>|\s+")


class WebSearchTool(Tool):
    """Zero-key web search (DuckDuckGo HTML endpoint). Best effort —
    returns whatever is reachable; never fails the pipeline."""

    name = "web_search"
    description = (
        'Search the web for a query. Args: {"query": "refund policy", "max": 5}. '
        "Returns up to max results as title/url/snippet."
    )

    async def run(self, args: dict[str, Any], ctx) -> dict[str, Any]:
        query = str(args.get("query", "")).strip()
        if not query:
            return {"ok": False, "output": None, "error": "query is required"}
        results: list[dict] = []
        try:
            async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
                resp = await client.get(
                    "https://html.duckduckgo.com/html/",
                    params={"q": query},
                    headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) model-agent/0.1"},
                )
                resp.raise_for_status()
            for block in re.findall(
                r'<a[^>]*class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
                resp.text,
            )[: int(args.get("max", 5))]:
                url = block[0].split("&uddg=")[-1]
                title = _RESULT_CLEAN.sub(" ", block[1]).strip()
                results.append({"title": title, "url": url})
        except Exception as exc:  # best effort: never break the pipeline
            return {"ok": False, "output": None, "error": f"search unavailable: {exc}"}
        return {"ok": True, "output": {"query": query, "results": results}}