from ..llm.client import ChatResult, LLMClient


class Reviewer:
    """Produces the final, human-readable outcome and a reliability note."""

    def __init__(self, llm: LLMClient) -> None:
        self.llm = llm

    async def review(self, task: str, outcomes) -> str:
        lines = "\n".join(
            f"- step {o.step_id} ({o.tool}): {'ok' if o.ok else 'failed'}"
            for o in outcomes
        )
        if self.llm.provider == "stub":
            lines = "\n".join(
                f"{'- ok' if o.ok else '- FAILED'}: step {o.step_id} ({o.tool})"
                for o in outcomes
            )
            failed = [o for o in outcomes if not o.ok]
            verdict = (
                f"Executed {len(outcomes)} step(s) for '{task}'."
                if not failed
                else f"Executed {len(outcomes)} step(s) for '{task}'; "
                f"{len(failed)} step(s) failed and were surfaced as errors."
            )
            return f"{verdict}\n{lines}"
        result: ChatResult = await self.llm.complete_text(
            [
                {
                    "role": "system",
                    "content": (
                        "You are the Reviewer agent. Summarize the executed steps for "
                        "the original task in 2-3 clear sentences; call out anything "
                        "that failed or was denied."
                    ),
                },
                {
                    "role": "user",
                    "content": f"Task: {task}\nExecution log:\n{lines}",
                },
            ]
        )
        return result.text