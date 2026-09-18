#!/usr/bin/env python3
"""Expose this project's built-in tools as a standard MCP server.

Any MCP host (Claude Desktop, Cursor, other agents...) can connect over
stdio and call `calculator`, `file_store`, `web_search`, `rag_search`,
`time.now` — HITL approval is surfaced via the read-only hint, matching
the inner registry's `requires_approval` flags.

Usage (from server/):  uv run python ../scripts/mcp_expose_server.py
"""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))

from app import config
from app.llm.client import LLMClient
from app.rag.retrieve import Retriever
from app.rag.store import VectorStore
from app.tools.registry import ToolContext, build_default_registry
from mcp import types as mcp_types
from mcp.server.mcpserver import MCPServer


def _make_handler(tool, sandbox):
    async def handler(args_json: str = "{}") -> str:
        args = json.loads(args_json)
        result = await tool.run(args, sandbox)
        if not result.get("ok"):
            return f"error: {result.get('error')}"
        return json.dumps(result.get("output"), ensure_ascii=False)

    handler.__name__ = f"run_{tool.name}"  # MCPServer derives a type name from func.__name__
    handler.__qualname__ = handler.__name__
    return handler


def _build() -> MCPServer:
    config.ensure_dirs()
    store = VectorStore()
    store.load(config.VSTORE_PATH)
    ctx = ToolContext(
        retrieval=Retriever(store),
        llm=LLMClient(),
        sandbox=config.SANDBOX_DIR,
    )
    registry = build_default_registry(ctx)

    server = MCPServer(name="AgentWorkflowDemo", version="0.1.0")

    for name in registry.names():
        tool_ref = registry.get(name)
        schema_hint = tool_ref.args_schema or "{}"
        server.add_tool(
            _make_handler(tool_ref, ctx),
            name=name,
            title=name,
            description=f"{tool_ref.description}\nargs schema: {schema_hint}",
            annotations=mcp_types.ToolAnnotations(
                read_only_hint=not tool_ref.requires_approval,
                destructive_hint=tool_ref.requires_approval,
            ),
        )
    return server


if __name__ == "__main__":
    asyncio.run(_build().run_stdio_async())