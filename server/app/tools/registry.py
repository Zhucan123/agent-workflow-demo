from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class ToolContext:
    """Injected dependencies available to tools at runtime."""
    def __init__(self, retrieval=None, llm=None, sandbox=None):
        self.retrieval = retrieval
        self.llm = llm
        self.sandbox = sandbox


@dataclass
class ToolSpec:
    name: str
    description: str
    requires_approval: bool = False
    args_schema: str | None = None


class Tool:
    name: str = ""
    description: str = ""
    requires_approval: bool = False
    args_schema: str | None = None

    async def run(self, args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
        raise NotImplementedError


class Registry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def names(self) -> list[str]:
        return sorted(self._tools)

    def describe_all(self) -> list[ToolSpec]:
        return [
            ToolSpec(t.name, t.description, t.requires_approval, t.args_schema)
            for t in self._tools.values()
        ]

    async def execute(self, name: str, args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
        tool = self._tools.get(name)
        if tool is None:
            return {"ok": False, "output": None, "error": f"unknown tool: {name}"}
        try:
            return await tool.run(args, ctx)
        except Exception as exc:  # noqa: BLE001 - tool errors are data, not crashes
            return {"ok": False, "output": None, "error": f"{type(exc).__name__}: {exc}"}


def build_default_registry(ctx: ToolContext) -> Registry:
    from .calculator import CalculatorTool
    from .file_store import FileStoreTool
    from .time_now import TimeNowTool
    from .web_search import WebSearchTool
    from .rag_search import RagSearchTool

    registry = Registry()
    registry.register(CalculatorTool())
    registry.register(TimeNowTool())
    registry.register(FileStoreTool(ctx.sandbox))
    registry.register(WebSearchTool())
    registry.register(RagSearchTool(ctx.retrieval))
    return registry