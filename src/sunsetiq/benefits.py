"""Benefits tracker: claimed vs verified savings under VERSIONED definitions.

The same retirement plan can be reported at very different 'savings' depending on policy levers.
Definitions are immutable, hashed and diffable; figures computed under different definitions
cannot be compared silently (DefinitionMismatch)."""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass

from .audit import AuditLog
from .data_gen import Estate
from .sequencer import CAPACITY, Plan, validate_plan

COST_PER_EFFORT_POINT = 2_500        # ASSUMED, currency units per effort point


class DefinitionMismatch(ValueError):
    pass


@dataclass(frozen=True)
class SavingsDefinition:
    name: str
    count_rolled_back: bool            # count retirements that had to be reversed?
    count_orphaned_as_done: bool       # count retirements that left live dependents orphaned?
    net_cost_to_achieve: bool          # subtract delivery + rework effort cost?
    net_missed_renewal: bool           # subtract licence paid again after a missed renewal date?

    @property
    def digest(self) -> str:
        return hashlib.sha256(json.dumps(asdict(self), sort_keys=True).encode()).hexdigest()[:12]


LOOSE_V1 = SavingsDefinition("loose_v1", True, True, False, False)
VERIFIED_V1 = SavingsDefinition("verified_v1", False, False, True, True)


class DefinitionRegistry:
    def __init__(self, audit: AuditLog | None = None) -> None:
        self.defs: dict[str, SavingsDefinition] = {}
        self.audit = audit

    def register(self, d: SavingsDefinition) -> str:
        if d.name in self.defs and self.defs[d.name].digest != d.digest:
            raise DefinitionMismatch(f"'{d.name}' already registered with a different hash; use a new version name")
        self.defs[d.name] = d
        if self.audit:
            self.audit.append("benefits_tracker", "definition_registered", name=d.name, digest=d.digest)
        return d.digest

    @staticmethod
    def diff(a: SavingsDefinition, b: SavingsDefinition) -> dict[str, tuple]:
        da, db = asdict(a), asdict(b)
        return {k: (da[k], db[k]) for k in da if k != "name" and da[k] != db[k]}


@dataclass
class SavingsFigure:
    plan: str
    definition: str
    digest: str
    annual_run_rate: int
    cost_to_achieve: int
    missed_renewal_cost: int
    net_year_one: int


def compute(estate: Estate, plan: Plan, d: SavingsDefinition, capacity: int = CAPACITY) -> SavingsFigure:
    v = validate_plan(estate, plan)
    orphan_providers = {r for r, _, _ in v.orphan_detail}
    rolled_back = {r for r, c, _ in v.orphan_detail if estate.apps[c].criticality >= 3}
    retired = {a: t.done_wave for t in plan.tasks if t.kind == "decommission" for a in t.apps}
    counted = []
    for a in retired:
        if a in rolled_back and not d.count_rolled_back:
            continue
        if a in orphan_providers and not d.count_orphaned_as_done:
            continue
        counted.append(a)
    run_rate = sum(estate.apps[a].annual_saving for a in counted)
    rework = 0
    for r, c, _ in v.orphan_detail:
        e = next(x for x in estate.edges if x.consumer == c and x.provider == r)
        rework += 2 * e.rewire_effort
    rework += sum(estate.apps[a].decom_effort for a in rolled_back)
    effort = sum(t.effort for t in plan.tasks) + rework
    cta = effort * COST_PER_EFFORT_POINT if d.net_cost_to_achieve else 0
    missed = sum(estate.apps[a].annual_licence for a in counted
                 if retired[a] > estate.apps[a].renewal_wave) if d.net_missed_renewal else 0
    return SavingsFigure(plan.name, d.name, d.digest, run_rate, cta, missed, run_rate - cta - missed)


class BenefitsTracker:
    def __init__(self, registry: DefinitionRegistry) -> None:
        self.registry = registry

    def gap(self, a: SavingsFigure, b: SavingsFigure) -> int:
        """Difference between two figures; refuses to compare across definitions silently."""
        if a.digest != b.digest:
            raise DefinitionMismatch(f"{a.definition}({a.digest}) vs {b.definition}({b.digest}): "
                                     "different definitions; diff them explicitly")
        return a.net_year_one - b.net_year_one
