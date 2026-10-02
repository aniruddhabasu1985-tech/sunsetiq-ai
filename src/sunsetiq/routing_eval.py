"""Routing evaluation: cost vs accuracy vs speed across routing profiles.

ACCURACY IS SIMULATED against designer-set `required_tier` labels (a model answers correctly iff its tier
meets the requirement, or is one tier short with effort_helps and medium/high effort). It measures the
ROUTING DESIGN, not any real model's output quality. Prices/speeds are illustrative (see models.py)."""
from __future__ import annotations

import math
import statistics
from dataclasses import dataclass

from .jev_layer import CATALOG, JevRouter, MockJevClient, RouteRequest, TIERS
from .jev_layer.models import cost_usd, latency_ms
from .jev_layer.router import TOKEN_PROFILE, TYPE_FLOOR

JEV_DECISION_COST = 340 * 0.042 / 1e6      # ~340 input tokens at $0.042/M (published Jev price)
JEV_DECISION_MS = 210.0                    # published P50 latency


def _by_tier(tier):
    return next(m for m in CATALOG if m.tier == tier)


def is_correct(model, effort, required, effort_helps) -> bool:
    gap = TIERS.index(required) - TIERS.index(model.tier)
    if gap <= 0:
        return True
    return gap == 1 and effort_helps and effort in ("medium", "high") and model.supports_effort


@dataclass
class ProfileResult:
    profile: str
    n: int
    accuracy: float
    cost_per_1000: float
    cost_per_correct: float
    mean_latency_ms: float
    p95_latency_ms: float
    tier_mix: dict[str, int]
    failures: list[str]
    ci95: tuple[float, float] = (0.0, 1.0)


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return 0.0, 1.0
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return round(max(0.0, c - h), 3), round(min(1.0, c + h), 3)


def _run(profile: str, tasks, picker) -> ProfileResult:
    cost = lat = 0.0
    lats, correct, mix, fails = [], 0, {t: 0 for t in TIERS}, []
    for i, (ttype, req, helps, text) in enumerate(tasks):
        model, effort, extra_cost, extra_ms = picker(i, ttype, text)
        in_t, out_t = TOKEN_PROFILE[ttype]
        c = cost_usd(model, in_t, out_t, effort) + extra_cost
        l = latency_ms(model, out_t, effort) + extra_ms
        ok = is_correct(model, effort, req, helps)
        correct += ok
        cost += c
        lats.append(l)
        mix[model.tier] += 1
        if not ok:
            fails.append(f"{ttype}: needed {req}, got {model.tier}/{effort}")
    n = len(tasks)
    lats.sort()
    return ProfileResult(profile, n, round(correct / n, 3), round(cost / n * 1000, 2),
                         round(cost / max(1, correct), 5), round(statistics.mean(lats), 0),
                         round(lats[int(0.95 * (n - 1))], 0), mix, fails, wilson(correct, n))


def evaluate(tasks, conf_min: float = 0.55) -> dict[str, ProfileResult]:
    frontier, nano = _by_tier("frontier"), _by_tier("nano")

    def all_frontier(i, t, x): return frontier, "medium", 0.0, 0.0
    def all_nano(i, t, x): return nano, "none", 0.0, 0.0
    def static_rules(i, t, x):
        m = _by_tier(TYPE_FLOOR[t]); return m, "low" if m.supports_effort else "none", 0.0, 0.0

    def static_medium(i, t, x):
        m = _by_tier(TYPE_FLOOR[t]); return m, "medium" if m.supports_effort else "none", 0.0, 0.0

    def jev_factory(use_floors):
        router = JevRouter(MockJevClient(), sticky=False, use_floors=use_floors, conf_min=conf_min)
        def pick(i, t, x):
            d = router.route(RouteRequest(f"t{i}", t, x, session_id=f"s{i}"))
            return d.model, d.effort, JEV_DECISION_COST, JEV_DECISION_MS
        return pick

    return {
        "all_frontier": _run("all_frontier", tasks, all_frontier),
        "all_nano": _run("all_nano", tasks, all_nano),
        "static_rules": _run("static_rules", tasks, static_rules),
        "static_rules_medium_effort": _run("static_rules_medium_effort", tasks, static_medium),  # added after first held-out run
        "jev_pure_no_floors": _run("jev_pure_no_floors", tasks, jev_factory(False)),
        "jev_with_floors": _run("jev_with_floors", tasks, jev_factory(True)),
    }
