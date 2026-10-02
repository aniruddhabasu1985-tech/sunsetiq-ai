"""Reproduce every number quoted in docs/README. Writes eval/results/results.json."""
import json, sys; sys.path.insert(0, "src"); sys.path.insert(0, "eval")
from collections import Counter
from dataclasses import asdict
from datasets import GATE_HELDOUT, ROUTING_DEV, ROUTING_HELDOUT
from sunsetiq.benefits import LOOSE_V1, VERIFIED_V1, compute
from sunsetiq.gate_eval import evaluate_gate
from sunsetiq.jev_layer import MockJevClient
from sunsetiq.pipeline import run
from sunsetiq.roi import ai_spend_at_scale, compute_roi, sensitivity
from sunsetiq.routing_eval import evaluate
from sunsetiq.sequencer import measure, plan_governed, plan_naive, renewal_lower_bound

s = run(); est = s["estate"]
dec = Counter(d.status for d in s["decisions"])
review = dec["HUMAN_REVIEW_REQUIRED"] + dec["APPROVAL_PACK_READY"]
roi = compute_roi(est, review, s["ai_cost_usd"])
held = evaluate(ROUTING_HELDOUT)
out = {
    "plans": {k: {kk: vv for kk, vv in asdict(m).items() if kk != "saving_by_wave"} for k, m in s["metrics"].items()},
    "benefits": {f"{p.name}/{d.name}": asdict(compute(est, p, d))
                 for p in (plan_naive(est), plan_governed(est)) for d in (LOOSE_V1, VERIFIED_V1)},
    "renewal_structural_floor": renewal_lower_bound(est),
    "governance_decisions": dict(dec),
    "ai_layer_cost_usd": round(s["ai_cost_usd"], 4),
    "routing_dev": {k: asdict(v) for k, v in evaluate(ROUTING_DEV).items()},
    "routing_heldout": {k: asdict(v) for k, v in held.items()},
    "gate_heldout": evaluate_gate(GATE_HELDOUT, MockJevClient())["summary"],
    "roi": {"lines": [asdict(l) for l in roi.lines], "avoided_loss": round(roi.avoided_loss),
            "governance_cost": round(roi.governance_cost), "net_benefit": round(roi.net_benefit),
            "bcr": round(roi.benefit_cost_ratio, 2), "break_even_incident_rate": round(roi.break_even_incident_rate, 3)},
    "roi_sensitivity": sensitivity(est, review, s["ai_cost_usd"]),
    "ai_spend_at_scale": ai_spend_at_scale({k: v.cost_per_1000 for k, v in held.items()}),
}
json.dump(out, open("eval/results/results.json", "w"), indent=1, default=str)
print("wrote eval/results/results.json;", "gate:", out["gate_heldout"], "| ROI BCR", out["roi"]["bcr"],
      "break-even", out["roi"]["break_even_incident_rate"])
