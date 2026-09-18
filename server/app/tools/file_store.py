from pathlib import Path
from typing import Any

from .. import config
from .registry import Tool


class FileStoreTool(Tool):
    """Sandboxed file read/write. Writes always require human approval (HITL)."""

    name = "file_store"
    description = (
        'Read or write a plain-text file inside the sandbox. '
        'Args: {"action": "write"|"read", "filename": "receipt.txt", '
        '"content": "..."}. Filenames are basename-only; paths outside '
        "the sandbox are rejected."
    )
    requires_approval = True

    def __init__(self, sandbox: Path | None = None) -> None:
        self.sandbox = (sandbox or config.SANDBOX_DIR).resolve()

    def _resolve(self, filename: str) -> Path:
        name = Path(filename).name  # basename only — no traversal
        if not name:
            raise ValueError("filename is required")
        return (self.sandbox / name).resolve()

    async def run(self, args: dict[str, Any], ctx) -> dict[str, Any]:
        action = str(args.get("action", "")).lower()
        filename = str(args.get("filename", ""))
        target = self._resolve(filename)
        if not target.parent or str(target.parent) != str(self.sandbox):
            return {"ok": False, "output": None, "error": "path escapes sandbox"}

        if action == "write":
            content = str(args.get("content", ""))
            if len(content.encode("utf-8")) > config.SANDBOX_MAX_FILE_BYTES:
                return {"ok": False, "output": None, "error": "content too large"}
            target.write_text(content, encoding="utf-8")
            return {
                "ok": True,
                "output": {"path": str(target), "bytes": len(content.encode("utf-8"))},
            }
        if action == "read":
            if not target.exists():
                return {"ok": False, "output": None, "error": f"file not found: {filename}"}
            content = target.read_text(encoding="utf-8", errors="replace")
            return {"ok": True, "output": {"filename": filename, "content": content[:2000]}}

        return {"ok": False, "output": None, "error": "action must be 'write' or 'read'"}