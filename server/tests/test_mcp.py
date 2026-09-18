import asyncio
import json
import sys
import threading

import pytest

from app import config
from app.tools.registry import Registry, ToolContext

_SPEC = (sys.executable, str(config.BASE_DIR.parent / "scripts" / "mcp_demo_server.py"))
_EXPOSE_SPEC = (sys.executable, str(config.BASE_DIR.parent / "scripts" / "mcp_expose_server.py"))


class _LoopWorker:
    """Runs the ENTIRE MCP session (connect → calls → close) inside ONE
    anyio task on a dedicated loop. anyio cancel scopes must be entered
    and exited in the same task; pytest's loop state on the main thread
    also breaks stdio MCP sessions, so we stay fully isolated."""

    def __init__(self) -> None:
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()

    def _serve(self) -> None:
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def run(self, scenario):
        """`scenario` is a zero-arg coroutine function; runs to completion
        and returns its value."""
        return asyncio.run_coroutine_threadsafe(scenario(), self._loop).result()

    def stop(self) -> None:
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.join(timeout=5)


@pytest.fixture(scope="module")
def worker():
    w = _LoopWorker()
    yield w
    w.stop()


@pytest.fixture()
def scratch_file(tmp_path):
    config.SANDBOX_DIR.mkdir(parents=True, exist_ok=True)
    target = config.SANDBOX_DIR / "scratch.txt"
    target.write_text("hello from external workspace\n", encoding="utf-8")
    yield target
    target.unlink(missing_ok=True)


def test_bridge_lists_remote_tools_with_read_only_hints(worker):
    from app.mcp_bridge import MCPBridge

    async def scenario():
        bridge = MCPBridge(_SPEC)
        try:
            await bridge.connect()
            tools = await bridge.list_tools()
            return {t["name"]: t for t in tools}
        finally:
            await bridge.close()

    names = worker.run(scenario)
    assert set(names) == {"workspace_read", "workspace_append"}
    assert names["workspace_read"]["read_only"] is True
    assert names["workspace_append"]["read_only"] is False


def test_bridge_calls_remote_read_tool(worker, scratch_file):
    from app.mcp_bridge import MCPBridge

    async def scenario():
        bridge = MCPBridge(_SPEC)
        try:
            await bridge.connect()
            return await bridge.call_tool(
                "workspace_read", {"filename": scratch_file.name}
            )
        finally:
            await bridge.close()

    result = worker.run(scenario)
    assert result["ok"] is True
    assert "hello from external workspace" in result["output"]


def test_bridge_calls_remote_append_tool(worker, scratch_file):
    from app.mcp_bridge import MCPBridge

    async def scenario():
        bridge = MCPBridge(_SPEC)
        try:
            await bridge.connect()
            return await bridge.call_tool(
                "workspace_append",
                {"filename": scratch_file.name, "text": "line two"},
            )
        finally:
            await bridge.close()

    result = worker.run(scenario)
    assert result["ok"] is True
    assert "line two" in scratch_file.read_text(encoding="utf-8")


def test_bridge_registers_adapters_in_registry(worker, scratch_file):
    from app.mcp_bridge import install

    registry = Registry()
    result_holder = {}

    async def scenario():
        bridge = await install(registry, _SPEC)
        try:
            result_holder["read"] = registry.get("mcp_workspace_read")
            result_holder["append"] = registry.get("mcp_workspace_append")
            result_holder["result"] = await registry.execute(
                "mcp_workspace_read", {"filename": "scratch.txt"}, ToolContext()
            )
        finally:
            await bridge.close()

    worker.run(scenario)

    read = result_holder["read"]
    append = result_holder["append"]
    assert read is not None and append is not None
    assert read.requires_approval is False
    assert append.requires_approval is True
    assert result_holder["result"]["ok"] is True
    assert "hello from external workspace" in result_holder["result"]["output"]


def test_bridge_consumes_project_exposed_tools(worker):
    """Recursive proof: the MCP client can consume the tools THIS project
    exposes as a server — the tool layer is protocol-agnostic both ways."""
    from app.mcp_bridge import MCPBridge

    async def scenario():
        bridge = MCPBridge(_EXPOSE_SPEC)
        try:
            await bridge.connect()
            tools = await bridge.list_tools()
            names = {t["name"]: t for t in tools}
            calc = await bridge.call_tool(
                "calculator", {"args_json": json.dumps({"expression": "2 + 2"})}
            )
            return names, calc
        finally:
            await bridge.close()

    names, calc = worker.run(scenario)
    assert {"calculator", "file_store", "rag_search", "web_search", "time.now"} <= set(names)
    assert names["calculator"]["read_only"] is True
    assert names["file_store"]["read_only"] is False  # HITL-gated tool surfaces destructive hint
    assert calc["ok"] is True
    assert "4.0" in calc["output"]