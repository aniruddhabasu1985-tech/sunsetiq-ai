"""Hash-chained, tamper-evident audit log."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field

GENESIS = "0" * 64


@dataclass
class AuditLog:
    entries: list[dict] = field(default_factory=list)

    @staticmethod
    def _digest(prev: str, body: dict) -> str:
        return hashlib.sha256((prev + json.dumps(body, sort_keys=True, default=str)).encode()).hexdigest()

    def append(self, actor: str, event: str, **data) -> dict:
        prev = self.entries[-1]["hash"] if self.entries else GENESIS
        body = {"seq": len(self.entries), "actor": actor, "event": event, "data": data}
        entry = {**body, "prev": prev, "hash": self._digest(prev, body)}
        self.entries.append(entry)
        return entry

    def verify(self) -> tuple[bool, int | None]:
        """Return (ok, first_bad_seq)."""
        prev = GENESIS
        for e in self.entries:
            body = {k: e[k] for k in ("seq", "actor", "event", "data")}
            if e["prev"] != prev or e["hash"] != self._digest(prev, body):
                return False, e["seq"]
            prev = e["hash"]
        return True, None
