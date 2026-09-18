import re
from pydantic import BaseModel, Field

from ..llm.client import LLMClient
from ..tools.registry import Registry, ToolSpec

_KEYWORDS_CALC = ("calculate", "compute", "sum", "total", "multiply", "tax", "price", "discount", "add")
_KEYWORDS_WRITE = ("write", "save", "receipt", "report", "create file", "writefile")
_KEYWORDS_READ = ("read the file", "read file", "cat file", "print the file", "show me the file", "show the file")
_KEYWORDS_SEARCH = ("search", "look up", "find", "online")
_KEYWORDS_RAG = ("knowledge", "policy", "faq", "manual", "docs", "guide", "refund")

_TOOL_ARG_SCHEMAS: dict[str, str] = {
    "calculator": '{"expression": "<e.g. 3 * 129.9 * 1.15>"}',
    "file_store": '{"action": "read|write", "filename": "<file name>", "content": "<body, only for write>"}',
    "web_search": '{"query": "<search phrase>", "max": 5}',
    "rag_search": '{"query": "<question about company docs>", "k": 3}',
    "time.now": "{}",
}


class ToolStep(BaseModel):
    id: str = Field(description="stable step identifier within the plan")
    tool: str = Field(description="tool name from the registry")
    args: dict = Field(default_factory=dict)
    requires_approval: bool = False


class Plan(BaseModel):
    reason: str
    steps: list[ToolStep]


def _extract_expression(task: str) -> str:
    """Best-effort extraction of an arithmetic expression from a task string.
    Falls back to a canonical demo expression."""
    task_low = task.lower()
    numbers = re.findall(r"\d+(?:\.\d+)?", task_low)
    if "tax" in task_low and len(numbers) >= 3:
        return f"{numbers[0]} * {numbers[1]} * 1.15"
    if "tax" in task_low and len(numbers) >= 2:
        core = " * ".join(numbers[1:])
        return f"{core} * 1.15"
    if len(numbers) >= 2:
        return " * ".join(numbers[:2])
    if numbers:
        return f"{numbers[0]} * 2"
    return "2 + 3 * 4"


def _stub_plan(task: str) -> Plan:
    low = task.lower()
    steps: list[ToolStep] = []
    seq = 0

    def next_id() -> str:
        nonlocal seq
        seq += 1
        return f"step-{seq}"

    if any(k in low for k in _KEYWORDS_CALC):
        steps.append(
            ToolStep(
                id=next_id(),
                tool="calculator",
                args={"expression": _extract_expression(task)},
                requires_approval=False,
            )
        )
    if any(k in low for k in _KEYWORDS_RAG):
        steps.append(
            ToolStep(id=next_id(), tool="rag_search", args={"query": task[:80], "k": 3})
        )
    if any(k in low for k in _KEYWORDS_SEARCH):
        steps.append(ToolStep(id=next_id(), tool="web_search", args={"query": task[:80]}))
    if any(k in low for k in _KEYWORDS_READ):
        name_match = re.search(r"(?:named|called)\s+([\w.\-]+\.\w+)", low)
        filename = name_match.group(1) if name_match else "agent-output.txt"
        steps.append(
            ToolStep(
                id=next_id(),
                tool="file_store",
                args={"action": "read", "filename": filename},
                requires_approval=False,
            )
        )
    if any(k in low for k in _KEYWORDS_WRITE):
        steps.append(
            ToolStep(
                id=next_id(),
                tool="file_store",
                args={"action": "write", "filename": "agent-output.txt", "content": ""},
                requires_approval=True,
            )
        )
    if not steps:
        steps.append(ToolStep(id=next_id(), tool="time.now", args={}))
    return Plan(reason="stub plan formed from keyword heuristics", steps=steps)


def _build_tool_prompt(specs: list[ToolSpec]) -> str:
    lines = ["Available tools; use ONLY these, with exact args schema:", ""]
    for spec in specs:
        schema = spec.args_schema or _TOOL_ARG_SCHEMAS.get(spec.name, "{}")
        approval = ", HITL approval required" if spec.requires_approval else ""
        lines.append(f"- {spec.name}{approval}: {spec.description}")
        lines.append(f"  args schema: {schema}")
    lines.append(
        ""
        "- rag_search is the ONLY way to read company documents (policy/manual/FAQ). "
        "These documents are NOT stored as files."
    )
    lines.append(
        "- file_store only reads/writes the user's own workspace files "
        "(e.g. writing or reading a receipt); it cannot see company documents."
    )
    return "\n".join(lines)


class Planner:
    """Decomposes a task into executable steps. Never executes tools itself."""

    def __init__(self, llm: LLMClient, registry: Registry) -> None:
        self.llm = llm
        self.registry = registry

    async def plan(self, task: str) -> tuple[Plan, dict]:
        if self.llm.provider == "stub":
            plan = _stub_plan(task)
            return plan, {"prompt_tokens": 0, "completion_tokens": 0, "cost_estimate": 0.0}

        tool_prompt = _build_tool_prompt(self.registry.describe_all())
        messages = [
            {
                "role": "system",
                "content": (
                    "You are the Planner agent. Decompose the user task into a "
                    "maximal minimal sequence of tool steps. If a step writes or "
                    "modifies persistent state, set requires_approval=true. "
                    "To reference a previous step's result inside a later step's "
                    'args, use the placeholder {{step-N.output}} — never invent '
                    "other placeholder text or copy values from memory. "
                    'Answer with strict JSON: {"reason": "...", "steps": '
                    '[{"id":"step-1","tool":"<name>","args":{...},'
                    '"requires_approval":bool}]}\n'
                    + tool_prompt
                ),
            },
            {"role": "user", "content": task},
        ]
        data = await self.llm.complete_json(messages)
        return Plan.model_validate(data), data.pop("usage", {}) or {}