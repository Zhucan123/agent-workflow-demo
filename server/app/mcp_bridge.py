"""MCP client bridge: lets the agent consume tools from any external
MCP server and exposes them through the same typed Tool registry as the
built-ins (so planning, HITL approval and SSE events work unchanged).

The bridge is generic: point it at any MCP server command
(`AGENT_MCP_MODE`), and every remote tool becomes `mcp_<name>`.
"""
from __future__ import annotations

import json
from typing import Any

from . import config
from .tools.registry import Registry, Tool, ToolContext

_WRITE_KEYWORDS = (
    "write",
    "append",
    "create",
    "update",
    "delete",
    "modify",
    "send",
    "remove",
)


class MCPBridge:
    """Owns the stdio subprocess + ClientSession for one MCP server."""

    def __init__(self, spec, timeout_s: float | None = None) -> None:
        self._spec = spec
        self._timeout = timeout_s or config.MCP_TIMEOUT_S
        self._session = None
        self._exit_stack = None

    async def connect(self) -> None:
        from mcp import ClientSession, StdioServerParameters  # deferred import
        from mcp.client.stdio import stdio_client
        import contextlib

        params = StdioServerParameters(
            command=self._spec[0],
            args=list(self._spec[1:]),
            cwd=str(config.BASE_DIR),
        )
        self._exit_stack = contextlib.AsyncExitStack()
        streams = await self._exit_stack.enter_async_context(stdio_client(params))
        self._session = await self._exit_stack.enter_async_context(ClientSession(*streams))
        await self._session.initialize()

    async def list_tools(self) -> list[dict[str, Any]]:
        result = await self._session.list_tools()
        tools = []
        for tool in result.tools:
            annotation = tool.annotations
            read_only = bool(annotation and getattr(annotation, "read_only_hint", False))
            if not read_only:
                read_only = not any(k in (tool.description or "").lower() for k in _WRITE_KEYWORDS)
            tools.append(
                {
                    "name": tool.name,
                    "description": tool.description or "",
                    "input_schema": tool.input_schema,
                    "read_only": read_only,
                }
            )
        return tools

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        result = await self._session.call_tool(name, arguments, read_timeout_seconds=self._timeout)
        if result.is_error:
            return {"ok": False, "output": None, "error": _render_content(result)}
        return {"ok": True, "output": _render_content(result), "error": None}

    async def close(self) -> None:
        if self._exit_stack is not None:
            await self._exit_stack.aclose()


class MCPToolAdapter(Tool):
    """Wraps one remote MCP tool behind the local Tool interface."""

    def __init__(
        self,
        bridge: MCPBridge,
        name: str,
        description: str,
        read_only: bool,
        remote_name: str | None = None,
        args_schema: str | None = None,
    ) -> None:
        self.name = name  # local registry name (mcp_<remote>)
        self.description = description
        self.requires_approval = not read_only
        self.args_schema = args_schema
        self._bridge = bridge
        self._remote_name = remote_name or name

    async def run(self, args: dict[str, Any], ctx: ToolContext | None = None) -> dict[str, Any]:
        return await self._bridge.call_tool(self._remote_name, args)


def _render_content(result) -> str:
    """Collapse MCP result content blocks into a single text value."""
    parts: list[str] = []
    for block in result.content:
        text = getattr(block, "text", None)
        if text is not None:
            parts.append(text)
    if not parts and result.structured_content is not None:
        return getattr(result.structured_content, "model_dump_json", None) or str(result.structured_content)
    return "\n".join(parts)


_SERVER_PATH = config.BASE_DIR.parent / "scripts" / "mcp_demo_server.py"


def resolve_spec() -> tuple | None:
    """Turn AGENT_MCP_MODE into a stdio command tuple, or None."""
    import sys

    mode = config.MCP_MODE
    if not mode or mode == "off":
        return None
    if mode == "demo":
        return (sys.executable, str(_SERVER_PATH))
    if mode.startswith("stdio:"):
        cmd = mode[len("stdio:"):].strip()
        return tuple(cmd.split())
    return (mode.strip(),)


async def install(registry: Registry, spec: tuple) -> MCPBridge:
    """Connect the bridge and register every remote tool into `registry`."""
    bridge = MCPBridge(spec)
    await bridge.connect()
    for tool in await bridge.list_tools():
        registry.register(
            MCPToolAdapter(
                bridge,
                name=f"mcp_{tool['name']}",
                description=tool["description"],
                read_only=tool["read_only"],
                remote_name=tool["name"],
                args_schema=json.dumps(tool["input_schema"], ensure_ascii=False),
            )
        )
    return bridge