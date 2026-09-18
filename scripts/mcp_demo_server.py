#!/usr/bin/env python3
"""Bundled external MCP server (the "other side of the wire").

Purpose: demonstrate that this project's agent can consume tools from
ANY MCP server over the standard protocol — not just its own built-ins.
This one simulates an independent, zero-key service with two tools that
operate on the sandbox workspace over stdio. Run it, point the bridge at
it (AGENT_MCP_MODE=demo), and the agent gains `mcp_workspace_read` /
`mcp_workspace_append` through normal planning.

Usage (from server/):  uv run python ../scripts/mcp_demo_server.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))

import asyncio

from app import config
from mcp.server.mcpserver import MCPServer

_PEER = "ExternalWorkspace"
_DIR = config.SANDBOX_DIR


def _read(filename: str) -> str:
    target = (_DIR / filename).resolve()
    if _DIR.resolve() not in target.parents:
        raise ValueError("path escapes the external workspace")
    return target.read_text(encoding="utf-8", errors="replace")


def _append(filename: str, text: str) -> str:
    target = _DIR / filename
    if _DIR.resolve() not in target.resolve().parents:
        raise ValueError("path escapes the external workspace")
    with target.open("a", encoding="utf-8") as fh:
        fh.write(text + "\n")
    return f"appended: {filename} ({len(text)} chars)"


def build() -> MCPServer:
    from mcp import types as mcp_types

    server = MCPServer(name=_PEER)

    async def workspace_read(filename: str) -> str:
        """Read a file from the external workspace (read-only view)."""
        try:
            return _read(filename)
        except FileNotFoundError:
            return f"file not found: {filename}"

    async def workspace_append(filename: str, text: str) -> str:
        """Append a line of text to a file in the external workspace."""
        return _append(filename, text)

    server.add_tool(
        workspace_read,
        title="Read (external workspace)",
        annotations=mcp_types.ToolAnnotations(read_only_hint=True),
    )
    server.add_tool(workspace_append, title="Append (external workspace)")
    return server


if __name__ == "__main__":
    config.ensure_dirs()
    print(f"MCP demo server '{_PEER}' on stdio, workspace={_DIR}", file=sys.stderr, flush=True)
    asyncio.run(build().run_stdio_async())