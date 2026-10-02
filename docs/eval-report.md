# Evaluation report

Reproduce everything: `python -m pytest -q tests` (69 tests) and `python scripts/run_all_eval.py` (writes `eval/results/results.json`).
Single seeded run (seed 7). Currency and prices illustrative; model behaviour is mocked.

## 1. Plans: naive vs governed
| | Naive (cost-first) | Governed |
|---|---|---|
| Waves | 14 on paper → **30** counting rework | 21 |
| Orphaned dependency links (critical) | 108 (49) | 0 (0) |
| Rollbacks | 42 | 0 |
| Change-freeze violations | 4 | 0 |
| Claimed annual run-rate | 34.95M | 34.95M |
| Verified net year-one (`verified_v1`) | 2.49M | 19.35M |
| Licence renewals missed | 5.17M | 13.14M |

**Governed is slower to first savings and misses more renewals** — reported, not patched. Zero violations for the governed plan
is a *design guarantee*, confirmed by the independent validator across seeds 1, 2, 3, 7, 11, 42 — not an empirical discovery.

## 2. Governance decisions (93 retirement decisions)
24 approval-pack-ready · 35 human review · 34 blocked. Every decision lists the Change Authority Board as approver. The audit chain (235 entries) verifies.

## 3. Evidence gate — held-out (22 packs, varied phrasing; written after the logic was frozen)
- **0 false approvals** of 14 unsupported packs (partial, contradictory, injected, missing, ambiguous).
- **0 true approvals** of 8 genuinely supported packs: all 8 went to a human (ambiguous band). **It fails safe but approves nothing.**
- The 52/52 "correct" figure on the repo's own templates is a self-written test and is **not** quoted as accuracy.
- Cause: the mock's keyword cues do not match paraphrases. A real decision model is expected to do better; unmeasured here.

## 4. Routing — held-out (24 tasks)
See `docs/model-selection.md`. Headline: floors dominate (71% vs 21% without); mock-Jev-with-floors ≈ static rules within noise
(n = 24); the mock never selected frontier. Dev-set results (n = 24) were similar in shape (jev_with_floors 88%, static 67%).

## 5. Benefits definitions
`loose_v1` counts every retirement; `verified_v1` excludes retirements that left orphans or were rolled back and nets cost to
achieve and missed-renewal licence. The tracker refuses to compare figures across definition hashes.

## 6. Flaws found during the build (documented, not hidden)
1. **Session stickiness locked 93 independent tasks onto one model.** Stickiness is only valid for requests sharing cacheable
   context. Fixed by keying sessions per task; regression test added.
2. **"14 waves" understated the naive plan** by ignoring the rework it would force; added `effective_waves` (30).
3. **Two different "verified" figures existed** (rollbacks-only vs strict). Renamed the planner metric `net_of_rollbacks` and made the
   benefits tracker the single authority.
4. **Evidence gate looked perfect on its own templates** (52/52) and approved nothing on paraphrases (0/8). Reported as the finding.
5. **Renewal penalty looked like a capacity problem; it is mostly structural and policy-driven.** Added `renewal_lower_bound`
   (tested to be a true floor) and a decomposition.

## 7. Limitations
- Synthetic data; one seed for headline figures. 24-task routing sets give wide intervals.
- Accuracy is simulated against designer labels, not measured on real model output.
- The Jev client is a mock; the real adapter is unverified against the live endpoint.
- Incident rate, effort cost, platform cost, review hours and all prices are assumptions.
- No real-estate validation; no claim about any real organisation.
