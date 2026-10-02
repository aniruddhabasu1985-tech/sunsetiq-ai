"""Security layer: PII/secret redaction and prompt-injection screening for untrusted text."""
from __future__ import annotations

import re
from dataclasses import dataclass

_PATTERNS = {
    "email": re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"),
    "phone": re.compile(r"(?<!\w)\+?\d[\d\s().-]{8,}\d(?!\w)"),
    "api_key": re.compile(r"\b(?:sk|key|tok)[-_][A-Za-z0-9]{12,}\b"),
    "password": re.compile(r"(?i)password\s*[:=]\s*\S+"),
}
_INJECTION = [
    r"ignore (all |any )?(previous|prior|above) instructions",
    r"disregard (the )?(policy|rules|instructions)",
    r"(mark|set|treat) (this|it) as approved",
    r"without (any )?(review|approval|checks?)",
    r"you are now", r"system prompt", r"override (the )?(gate|policy|governance)",
]
_INJ_RE = [re.compile(p, re.I) for p in _INJECTION]


@dataclass
class Screened:
    text: str
    redactions: dict[str, int]
    injection_flags: list[str]

    @property
    def injected(self) -> bool:
        return bool(self.injection_flags)


def redact(text: str) -> tuple[str, dict[str, int]]:
    counts: dict[str, int] = {}
    for name, rx in _PATTERNS.items():
        text, n = rx.subn(f"[REDACTED_{name.upper()}]", text)
        if n:
            counts[name] = n
    return text, counts


def screen(text: str) -> Screened:
    clean, counts = redact(text)
    flags = [rx.pattern for rx in _INJ_RE if rx.search(clean)]
    return Screened(clean, counts, flags)
