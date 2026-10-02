"""ROI model. Every input is labelled Given / Calculated / Assumed; formulas are shown, not just results.

Framing: VALUE OF GOVERNANCE (loss avoided vs a naive plan, net of what governance costs), not a promise of
savings. The naive plan is the counterfactual. `incident_rate` is the single biggest assumption."""
from __future__ import annotations

from dataclasses import dataclass, field

from .benefits import COST_PER_EFFORT_POINT
from .data_gen import Estate
from .sequencer import measure, plan_governed, plan_naive, renewal_lower_bound

ASSUMED = {
    "incident_rate": 0.5,              # share of critical-orphan events that really force a rollback
    "cost_per_effort_point": COST_PER_EFFORT_POINT,
    "platform_build_cost": 450_000,
    "platform_annual_run": 120_000,
    "review_hours_per_decision": 2.0,
    "review_rate_per_hour": 60.0,
}


@dataclass
class Line:
    name: str
    value: float
    label: str          # Given | Calculated | Assumed
    formula: str = ""


@dataclass
class RoiResult:
    lines: list[Line] = field(default_factory=list)
    avoided_loss: float = 0.0
    governance_cost: float = 0.0
    net_benefit: float = 0.0
    benefit_cost_ratio: float = 0.0
    break_even_incident_rate: float = 0.0

    def get(self, name: str) -> float:
        return next(l.value for l in self.lines if l.name == name)


def compute_roi(estate: Estate, review_decisions: int, ai_cost_usd: float, **over) -> RoiResult:
    a = {**ASSUMED, **over}
    n, g = measure(estate, plan_naive(estate)), measure(estate, plan_governed(estate))
    at_risk = n.claimed_saving - n.net_of_rollbacks
    rework_cost = n.rework_effort * a["cost_per_effort_point"]
    extra_renewal = max(0, g.renewal_penalty - n.renewal_penalty)
    review_cost = review_decisions * a["review_hours_per_decision"] * a["review_rate_per_hour"]
    r = RoiResult()
    L = r.lines.append
    L(Line("naive_claimed_run_rate", n.claimed_saving, "Calculated", "sum of annual saving of retired apps"))
    L(Line("naive_savings_at_risk", at_risk, "Calculated", "claimed - net_of_rollbacks (naive plan)"))
    L(Line("naive_rework_effort_points", n.rework_effort, "Calculated", "2x emergency rewires + wasted decom effort"))
    L(Line("naive_rework_cost", rework_cost, "Calculated", "rework points x cost_per_effort_point"))
    L(Line("governed_extra_renewal_cost", extra_renewal, "Calculated",
           "governed renewal penalty - naive renewal penalty (conservative: naive ignores rework delay)"))
    L(Line("structural_renewal_floor", renewal_lower_bound(estate), "Calculated", "unavoidable under ANY plan"))
    L(Line("incident_rate", a["incident_rate"], "Assumed", "share of critical orphans causing a rollback"))
    L(Line("cost_per_effort_point", a["cost_per_effort_point"], "Assumed"))
    L(Line("platform_build_cost", a["platform_build_cost"], "Assumed"))
    L(Line("platform_annual_run", a["platform_annual_run"], "Assumed"))
    L(Line("human_review_cost", review_cost, "Calculated", "decisions x hours x rate (hours, rate Assumed)"))
    L(Line("ai_layer_cost_usd", ai_cost_usd, "Calculated", "pipeline run, illustrative prices; 1 unit = 1 USD (Assumed)"))
    r.avoided_loss = a["incident_rate"] * (at_risk + rework_cost)
    r.governance_cost = (extra_renewal + a["platform_build_cost"] + a["platform_annual_run"]
                         + review_cost + ai_cost_usd)
    r.net_benefit = r.avoided_loss - r.governance_cost
    r.benefit_cost_ratio = r.avoided_loss / r.governance_cost if r.governance_cost else float("inf")
    r.break_even_incident_rate = r.governance_cost / (at_risk + rework_cost) if (at_risk + rework_cost) else float("inf")
    return r


def sensitivity(estate: Estate, review_decisions: int, ai_cost_usd: float) -> dict[str, list]:
    out = {"incident_rate": [], "cost_per_effort_point": []}
    for ir in (0.1, 0.25, 0.5, 0.75, 1.0):
        r = compute_roi(estate, review_decisions, ai_cost_usd, incident_rate=ir)
        out["incident_rate"].append((ir, round(r.net_benefit), round(r.benefit_cost_ratio, 2)))
    for c in (1_000, 2_500, 5_000, 10_000):
        r = compute_roi(estate, review_decisions, ai_cost_usd, cost_per_effort_point=c)
        out["cost_per_effort_point"].append((c, round(r.net_benefit), round(r.benefit_cost_ratio, 2)))
    return out


def ai_spend_at_scale(per_1000: dict[str, float], volumes=(138, 10_000, 1_000_000)) -> dict[str, dict[int, float]]:
    """Annual model spend by routing profile at different task volumes (from per-1,000-task costs)."""
    return {p: {v: round(c * v / 1000, 2) for v in volumes} for p, c in per_1000.items()}
