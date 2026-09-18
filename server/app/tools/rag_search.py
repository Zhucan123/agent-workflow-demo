from typing import Any

from .registry import Tool


class RagSearchTool(Tool):
    """Query the local hybrid-retrieval corpus; feeds context to the pipeline."""

    name = "rag_search"
    description = (
        'Search the company knowledge base. Args: {"query": "refund policy", '
        '"k": 3}. Returns top-k documents with scores.'
    )

    def __init__(self, retrieval=None) -> None:
        self.retrieval = retrieval

    async def run(self, args: dict[str, Any], ctx) -> dict[str, Any]:
        retriever = self.retrieval or getattr(ctx, "retrieval", None)
        if retriever is None:
            return {"ok": False, "output": None, "error": "retrieval not configured"}
        query = str(args.get("query", "")).strip()
        if not query:
            return {"ok": False, "output": None, "error": "query is required"}
        hits = retriever.search(query, k=int(args.get("k", 3)))
        return {"ok": True, "output": {"query": query, "hits": hits}}