import asyncio
import time
import uuid
from dataclasses import dataclass, field

from . import config


@dataclass
class PendingApproval:
    action_id: str
    step_id: str
    tool: str
    summary: str
    decision: str | None = None
    event: asyncio.Event = field(default_factory=asyncio.Event)


@dataclass
class SessionState:
    session_id: str
    created_at: float
    pending: dict[str, PendingApproval] = field(default_factory=dict)
    events: list[dict] = field(default_factory=list)

    def record(self, event_type: str, payload: dict) -> None:
        self.events.append({"event": event_type, "data": payload})
        if len(self.events) > 200:  # cap: replay stays cheap
            del self.events[: len(self.events) - 200]


class StateStore:
    """In-memory per-session state: approvals, memory (summary, recent events)."""

    def __init__(self) -> None:
        self._sessions: dict[str, SessionState] = {}
        self._memory: dict[str, list[str]] = {}

    def get_or_create(self, session_id: str | None = None) -> SessionState:
        if not session_id:
            session_id = "sess_" + uuid.uuid4().hex[:12]
        session = self._sessions.get(session_id)
        if session is None:
            session = SessionState(session_id=session_id, created_at=time.time())
            self._sessions[session_id] = session
        return session

    def get(self, session_id: str) -> SessionState | None:
        return self._sessions.get(session_id)

    def add_approval(self, session_id: str, approval: PendingApproval) -> None:
        self._sessions[session_id].pending[approval.action_id] = approval

    def resolve(self, session_id: str, action_id: str, decision: str) -> bool:
        session = self._sessions.get(session_id)
        if not session or action_id not in session.pending:
            return False
        if decision not in ("allow", "deny"):
            raise ValueError("decision must be 'allow' or 'deny'")
        approval = session.pending[action_id]
        approval.decision = decision
        approval.event.set()
        return True

    def remember(self, session_id: str, line: str, max_lines: int = 50) -> None:
        lines = self._memory.setdefault(session_id, [])
        lines.append(line)
        if len(lines) > max_lines:
            del lines[: len(lines) - max_lines]

    def recall(self, session_id: str) -> list[str]:
        return list(self._memory.get(session_id, []))