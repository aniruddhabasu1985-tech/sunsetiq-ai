import sys; sys.path.insert(0, "src"); sys.path.insert(0, "eval")
from datasets import ROUTING_DEV, ROUTING_HELDOUT
from sunsetiq.routing_eval import evaluate

for name, ds in (("DEV", ROUTING_DEV), ("HELD-OUT", ROUTING_HELDOUT)):
    print(f"\n=== {name} (n={len(ds)}) ===")
    res = evaluate(ds)
    print(f"{'profile':27} {'acc':>6} {'$/1k':>9} {'$/correct':>10} {'mean ms':>8} {'p95 ms':>8}  tiers")
    for r in res.values():
        print(f"{r.profile:27} {r.accuracy:>6.1%} [{r.ci95[0]:.0%}-{r.ci95[1]:.0%}] {r.cost_per_1000:>9.2f} {r.cost_per_correct:>10.5f} "
              f"{r.mean_latency_ms:>8.0f} {r.p95_latency_ms:>8.0f}  {r.tier_mix}")
    
