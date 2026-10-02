# Project charter (DMAIC — Define)

**Project:** SunsetIQ — governed legacy-application retirement planning
**Type:** Portfolio project on synthetic, fully anonymized data. No real organisation, client or system is modelled.

## Problem statement
Large operators accumulate parallel platforms for billing, CRM, order management and middleware across business units.
Retiring them is where the savings are, and also where the damage is: an application retired before its consumers have
moved breaks something, the "saving" is reversed, and the programme report still shows it as delivered. Programmes need
a way to (a) sequence retirements so that nothing is orphaned, (b) keep humans accountable for every irreversible step,
and (c) report savings under a definition that cannot quietly change.

## Goal and scope
Plan the retirement of a synthetic estate of 200 applications (93 retire candidates, 276 dependency links) with zero
orphaned dependencies, human approval on every decommission, and savings reported as *claimed* versus *verified*.
**In scope:** planning, governance, evidence checking, benefit tracking, model routing. **Out of scope:** executing any change.

## Success criteria (CTQs)
| CTQ | Measure | Target |
|---|---|---|
| No unplanned breakage | orphaned dependency links in the plan | 0 (independently validated) |
| Human accountability | decommission decisions executed without a named human approver | 0 — enforced in code |
| Honest benefits | difference between claimed and verified figures is visible and attributable | definitions hashed and versioned |
| Safe evidence handling | unsupported evidence reaching "approval pack ready" | 0 false approvals on held-out set |
| Proportionate AI spend | accuracy per dollar by routing profile | reported with confidence intervals |
| Renewal protection | licence renewals missed | reported, split into structural vs policy vs capacity |

## SIPOC
| Supplier | Input | Process | Output | Customer |
|---|---|---|---|---|
| Enterprise architecture | Application inventory, dependency register | Map → score → sequence → validate | Wave plan with rewire and decommission tasks | Programme sponsor |
| Service owners | Evidence packs (free text) | Redact, screen, judge, apply policy | Decision per app + approver list | Change Authority Board |
| Finance | Licence, run cost, renewal dates | Benefits tracker under versioned definition | Claimed vs verified savings | Programme sponsor, Finance |
| Platform engineering | Model catalogue, prices | Route tasks to tier + effort | Drafts (change requests, status) at known cost | Transformation Manager |

## Stakeholders and RACI
R = Responsible, A = Accountable, C = Consulted, I = Informed.

| Activity | Programme sponsor | Transformation Manager | Enterprise architecture | Service owners | Change Authority Board | Data Protection Officer | Finance | Platform engineering |
|---|---|---|---|---|---|---|---|---|
| Approve retirement wave plan | A | R | C | C | I | I | C | I |
| Maintain dependency data | I | C | A/R | R | I | I | I | C |
| Provide decommission evidence | I | C | C | A/R | I | C | I | I |
| Approve each decommission (L4) | I | C | C | C | **A/R** | C (if regulated) | I | I |
| Retention sign-off | I | I | C | R | C | **A** | I | I |
| Define savings definition | C | R | I | I | I | I | **A** | I |
| Operate the platform and model layer | I | C | C | I | I | I | I | **A/R** |

## RAID log
| ID | Type | Item | Impact | Mitigation | Owner |
|---|---|---|---|---|---|
| R1 | Risk | Dependency register incomplete; hidden consumers exist | Unplanned breakage | Validator + evidence gate + monitoring evidence required before approval | Enterprise architecture |
| R2 | Risk | Governance slows retirements past licence renewal dates | Renewal penalties | Split misses (structural / policy / capacity); negotiate short extensions on long dependency chains | Transformation Manager |
| R3 | Risk | Decision model unavailable or returns bad output | Gate stalls | Fail closed to humans; router falls back to floor tier | Platform engineering |
| R4 | Risk | Prompt injection in free-text evidence | Fraudulent approval | Screen before any model sees text; flagged text forces human review | Platform engineering |
| R5 | Risk | Savings redefined mid-programme | Misleading reporting | Hashed, versioned definitions; cross-definition comparison refused | Finance |
| A1 | Assumption | 50% of critical orphan events cause a rollback | ROI swings from loss to gain | Sensitivity analysis; break-even rate published | Transformation Manager |
| A2 | Assumption | Model prices and speeds in the catalogue | Cost figures wrong | Marked illustrative; refresh before any real decision | Platform engineering |
| I1 | Issue | Jev real-endpoint behaviour unverified in this repo | Cannot claim real accuracy | Mock only; same held-out harness reruns with a key | Platform engineering |
| D1 | Dependency | Vendor terms (retention, residency) for any hosted decision model | Compliance | Contract review before any real use | DPO |

## ADKAR change plan
| Stage | What people need | Action in this programme |
|---|---|---|
| **A**wareness | Why unmanaged retirement fails | Show the naive-vs-governed comparison (108 orphaned links vs 0) in the kickoff |
| **D**esire | Reason to accept slower waves | Show verified vs claimed savings; make the renewal trade-off explicit |
| **K**nowledge | How approvals work | One-page approval-pack guide; autonomy ladder explained |
| **A**bility | Capacity to review | Review load is shown per wave (59 decisions needing a human in the demo run) |
| **R**einforcement | Keep the discipline | Audit chain, definition registry, and retrospective after each wave |

## Delivery approach: DMAIC container, Agile delivery
Define (this document) → Measure (baseline: naive plan metrics) → Analyse (why plans break; renewal decomposition) →
Improve (three Scrum releases, below) → Control (audit chain, definition registry, gated rollout).

### Releases and gates
| Release | Scope | Gate to proceed | Pilot design |
|---|---|---|---|
| **R1 Plan & prove** | Estate model, graph, readiness, sequencers, independent validator, audit log | All tests pass; validator reports 0 violations on the governed plan across 5 seeds; security review of data handling | Shadow-plan one business unit's candidates and compare with its manual plan |
| **R2 Govern** | Policy engine, evidence gate, autonomy ladder, security layer, Jev layer (mock) | 0 false approvals on held-out evidence set; injection and outage tests pass; audit chain verifies | Reviewers receive approval packs for two waves; measure review time and overrides |
| **R3 Prove value** | Benefits tracker, routing evaluation, ROI, real model clients behind the same interfaces | Held-out routing re-run with a real decision-model key meets the accuracy floor at no higher cost than static rules; Finance signs the savings definition | Parallel-run routing on a sample of real tasks with human scoring |

**Go / no-go rule:** a release does not start until the previous gate is met; a failed gate is reported, not waived.
