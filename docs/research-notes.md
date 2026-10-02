# Research notes

All sources were read in October 2026. Claims are paraphrased, not quoted. **Evidence quality is labelled**: much of the
2026 material on the model-routing layer is vendor-published or secondary commentary on a product that is only weeks old.

## A. The problem: legacy application estates and decommissioning risk

| Finding (paraphrased) | Source | Evidence quality |
|---|---|---|
| Technical debt is estimated to absorb roughly a fifth to two-fifths of total IT spend (figure attributed to a Deloitte 2026 study, reported second-hand). | Software Improvement Group, "Cost of Technical Debt" — softwareimprovementgroup.com/blog/cost-of-technical-debt | Secondary; vendor blog quoting a study |
| The same page cites a peer-reviewed study (April 2026) reporting positive median returns from systematic architectural-debt remediation over 24 months. | same | Secondary; I did not read the study |
| Application rationalisation commonly uses a four-quadrant "TIME" model (Tolerate / Invest / Migrate / Eliminate) based on business value and technical fit. | Sparx Systems/Prolaborate guide; Quinnox explainer | Vendor blogs; the framework itself is widely used |
| The riskiest part of rationalisation programmes is decommissioning itself, especially where data-retention obligations and integration dependencies are overlooked. | Archon Data Store, "Application Portfolio Rationalization" | Vendor blog (sells archiving) — directionally plausible, self-interested |
| Duplicate and rarely used applications are a recurring source of waste; one vendor white paper claims three-quarters of organisations lose at least a tenth of IT budget to unnecessary spend. | SAP LeanIX white paper, "IT cost savings: a guide to application rationalization" | Vendor white paper; statistic not independently checked |
| Case-style claims of ~30% portfolio reduction exist but are anecdotal. | Enov8, "An Introduction to Application Rationalization" | Anecdotal; not used for any number in this repo |

**How this repo uses the above:** only to motivate the problem shape (duplicate platforms, hidden dependencies,
retention obligations, savings that are claimed before they are verified). **No percentage from these sources is used as a
parameter.** All costs, dependencies and renewal dates in the repo are synthetic.

## B. The decision-model layer: TypeSafe AI's Jev and the Jev Router

| Finding (paraphrased) | Source | Evidence quality |
|---|---|---|
| TypeSafe AI is a San Francisco company, founded 2024; it came out of stealth on 15 Sep 2026 with a $40M seed round (DCVC-led) and released Jev in early access. | Wikipedia "Jev (AI model)"; ai.engineer org page | Reasonable (multiple consistent secondary sources) |
| Jev is a "System One" decision model: it receives a state plus questions and returns typed answers (a choice, a score, a yes/no probability) with no free text. | OpenRouter Jev docs (openrouter.ai/docs/guides/community/jev); promptql.io explainer | Vendor docs + commentary |
| Published price: $0.042 per million input tokens, free output, ~0.21 s median latency, 32k context. | OpenRouter model page (openrouter.ai/typesafe/jev-1.13) | Marketplace listing (current as read) |
| `typesafe/jev-router` appeared on OpenRouter on 25 Sep 2026. It picks a model *and* reasoning effort per request, is cache-aware, keeps a working model for the session, and accepts include/exclude model lists. | OpenRouter docs (…/routing/routers/jev-router); OpenRouter announcement thread | Vendor/marketplace docs |
| Vendor-reported benchmark: on four agent benchmarks the Jev Router solved 237 of 423 tasks versus 130 for OpenRouter's Auto Router, and had the fastest median time-to-first-token on five benchmarks. | OpenRouter announcement thread (25 Sep 2026) | **Vendor-reported; not independently replicated** |
| Vendor-reported: a Jev call is 22×–805× cheaper and 10×–125× faster than LLM calls on their own cookbook workloads. | Spring AI blog (21 Sep 2026), citing TypeSafe's cookbook | **Vendor benchmark; independent write-up of their numbers** |
| Independent commentary notes that benchmark and cost figures come from the company, demos are simulator-based, and "System One" is the vendor's own category label. | MindStudio explainer | Commentary — the cautionary note this repo adopts |
| **Failure behaviour:** if the Jev call times out or returns invalid output, the hosted router fails the request rather than falling back to another router. | OpenRouter announcement thread | Vendor statement — drives our own-fallback design |
| An open-source router (`prismhq/jev-router`, on LiteLLM) runs a cheapest-eligible baseline when no key is set and falls back on failure. | github.com/prismhq/jev-router | Open-source README |
| Published cookbooks show Jev gating agent tool calls (safe runs, unsupported is refused, only ambiguous pauses for a human) and a cascade pattern (cheap model drafts, Jev verifies, only failures escalate). | OpenRouter docs: "Gate Agent Tool Calls with Jev"; "Cut LLM Cost with a Jev-Verified Cascade" | Vendor cookbooks — patterns, not proof |
| Data handling statements (zero data retention; attachments not sent to Jev) are the vendor's. | OpenRouter announcement thread | Vendor-stated; verify contractually before real use |

**How this repo uses the above:** (1) the *router* picks tier + effort per task, under rules-over-model floors and
our own fallback; (2) the *evidence gate* uses the typed yes/no-probability pattern with three bands (supported /
ambiguous → human / refused) and fails closed. **Jev is not called live anywhere in this repo.** A deterministic
`MockJevClient` stands in; the real adapter is an unverified skeleton (see `src/sunsetiq/jev_layer/client.py`). All claims about
Jev's real accuracy are the vendor's and are not repeated as findings here.

## C. Method references
- Lean Six Sigma **DMAIC** for the programme container; **Agile Scrum** for delivery; **ADKAR** for change management.
- Statistical method: **Wilson score intervals** for all small-sample accuracy figures.
