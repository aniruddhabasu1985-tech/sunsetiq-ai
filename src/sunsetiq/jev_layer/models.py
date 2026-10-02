"""Model catalogue. ALL PRICES, SPEEDS AND EFFORT MULTIPLIERS ARE ILLUSTRATIVE ASSUMPTIONS, not live
quotes: replace with current vendor pricing before using the cost numbers for any real decision."""
from __future__ import annotations

from dataclasses import dataclass

TIERS = ["nano", "fast", "balanced", "frontier"]
ALLOWED_VENDORS = {"openai": "US", "google": "US", "anthropic": "US"}   # US-headquartered only
EFFORT_MULT = {"none": 1.0, "low": 1.0, "medium": 2.0, "high": 4.0}      # reasoning tokens vs plain output
CACHE_DISCOUNT = 0.90                                                    # cached input tokens (assumed)


@dataclass(frozen=True)
class Model:
    slug: str
    vendor: str
    tier: str
    in_per_m: float      # USD per million input tokens (illustrative)
    out_per_m: float
    ttft_ms: int
    tps: int             # output tokens / second
    supports_effort: bool


CATALOG: list[Model] = [
    Model("openai/gpt-5-nano", "openai", "nano", 0.05, 0.40, 250, 200, False),
    Model("google/gemini-3-flash", "google", "fast", 0.50, 3.00, 300, 160, True),
    Model("anthropic/claude-sonnet-5-5", "anthropic", "balanced", 3.00, 15.00, 450, 90, True),
    Model("anthropic/claude-opus-5-5", "anthropic", "frontier", 15.00, 75.00, 700, 55, True),
]


def assert_vendor_ok(vendor: str, hq_country: str) -> None:
    """Reject non-allow-listed vendors at code level (no silent fallback to an unvetted vendor)."""
    if ALLOWED_VENDORS.get(vendor) != hq_country:
        raise ValueError(f"vendor '{vendor}' ({hq_country}) is not on the approved US-headquartered list")


for _m in CATALOG:
    assert_vendor_ok(_m.vendor, "US")


def cost_usd(model: Model, in_tok: int, out_tok: int, effort: str = "none", cached: bool = False) -> float:
    eff = EFFORT_MULT[effort if model.supports_effort else "none"]
    in_cost = in_tok * model.in_per_m / 1e6 * ((1 - CACHE_DISCOUNT) if cached else 1.0)
    return in_cost + out_tok * eff * model.out_per_m / 1e6


def latency_ms(model: Model, out_tok: int, effort: str = "none") -> float:
    eff = EFFORT_MULT[effort if model.supports_effort else "none"]
    return model.ttft_ms + out_tok * eff / model.tps * 1000
