import time
from datetime import datetime, timezone
from typing import Any

from .registry import Tool


class TimeNowTool(Tool):
    name = "time.now"
    description = 'Return the current UTC timestamp. Args: {}. Deterministic, safe to call anytime.'

    async def run(self, args: dict[str, Any], ctx) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        return {
            "ok": True,
            "output": {
                "iso": now.isoformat(),
                "utc_epoch": int(time.time()),
            },
        }