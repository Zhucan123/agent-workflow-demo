import ast
import operator
from typing import Any

from .registry import Tool

_ALLOWED_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}
_ALLOWED_FUNCS = {"round": round, "abs": abs, "min": min, "max": max}


def safe_eval(expression: str) -> float:
    """Evaluate a pure arithmetic expression without eval()."""
    tree = ast.parse(expression, mode="eval")

    def walk(node: ast.AST):
        if isinstance(node, ast.Expression):
            return walk(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in _ALLOWED_OPS:
            return _ALLOWED_OPS[type(node.op)](walk(node.left), walk(node.right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in _ALLOWED_OPS:
            return _ALLOWED_OPS[type(node.op)](walk(node.operand))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            fn = _ALLOWED_FUNCS.get(node.func.id)
            if fn is None or not all(isinstance(a, ast.Constant) for a in node.args):
                raise ValueError(f"disallowed function: {node.func.id}")
            return fn(*(a.value for a in node.args))
        raise ValueError(f"unsupported syntax: {type(node).__name__}")

    result = walk(tree)
    return float(result)


class CalculatorTool(Tool):
    name = "calculator"
    description = (
        "Evaluate a pure arithmetic expression and return the numeric result. "
        'Args: {"expression": "3 * 129.9 * 1.15"}. Supports + - * / % ** ( ) '
        "and round/abs/min/max."
    )

    async def run(self, args: dict[str, Any], ctx) -> dict[str, Any]:
        expression = str(args.get("expression", "")).strip()
        if not expression:
            return {"ok": False, "output": None, "error": "expression is required"}
        value = safe_eval(expression)
        return {"ok": True, "output": {"expression": expression, "result": value}}