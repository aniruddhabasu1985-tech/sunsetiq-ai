# Governance

## Autonomy ladder
| Level | Meaning | Who can hold it |
|---|---|---|
| L0 observe | Read data | any agent |
| L1 recommend | Propose | dependency mapper, readiness scorer, benefits tracker |
| L2 prepare | Draft artefacts (approval packs, change requests, status) | sequencer, governance gate, status writer |
| L3 reversible step | Perform a reversible pre-step with approval | **no agent is currently granted this** |
| L4 irreversible change | Decommission in production | **nobody — humans only, always** |

`authorise(agent, action)` returns false for any level above L3 for every agent, and unknown agents hold nothing above L0.

## Decommission policy (all rules are deterministic code)
- Every decision names the **Change Authority Board** as approver; no code path yields an "executed" status.
- Criticality ≥ 3: add **Service Owner**; blocked entirely inside a change-freeze wave.
- Regulated data: add **Data Protection Officer** and force human review.
- Readiness band "conditional": human review. "Blocked": blocked.
- The most restrictive outcome wins.

## Evidence gate
Evidence packs are untrusted free text. Order of operations: **redact** PII/secrets → **screen** for injection → only then
ask the decision model three typed questions (consumers migrated? retention covered? owner signed off?). The gate takes
the *minimum* probability. Bands: ≥ 0.85 supported; ≤ 0.15 refused; in between → human review.
**Fail closed:** injection flagged, no model configured, model error, or invalid output → human review, never approval.

## Audit
Every mapping, score, plan, routing decision, definition registration and policy decision is appended to a SHA-256 hash
chain. `verify()` detects an edited entry and a deleted entry (both tested).

## Decision-model data handling
Text is redacted before it can reach any model. The vendor states that Jev runs under zero-data-retention terms and never
receives attachments; those are vendor statements to be confirmed contractually before real use.
