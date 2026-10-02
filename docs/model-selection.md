# Model selection: balancing cost, accuracy and speed

> **Read this first.** All accuracy figures below are *simulated against designer-set labels* and all prices/speeds are
> *illustrative assumptions* (`src/sunsetiq/jev_layer/models.py`). The "Jev" in these tables is a deterministic
> hand-written mock, **not** TypeSafe's model. These numbers evaluate the routing *design*; they say nothing about
> real Jev accuracy, which this repo does not measure.

## The three-way trade-off
Cost, accuracy and speed pull in different directions. The cheapest tier is fast and almost free but fails hard tasks; the
frontier tier is accurate but ~350× the cost per task and ~6× the latency. Reasoning effort adds a second dial: more
reasoning tokens raise cost and latency and can rescue a task that sits one tier above the chosen model.

| Tier | Example model slug (illustrative) | $ in / out per M tokens | First token | Speed |
|---|---|---|---|---|
| nano | openai/gpt-5-nano | 0.05 / 0.40 | 250 ms | 200 tok/s |
| fast | google/gemini-3-flash | 0.50 / 3.00 | 300 ms | 160 tok/s |
| balanced | anthropic/claude-sonnet-5-5 | 3 / 15 | 450 ms | 90 tok/s |
| frontier | anthropic/claude-opus-5-5 | 15 / 75 | 700 ms | 55 tok/s |

## What the router does
1. **Floor by task type (rules before model):** classification nano; extraction/summaries fast; status packs, change
   requests, claim verification balanced; regulated work at least balanced.
2. **Ask the decision model** for tier probabilities and an effort score; escalate one tier if confidence is below 0.55.
3. **Apply include/exclude pools**; exclusions are never ignored, an include list matching nothing is ignored, a tier can be
   capped by the lists.
4. **Session stickiness** (cache-aware): keep a working model for a conversation that shares context; never share a model
   across independent tasks (see "flaws found").
5. **Fallback:** if the decision model fails, use the floor tier.

## Held-out results (24 tasks, 6 task types; 95% Wilson intervals)
| Profile | Accuracy | $ per 1,000 tasks | Mean latency |
|---|---|---|---|
| all frontier (medium effort) | 100% (86–100) | 61.00 | 11,912 ms |
| static rules, medium effort* | 79% (60–91) | 8.67 | 6,184 ms |
| **mock-Jev routed, with floors** | 71% (51–85) | 5.59 | 3,584 ms |
| static rules (floor tier, low effort) | 67% (47–82) | 5.27 | 3,296 ms |
| mock-Jev routed, no floors | 21% (9–40) | 1.51 | 2,391 ms |
| all nano | 13% (4–31) | 0.17 | 1,792 ms |

\*Added after the first held-out run, as a stronger baseline — not a tuning of the system.
The Jev profiles include the published decision overhead (~$0.000014 and ~210 ms per decision).

## How to read it
- **Floors are the biggest lever.** Removing them collapses accuracy from 71% to 21%: rules before models.
- **Jev-with-floors vs plain static rules is within noise** at n = 24 (one task). The mock never selected the frontier tier
  on held-out tasks, so every frontier-required task was missed. A mock that cannot recognise hard tasks cannot show the
  value a real decision model might add. **That is a test to run with a real key, not a claim to make now.**
- **The honest cost view is cost per correct answer**, not cost per call: nano is cheapest per call but worst per correct
  answer; all-frontier is most accurate but most expensive per correct answer.
- **At scale** (annual spend, held-out mix): 1M tasks costs ~$61,000 all-frontier, ~$8,700 static-medium, ~$5,600
  floors-routed, ~$5,300 static. Model spend is real but second-order against the programme's own £-scale savings.

## When to use a decision-model router, and when not to
| Situation | Use a router | Use static rules |
|---|---|---|
| Task difficulty varies widely within one task type | ✓ | |
| Task types map cleanly to tiers | | ✓ |
| You can tolerate a vendor dependency in the request path | ✓ (with fallback) | |
| Regulated or irreversible downstream use | floors + human review regardless | floors + human review regardless |
| Very new product (this one is weeks old) | pilot in shadow mode first | ✓ default |

## Re-running with the real thing
Implement `OpenRouterJevClient`'s `request_builder` and `transport` from TypeSafe's published docs, set it as the
`jev` argument in `evaluate()` and `run()`, and re-run `scripts/run_all_eval.py` on the same held-out set.
