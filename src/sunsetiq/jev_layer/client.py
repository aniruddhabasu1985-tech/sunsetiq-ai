"""Jev decision-model clients.

Jev (TypeSafe AI) is a *decision* model: it returns typed answers (a choice, a score, a yes/no
probability) rather than text. This module defines the interface SunsetIQ needs and two clients:

* MockJevClient  - deterministic, free, offline. It is a hand-written heuristic that MIMICS the
  interface. Numbers produced with it measure the DESIGN, not Jev's real accuracy.
* OpenRouterJevClient - adapter skeleton for the hosted model. NOT verified against the live
  endpoint: the request schema must be taken from TypeSafe's published docs/agent skill and
  injected via `request_builder` / `transport`. It raises JevError until both are supplied.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Callable, Protocol

TIER_ORDER = ["nano", "fast", "balanced", "frontier"]


class JevError(RuntimeError):
    """Timeout, invalid output, or unavailable decision model."""


@dataclass
class JevRoute:
    tier_probs: dict[str, float]
    effort: float            # 0..1: how much extra reasoning would help
    confidence: float        # probability mass of the winning tier
    latency_ms: float = 210.0

    @property
    def tier(self) -> str:
        return max(self.tier_probs, key=self.tier_probs.get)


class JevClient(Protocol):
    def route(self, text: str, task_type: str) -> JevRoute: ...
    def judge(self, state: str, statement: str) -> float: ...


_HARD = ["reconcile", "contradict", "regulat", "legal", "conflict", "ambiguous", "multi-step", "trade-off",
         "audit", "dependency chain", "cut-over", "retention", "sign-off"]
_EASY = ["list", "format", "tag", "label", "simple", "summarise in one line", "classify"]


class MockJevClient:
    def __init__(self, fail_every: int = 0, latency_ms: float = 210.0) -> None:
        self.fail_every, self.latency_ms, self.calls = fail_every, latency_ms, 0

    # -- routing ------------------------------------------------------------------------------
    def route(self, text: str, task_type: str) -> JevRoute:
        self.calls += 1
        if self.fail_every and self.calls % self.fail_every == 0:
            raise JevError("simulated timeout")
        low = text.lower()
        words = len(low.split())
        hard = sum(k in low for k in _HARD)
        easy = sum(k in low for k in _EASY)
        difficulty = min(1.0, 0.15 + 0.12 * hard + min(words, 400) / 1200 - 0.10 * easy)
        centres = {"nano": 0.1, "fast": 0.35, "balanced": 0.6, "frontier": 0.9}
        logits = {t: -((difficulty - c) ** 2) * 14 for t, c in centres.items()}
        z = sum(math.exp(v) for v in logits.values())
        probs = {t: math.exp(v) / z for t, v in logits.items()}
        top = max(probs.values())
        return JevRoute(probs, round(min(1.0, difficulty * 1.1), 3), round(top, 3), self.latency_ms)

    # -- judging evidence ---------------------------------------------------------------------
    def judge(self, state: str, statement: str) -> float:
        self.calls += 1
        if self.fail_every and self.calls % self.fail_every == 0:
            raise JevError("simulated timeout")
        low = state.lower()
        cues = {
            "consumers_migrated": (["all consumers have been migrated", "all consumers migrated",
                                    "migration verified", "cutover complete"],
                                   ["pending cutover", "still live", "still reading", "not yet migrated",
                                    "some consumers", "most consumers"]),
            "retention_covered": (["retention schedule confirmed", "archived per retention", "data archived"],
                                  ["retention not confirmed", "to be confirmed", "retention pending"]),
            "owner_signoff": (["sign-off recorded", "owner confirmed", "owner confirmation"],
                              ["no sign-off", "awaiting owner", "no evidence"]),
        }
        pos, neg = cues[statement]
        p = 0.5 + 0.22 * sum(c in low for c in pos) - 0.30 * sum(c in low for c in neg)
        if "no evidence" in low:
            p = 0.02
        return round(min(0.99, max(0.01, p)), 3)


class OpenRouterJevClient:
    """Adapter skeleton. See module docstring: unverified against the live endpoint."""

    MODEL = "typesafe/jev-1.13"

    def __init__(self, transport: Callable[[dict], dict] | None = None,
                 request_builder: Callable[..., dict] | None = None) -> None:
        self.transport, self.request_builder = transport, request_builder

    def _call(self, **kw) -> dict:
        if not (self.transport and self.request_builder):
            raise JevError("OpenRouterJevClient needs transport + request_builder built from TypeSafe's docs")
        try:
            return self.transport(self.request_builder(model=self.MODEL, **kw))
        except Exception as exc:  # network, timeout, schema
            raise JevError(str(exc)) from exc

    def route(self, text: str, task_type: str) -> JevRoute:
        out = self._call(kind="route", text=text, task_type=task_type)
        try:
            probs = {t: float(out["tier_probs"][t]) for t in TIER_ORDER}
            return JevRoute(probs, float(out["effort"]), max(probs.values()))
        except (KeyError, TypeError, ValueError) as exc:
            raise JevError("invalid Jev output") from exc

    def judge(self, state: str, statement: str) -> float:
        out = self._call(kind="judge", state=state, statement=statement)
        try:
            return float(out["probability"])
        except (KeyError, TypeError, ValueError) as exc:
            raise JevError("invalid Jev output") from exc
