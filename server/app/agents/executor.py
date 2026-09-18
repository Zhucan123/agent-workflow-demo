import asyncio
import json
import re
from dataclasses import dataclass
from typing import Any, Callable

from .. import config
from ..llm.client import LLMClient
from ..state import StateStore
from ..tools.registry import Registry, ToolContext

EmitCB = Callable[[str, dict[str, Any]], Any]


@dataclass
class StepOutcome:
    step_id: str
    tool: str
    ok: bool
    output: dict | None
    approved: bool | None = None
    duration_ms: int = 0


_TEMPLATE_RE = re.compile(r"\{\{\s*step-(\d+)\s*\.\s*(result|output|error)\s*\}\}")


def _render_args(args: dict[str, Any], outcomes: dict[str, StepOutcome]) -> dict[str, Any]:
    """Substitute {{step-N.result}} / {{step-N.output}} / {{step-N.error}}
    placeholders with previous step outcomes, so a plan can chain steps
    that consume the results of earlier ones."""
    if not outcomes:
        return args
    rendered: dict[str, Any] = dict(args)
    for key, value in rendered.items():
        if not isinstance(value, str):
            continue

        def repl(match: re.Match) -> str:
            index, field = int(match.group(1)), match.group(2)
            outcome = outcomes.get(f"step-{index}")
            if outcome is None:
                return match.group(0)
            if outcome.output is None:
                return ""
            if isinstance(outcome.output, (dict, list)):
                return json.dumps(outcome.output, ensure_ascii=False)
            return str(outcome.output)

        rendered[key] = _TEMPLATE_RE.sub(repl, value)
    return rendered


class Executor:
    """Runs planned steps, streams per-tool events, and gates risky
    actions behind HITL approval (approval.request → await decision)."""

    def __init__(
        self,
        registry: Registry,
        state: StateStore,
        llm: LLMClient,
        ctx: ToolContext | None = None,
    ) -> None:
        self.registry = registry
        self.state = state
        self.llm = llm
        self.ctx = ctx or ToolContext()

    async def run(
        self,
        session_id: str,
        plan,
        emit: EmitCB,
    ) -> list[StepOutcome]:
        outcomes: list[StepOutcome] = []
        outcome_by_id: dict[str, StepOutcome] = {}
        for step in plan.steps:
            started = asyncio.get_event_loop().time()
            args = _render_args(step.args, outcome_by_id)
            await emit("tool.call", {"step_id": step.id, "tool": step.tool, "args": args})
            approved: bool | None = True
            if step.requires_approval:
                approved = await self._request_approval(session_id, step, emit)
            if approved is False:
                outcome = StepOutcome(step.id, step.tool, ok=False, output=None, approved=False)
                outcomes.append(outcome)
                outcome_by_id[step.id] = outcome
                await emit(
                    "tool.result",
                    {"step_id": step.id, "tool": step.tool, "ok": False, "output": None, "decision": "denied"},
                )
                continue
            result = await self.registry.execute(step.tool, args, self.ctx)
            elapsed_ms = int((asyncio.get_event_loop().time() - started) * 1000)
            outcome = StepOutcome(
                step.id, step.tool, ok=result["ok"], output=result.get("output"), approved=approved
            )
            outcomes.append(outcome)
            outcome_by_id[step.id] = outcome
            await emit(
                "tool.result",
                {
                    "step_id": step.id,
                    "tool": step.tool,
                    "ok": result["ok"],
                    "output": result.get("output"),
                    "error": result.get("error"),
                    "duration_ms": elapsed_ms,
                },
            )
        return outcomes

    async def _request_approval(self, session_id: str, step, emit: EmitCB) -> bool:
        from ..state import PendingApproval

        action_id = f"act_{step.id}"
        approval = PendingApproval(
            action_id=action_id,
            step_id=step.id,
            tool=step.tool,
            summary=f"Tool '{step.tool}' with args {step.args}",
        )
        self.state.add_approval(session_id, approval)
        await emit(
            "approval.request",
            {
                "action_id": action_id,
                "step_id": step.id,
                "tool": step.tool,
                "summary": approval.summary,
                "timeout_s": int(config.APPROVAL_TIMEOUT_S),
            },
        )
        try:
            await asyncio.wait_for(approval.event.wait(), timeout=config.APPROVAL_TIMEOUT_S)
        except asyncio.TimeoutError:
            raise TimeoutError(f"HITL approval timed out for {action_id}")
        return approval.decision == "allow"