"""Jev-backed model router with rules-over-model floors, include/exclude pools, session stickiness,
confidence-aware escalation, and OUR OWN fallback (the hosted Jev Router fails the request if the Jev
call times out; SunsetIQ degrades to a deterministic cheapest-eligible baseline instead)."""
from __future__ import annotations

from dataclasses import dataclass, field
from fnmatch import fnmatchcase

from ..audit import AuditLog
from .client import JevClient, JevError
from .models import CATALOG, TIERS, Model, cost_usd, latency_ms

# deterministic floor per task type: rules before models
TYPE_FLOOR = {"classify_evidence": "nano", "extract_dependencies": "fast", "summarise_impact": "fast",
              "draft_status_pack": "balanced", "draft_change_request": "balanced", "verify_claim": "balanced"}
TOKEN_PROFILE = {"classify_evidence": (500, 50), "extract_dependencies": (1200, 300),
                 "summarise_impact": (800, 250), "draft_status_pack": (1500, 600),
                 "draft_change_request": (1000, 500), "verify_claim": (900, 150)}
CONF_MIN = 0.55


class RoutingError(RuntimeError):
    pass


@dataclass
class RouteRequest:
    task_id: str
    task_type: str
    text: str
    session_id: str = "default"
    regulated: bool = False
    latency_budget_ms: float | None = None


@dataclass
class RouteDecision:
    task_id: str
    model: Model
    effort: str
    source: str                       # jev | fallback_static
    reasons: list[str] = field(default_factory=list)
    est_cost: float = 0.0
    est_latency_ms: float = 0.0
    cache_hit: bool = False


def _match(slug: str, patterns: list[str]) -> bool:
    return any(fnmatchcase(slug, p) for p in patterns)


class JevRouter:
    def __init__(self, jev: JevClient | None, catalog: list[Model] | None = None,
                 include: list[str] | None = None, exclude: list[str] | None = None,
                 audit: AuditLog | None = None, sticky: bool = True, use_floors: bool = True,
                 conf_min: float = CONF_MIN) -> None:
        self.jev, self.audit, self.sticky = jev, audit, sticky
        self.use_floors, self.conf_min = use_floors, conf_min
        pool = catalog or CATALOG
        if include and any(_match(m.slug, include) for m in pool):
            pool = [m for m in pool if _match(m.slug, include)]       # empty include match is ignored
        if exclude:
            pool = [m for m in pool if not _match(m.slug, exclude)]   # exclusions are never ignored
        if not pool:
            raise RoutingError("exclusion list removed every candidate model")
        self.pool = pool
        self.sessions: dict[str, Model] = {}

    def _best_at_or_below(self, tier: str) -> Model:
        idx = TIERS.index(tier)
        for t in reversed(TIERS[: idx + 1]):
            for m in self.pool:
                if m.tier == t:
                    return m
        raise RoutingError(f"no admitted model at or below tier '{tier}'")

    def _cheapest_at_or_above(self, tier: str) -> Model:
        idx = TIERS.index(tier)
        for t in TIERS[idx:]:
            for m in self.pool:
                if m.tier == t:
                    return m
        return self._best_at_or_below("frontier")   # lists capped the tier; use strongest available

    def route(self, req: RouteRequest) -> RouteDecision:
        floor = TYPE_FLOOR[req.task_type] if self.use_floors else "nano"
        if self.use_floors and req.regulated and TIERS.index(floor) < TIERS.index("balanced"):
            floor = "balanced"
        reasons = [f"floor={floor}"]
        effort_score, source = 0.0, "fallback_static"
        want = floor
        if self.jev is not None:
            try:
                r = self.jev.route(req.text, req.task_type)
                want, source, effort_score = r.tier, "jev", r.effort
                reasons.append(f"jev tier={r.tier} conf={r.confidence}")
                if r.confidence < self.conf_min and want != "frontier":
                    want = TIERS[TIERS.index(want) + 1]
                    reasons.append("low confidence: escalated one tier")
            except JevError as exc:
                reasons.append(f"jev failed ({exc}): static fallback")
        if TIERS.index(want) < TIERS.index(floor):
            want = floor
            reasons.append("floor applied over jev")
        model = self._cheapest_at_or_above(want)
        if TIERS.index(model.tier) < TIERS.index(want):
            reasons.append("tier capped by include/exclude lists")
        cached = False
        cur = self.sessions.get(req.session_id)
        if self.sticky and cur is not None and TIERS.index(cur.tier) >= TIERS.index(model.tier) \
                and TIERS.index(cur.tier) >= TIERS.index(floor):
            model, cached = cur, True
            reasons.append("sticky: kept session model (cache preserved)")
        self.sessions[req.session_id] = model
        effort = "none"
        if model.supports_effort:
            effort = "low" if effort_score < 0.34 else "medium" if effort_score < 0.67 else "high"
        in_tok, out_tok = TOKEN_PROFILE[req.task_type]
        if req.latency_budget_ms and latency_ms(model, out_tok, effort) > req.latency_budget_ms \
                and effort != "none":
            effort = "low"
            reasons.append("effort lowered to meet latency budget")
        d = RouteDecision(req.task_id, model, effort, source, reasons,
                          cost_usd(model, in_tok, out_tok, effort, cached),
                          latency_ms(model, out_tok, effort), cached)
        if self.audit:
            self.audit.append("jev_router", "route", task=req.task_id, model=model.slug, effort=effort,
                              source=source, reasons=reasons)
        return d
