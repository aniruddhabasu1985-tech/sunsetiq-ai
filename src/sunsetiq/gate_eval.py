"""Evidence-gate evaluation against labelled evidence packs. Critical error = FALSE APPROVE
(unsupported evidence reaching 'supported'). Routing a good pack to a human is a cost, not a harm."""
from __future__ import annotations

from collections import Counter

from .jev_layer.client import JevClient
from .policy import REFUSED_MAX, SUPPORTED_MIN, evidence_gate


def band(p: float | None) -> str:
    if p is None:
        return "human"
    return "supported" if p >= SUPPORTED_MIN else "refused" if p <= REFUSED_MAX else "ambiguous"


def evaluate_gate(items, jev: JevClient) -> dict:
    out, rows = Counter(), []
    for cat, truth, text in items:
        p, _ = evidence_gate(jev, text)
        b = band(p)
        rows.append((cat, truth, b, p))
        if not truth and b == "supported":
            out["false_approve"] += 1
        elif truth and b == "refused":
            out["false_block"] += 1
        elif truth and b == "supported":
            out["true_approve"] += 1
        elif truth:
            out["good_but_sent_to_human"] += 1
        else:
            out["unsupported_caught"] += 1      # refused, ambiguous or human: none reached approval
    out["n"] = len(items)
    return {"summary": dict(out), "rows": rows}
