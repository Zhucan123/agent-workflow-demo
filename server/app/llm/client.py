import json
import re
import time
from dataclasses import dataclass

import httpx

from .. import config

# Rough USD-estimates per 1M tokens (input, output); used for token.usage events.
MODEL_COST_PER_1M = {
    "gpt-4o-mini": (0.15, 0.60),
    "deepseek-chat": (0.27, 1.10),
    "qwen-plus": (0.40, 1.20),
}


@dataclass
class ChatResult:
    text: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost_estimate: float = 0.0


class LLMClient:
    """OpenAI-compatible chat client with a deterministic stub mode.

    Stub mode (no API key) returns canned, schema-valid responses so the
    whole pipeline is testable and demo-able offline.
    """

    def __init__(self, mode: str | None = None) -> None:
        self.mode = mode or config.LLM_MODE
        if self.mode == "auto":
            self.mode = "openai" if config.OPENAI_API_KEY else "stub"

    @property
    def provider(self) -> str:
        return self.mode

    async def complete_json(self, messages: list[dict], temperature: float = 0.2) -> dict:
        if self.mode == "stub":
            return self._stub_json(messages)
        result = await self._openai(messages, temperature, json_mode=True)
        return _safe_json(result.text)

    async def complete_text(self, messages: list[dict], temperature: float = 0.4) -> ChatResult:
        if self.mode == "stub":
            return ChatResult(text=self._stub_text(messages))
        return await self._openai(messages, temperature, json_mode=False)

    async def _openai(self, messages: list[dict], temperature: float, json_mode: bool) -> ChatResult:
        url = config.OPENAI_BASE_URL.rstrip("/") + "/chat/completions"
        payload = {
            "model": config.MODEL,
            "messages": messages,
            "temperature": temperature,
            "stream": False,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        async with httpx.AsyncClient(timeout=config.STEP_TIMEOUT_S) as client:
            resp = await client.post(
                url,
                json=payload,
                headers={"Authorization": f"Bearer {config.OPENAI_API_KEY}"},
            )
            resp.raise_for_status()
        body = resp.json()
        choice = body["choices"][0]["message"]["content"]
        usage = body.get("usage") or {}
        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)
        cost = _estimate_cost(config.MODEL, prompt_tokens, completion_tokens)
        return ChatResult(
            text=choice,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost_estimate=cost,
        )

    # ---------------- stub mode ----------------

    @staticmethod
    def _role(messages: list[dict]) -> str:
        for msg in reversed(messages):
            if msg.get("role") == "system":
                sig = (msg.get("content") or "").lower()
                if "planner" in sig:
                    return "plan"
                if "reviewer" in sig:
                    return "review"
        return "chat"

    def _stub_json(self, messages: list[dict]) -> dict:
        role = self._role(messages)
        task = _last_user_text(messages)
        if role == "plan":
            raise NotImplementedError("planning is shaped in planner.py (stub)")
        return {"reply": self._stub_text(messages)}

    def _stub_text(self, messages: list[dict]) -> str:
        role = self._role(messages)
        task = _last_user_text(messages)
        if role == "review":
            return "Stub review: task executed successfully with verified tool outputs."
        return f"[stub] simulated reply for: {task[:120]}"


def _safe_json(raw: str) -> dict:
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        raise ValueError(f"no JSON object in LLM output: {raw[:200]}")
    return json.loads(match.group(0))


def _last_user_text(messages: list[dict]) -> str:
    for msg in reversed(messages):
        if msg.get("role") == "user":
            return msg.get("content") or ""
    return ""


def _estimate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    in_cost, out_cost = MODEL_COST_PER_1M.get(model, (0.5, 1.5))
    return round((prompt_tokens * in_cost + completion_tokens * out_cost) / 1_000_000, 6)