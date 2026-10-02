"""Governance policy engine + autonomy ladder.

Autonomy ladder:  L0 observe -> L1 recommend -> L2 prepare artefacts -> L3 reversible pre-steps (with
approval) -> L4 irreversible production change.  NO AGENT IS EVER GRANTED L4: a decommission is always
executed by a human change authority; the system only prepares the approval pack.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .audit import AuditLog
from .data_gen import App
from .jev_layer.client import JevClient, JevError
from .readiness import Readiness
from .security import screen

LEVELS = {"observe": 0, "recommend": 1, "prepare": 2, "reversible_step": 3, "irreversible_change": 4}
AGENT_CEILING = {"dependency_mapper": 1, "readiness_scorer": 1, "sequencer": 2, "governance_gate": 2,
                 "benefits_tracker": 1, "status_writer": 2}
MAX_GRANTABLE = 3   # hard ceiling: nothing above L3 is ever grantable to an agent
SUPPORTED_MIN, REFUSED_MAX = 0.85, 0.15
STATEMENTS = ["consumers_migrated", "retention_covered", "owner_signoff"]


@dataclass
class Decision:
    app_id: str
    status: str                       # APPROVAL_PACK_READY | HUMAN_REVIEW_REQUIRED | BLOCKED
    approvers: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    p_supported: float | None = None


def authorise(agent: str, action: str) -> bool:
    level = LEVELS[action]
    if level > MAX_GRANTABLE:
        return False
    return level <= AGENT_CEILING.get(agent, 0)


def evidence_gate(jev: JevClient | None, text: str) -> tuple[float | None, list[str]]:
    """Jev-style typed check: probability the evidence supports retirement. Fails closed."""
    s = screen(text)
    notes: list[str] = []
    if s.injected:
        return None, ["prompt-injection pattern in evidence text: not sent to any model"]
    if jev is None:
        return None, ["no decision model configured"]
    try:
        ps = [jev.judge(s.text, st) for st in STATEMENTS]
    except JevError as exc:
        return None, [f"decision model unavailable ({exc}): fail closed"]
    return min(ps), notes


def evaluate_decommission(app: App, readiness: Readiness, wave: int, freeze_waves: set[int],
                          evidence_text: str, jev: JevClient | None, audit: AuditLog | None = None
                          ) -> Decision:
    reasons: list[str] = []
    approvers = ["Change Authority Board"]            # always: L4 is human-only
    status = "APPROVAL_PACK_READY"

    def worse(new: str) -> None:
        nonlocal status
        order = ["APPROVAL_PACK_READY", "HUMAN_REVIEW_REQUIRED", "BLOCKED"]
        if order.index(new) > order.index(status):
            status = new

    if readiness.band == "blocked":
        worse("BLOCKED"); reasons.append("readiness blocked")
    elif readiness.band == "conditional":
        worse("HUMAN_REVIEW_REQUIRED"); reasons.append("readiness conditional")
    if app.criticality >= 3:
        if wave in freeze_waves:
            worse("BLOCKED"); reasons.append("change-freeze window")
        approvers.append("Service Owner")
        worse("HUMAN_REVIEW_REQUIRED"); reasons.append("criticality >= 3 needs extra sign-off")
    if app.regulated_data:
        approvers.append("Data Protection Officer")
        worse("HUMAN_REVIEW_REQUIRED"); reasons.append("regulated data")
    p, notes = evidence_gate(jev, evidence_text)
    reasons += notes
    if p is None:
        worse("HUMAN_REVIEW_REQUIRED")
    elif p <= REFUSED_MAX:
        worse("BLOCKED"); reasons.append(f"evidence refuted (p={p})")
    elif p < SUPPORTED_MIN:
        worse("HUMAN_REVIEW_REQUIRED"); reasons.append(f"evidence ambiguous (p={p})")
    else:
        reasons.append(f"evidence supports (p={p})")
    d = Decision(app.app_id, status, sorted(set(approvers)), reasons, p)
    if audit:
        audit.append("governance_gate", "decommission_decision", app=app.app_id, wave=wave,
                     status=status, p=p, reasons=reasons)
    return d
