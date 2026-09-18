import asyncio

from app import config
from app.agents.executor import Executor
from app.llm.client import LLMClient
from app.state import StateStore
from app.tools.registry import Registry, ToolContext


class _Step:
    def __init__(self, step_id="s1", tool="file_store", args=None, requires_approval=True):
        self.id = step_id
        self.tool = tool
        self.args = args or {"action": "write", "filename": "a.txt", "content": "hello"}
        self.requires_approval = requires_approval


async def test_approval_gate_resolves_allow(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "APPROVAL_TIMEOUT_S", 10)
    state = StateStore()
    session = state.get_or_create()
    events: list[tuple[str, dict]] = []

    async def emit(event, payload):
        events.append((event, payload))

    executor = Executor(Registry(), state, LLMClient(mode="stub"), ToolContext(sandbox=tmp_path))
    pending = asyncio.create_task(
        executor._request_approval(session.session_id, _Step(), emit)
    )
    await asyncio.sleep(0.1)
    state.resolve(session.session_id, "act_s1", "allow")
    assert await pending is True
    assert events[0][0] == "approval.request"
    assert events[0][1]["action_id"] == "act_s1"


async def test_approval_gate_resolves_deny(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "APPROVAL_TIMEOUT_S", 10)
    state = StateStore()
    session = state.get_or_create()
    events: list[tuple[str, dict]] = []

    async def emit(event, payload):
        events.append((event, payload))

    executor = Executor(Registry(), state, LLMClient(mode="stub"), ToolContext(sandbox=tmp_path))
    pending = asyncio.create_task(
        executor._request_approval(session.session_id, _Step(), emit)
    )
    await asyncio.sleep(0.1)
    state.resolve(session.session_id, "act_s1", "deny")
    assert await pending is False