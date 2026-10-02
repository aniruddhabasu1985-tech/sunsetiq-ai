# ROI model

**Framing: value of governance, not a promise of savings.** The counterfactual is the naive "most expensive first" plan.
Currency is illustrative; 1 unit = 1 USD for the small model-spend lines (Assumed). Reproduce with `python scripts/run_all_eval.py`.

## Inputs (labelled)
| Input | Value | Label | Formula / note |
|---|---|---|---|
| Naive plan claimed run-rate | 34,950,000 | Calculated | sum of annual saving of retired apps |
| Naive savings at risk | 15,685,000 | Calculated | claimed − net-of-rollbacks (naive) |
| Naive rework effort | 1,005 points | Calculated | 2× emergency rewires + wasted decommission effort |
| Cost per effort point | 2,500 | **Assumed** | |
| Naive rework cost | 2,512,500 | Calculated | rework points × cost per point |
| Governed extra renewal cost | 7,963,000 | Calculated | governed renewal penalty − naive renewal penalty |
| Structural renewal floor | 3,395,000 | Calculated | unavoidable under *any* plan |
| Incident rate | 0.50 | **Assumed** | share of critical orphan events that force a rollback |
| Platform build cost | 450,000 | **Assumed** | |
| Platform annual run | 120,000 | **Assumed** | |
| Human review cost | 7,080 | Calculated | 59 decisions × 2 h × 60/h (hours, rate Assumed) |
| AI layer cost | 0.65 | Calculated | pipeline run, illustrative prices |

## Formulas
```
avoided_loss    = incident_rate × (naive_savings_at_risk + naive_rework_cost)
                = 0.5 × (15,685,000 + 2,512,500) = 9,098,750
governance_cost = governed_extra_renewal + build + annual_run + review + AI
                = 7,963,000 + 450,000 + 120,000 + 7,080 + 0.65 ≈ 8,540,081
net_benefit     = avoided_loss − governance_cost = 558,669
benefit/cost    = 9,098,750 / 8,540,081 = 1.07
break_even_incident_rate = governance_cost / (at_risk + rework_cost) = 0.469
```

## Sensitivity (the two inputs that move the answer)
| Incident rate | Net benefit | Benefit/cost |
|---|---|---|
| 10% | −6,720,331 | 0.21 |
| 25% | −3,990,706 | 0.53 |
| **50% (base)** | **+558,669** | **1.07** |
| 75% | +5,108,044 | 1.60 |
| 100% | +9,657,419 | 2.13 |

| Cost per effort point | Net benefit | Benefit/cost |
|---|---|---|
| 1,000 | −195,081 | 0.98 |
| **2,500 (base)** | **+558,669** | **1.07** |
| 5,000 | +1,814,919 | 1.21 |
| 10,000 | +4,327,419 | 1.51 |

## What this says — and doesn't
- **Marginal at base assumptions; strongly dependent on how often a critical orphan really causes a rollback.** Below
  ~47% governance loses money *on this synthetic estate*. The model does not know the real rate.
- **The dominant cost is not the tooling** (~570k build and first-year run) **but renewals missed because governance takes longer**
  (7.96M more than naive). That is the honest price of safety.
- **Where the renewal misses come from (seed 7):** ~3.4M is structural (dependency-chain depth alone), ~6.3M comes from
  governance rules (change-freeze waves and the cap on critical decommissions), ~3.4M from capacity. Doubling capacity cut the
  total by ~19% on seed 7 and ~38% on seed 11, and re-weighting urgency barely moved it — **the main lever is commercial as much as computational:** negotiate short
  renewal extensions for apps on long dependency chains.
- **Conservative bias:** the naive plan's renewal penalty ignores the delay caused by its own rework, which understates
  governance's value.
- **Model spend is second-order:** a full pipeline run costs ~$0.65; routing matters at volume (see model-selection.md), not
  for this programme's headline.
