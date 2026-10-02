"""Rule-based decommission readiness score (0-100). Deterministic and explainable: no model call."""
from __future__ import annotations

from dataclasses import dataclass

import networkx as nx

from .data_gen import App, Estate
from .graph import direct_dependents, transitive_dependents

WEIGHTS = {
    "per_live_direct_dependent": 3.0, "direct_cap": 30.0,
    "per_indirect_dependent": 1.0, "indirect_cap": 15.0,
    "per_criticality_point_above_1": 6.0,
    "regulated_data": 10.0,
    "users_per_point": 300.0, "users_cap": 10.0,
}
READY, CONDITIONAL = 70, 40


@dataclass
class Readiness:
    app_id: str
    score: float
    band: str
    factors: dict[str, float]


def score_app(estate: Estate, g: nx.DiGraph, app: App) -> Readiness:
    w = WEIGHTS
    direct = direct_dependents(g, app.app_id)
    indirect = transitive_dependents(g, app.app_id) - set(direct)
    f = {
        "direct_dependents": min(w["direct_cap"], w["per_live_direct_dependent"] * len(direct)),
        "indirect_dependents": min(w["indirect_cap"], w["per_indirect_dependent"] * len(indirect)),
        "criticality": w["per_criticality_point_above_1"] * (app.criticality - 1),
        "regulated_data": w["regulated_data"] if app.regulated_data else 0.0,
        "user_footprint": min(w["users_cap"], app.users / w["users_per_point"]),
    }
    score = max(0.0, 100.0 - sum(f.values()))
    band = "ready" if score >= READY else "conditional" if score >= CONDITIONAL else "blocked"
    return Readiness(app.app_id, round(score, 1), band, {k: round(v, 1) for k, v in f.items()})


def score_all(estate: Estate, g: nx.DiGraph) -> dict[str, Readiness]:
    return {a.app_id: score_app(estate, g, a) for a in estate.retire_candidates()}
