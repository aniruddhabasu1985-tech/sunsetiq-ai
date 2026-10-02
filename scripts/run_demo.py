"""One-command demo: prints the headline numbers quoted in the README (all from a real run)."""
import sys; sys.path.insert(0, "src"); sys.path.insert(0, "eval")
from collections import Counter
from datasets import GATE_HELDOUT, ROUTING_HELDOUT
from sunsetiq.benefits import LOOSE_V1, VERIFIED_V1, compute
from sunsetiq.gate_eval import evaluate_gate
from sunsetiq.jev_layer import MockJevClient
from sunsetiq.pipeline import run
from sunsetiq.roi import compute_roi
from sunsetiq.routing_eval import evaluate
from sunsetiq.sequencer import measure, plan_governed, plan_naive

s = run(); est = s["estate"]
n, g = s["metrics"]["naive"], s["metrics"]["governed"]
print(f"Estate: {len(est.apps)} apps, {len(est.edges)} dependency links, {len(est.retire_candidates())} retire candidates")
print("\n-- Plan comparison (same estate, same retirements) --")
print(f"{'':28}{'naive cost-first':>18}{'governed':>12}")
print(f"{'orphaned dependency links':28}{n.orphaned_links:>18}{g.orphaned_links:>12}")
print(f"{'rollbacks':28}{n.rollbacks:>18}{g.rollbacks:>12}")
print(f"{'change-freeze violations':28}{n.freeze_violations:>18}{g.freeze_violations:>12}")
print(f"{'waves (incl. rework)':28}{n.effective_waves:>18}{g.effective_waves:>12}")
for p in (plan_naive(est), plan_governed(est)):
    l, v = compute(est, p, LOOSE_V1), compute(est, p, VERIFIED_V1)
    print(f"  {p.name}: claimed {l.annual_run_rate/1e6:.2f}M run-rate | verified net year-one {v.net_year_one/1e6:.2f}M")
dec = Counter(d.status for d in s["decisions"])
print("\n-- Governance (every decommission needs a human) --", dict(dec))
print("audit chain intact:", s["audit"].verify()[0], f"({len(s['audit'].entries)} entries)")
print("\n-- Routing, held-out set (mock Jev; illustrative prices) --")
for k, r in evaluate(ROUTING_HELDOUT).items():
    print(f"  {k:28} acc {r.accuracy:>5.0%} [{r.ci95[0]:.0%}-{r.ci95[1]:.0%}]  ${r.cost_per_1000:>6.2f}/1k tasks  {r.mean_latency_ms:>6.0f} ms")
print("\n-- Evidence gate, held-out --", evaluate_gate(GATE_HELDOUT, MockJevClient())["summary"])
rev = dec["HUMAN_REVIEW_REQUIRED"] + dec["APPROVAL_PACK_READY"]
r = compute_roi(est, rev, s["ai_cost_usd"])
print(f"\n-- ROI (illustrative) -- benefit/cost {r.benefit_cost_ratio:.2f}x at 50% incident rate; break-even {r.break_even_incident_rate:.0%}")
