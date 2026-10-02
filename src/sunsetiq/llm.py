"""LLM client interface. Same pattern as the earlier repos: a free deterministic mock for tests,
and a real client slot (US-headquartered vendors only) behind the same interface."""
from __future__ import annotations

from typing import Protocol


class LLMClient(Protocol):
    def complete(self, task_type: str, prompt: str, model: str, effort: str) -> str: ...


class MockLLMClient:
    """Deterministic, zero-cost. Produces templated text so pipelines and tests run offline."""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    def complete(self, task_type: str, prompt: str, model: str, effort: str) -> str:
        self.calls.append({"task_type": task_type, "model": model, "effort": effort, "chars": len(prompt)})
        head = prompt.strip().splitlines()[0][:80] if prompt.strip() else ""
        return f"[mock:{task_type}:{model}:{effort}] {head}"


class RealLLMClient:
    """Placeholder for a production client (OpenAI / Google / Anthropic SDK or a gateway).
    Intentionally not wired: this repo's numbers come from the mock; see docs/eval-report.md."""

    def complete(self, task_type: str, prompt: str, model: str, effort: str) -> str:
        raise NotImplementedError("Wire a US-headquartered vendor SDK or gateway here.")
