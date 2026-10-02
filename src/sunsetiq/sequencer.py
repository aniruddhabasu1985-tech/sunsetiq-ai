"""Wave sequencing: a naive cost-first plan vs a dependency-aware governed plan.

Both emit the same Plan structure. `validate_plan` re-derives every invariant from the plan alone
(it does not import sequencer internals), so a bug in the governed planner cannot hide itself.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import networkx as nx

from .data_gen import Estate
from .graph import build_graph, cutover_groups

CAPACITY = 60                 # effort points per wave
MAX_WAVES = 60
FREEZE_WAVES = {5, 6}         # change-freeze: no decommission of criticality >= 3
MAX_CRITICAL_DECOMS_PER_WAVE = 2


@dataclass
class Task:
    kind: str                 # "rewire" | "decommission"
    group: int
    apps: tuple[str, ...]
    effort: int
    start_wave: int = 0
    done_wave: int = 0        # wave in which the task completed


@dataclass
class Plan:
    name: str
    tasks: list[Task] = field(default_factory=list)
    waves_used: int = 0


def _groups(estate: Estate):
    g = build_graph(estate)
    groups = sorted(cutover_groups(estate, g), key=lambda s: sorted(s))
    gid = {a: i for i, grp in enumerate(groups) for a in grp}
    return g, groups, gid


def _group_info(estate: Estate, g: nx.DiGraph, groups, gid):
    info = []
    retire = {a.app_id for a in estate.retire_candidates()}
    for i, grp in enumerate(groups):
        rewire = 0
        blockers: set[int] = set()   # groups whose retirement must precede this group's
        for a in grp:
            for e in estate.dependents_of(a):
                if e.consumer in grp:
                    continue
                if e.consumer in retire:
                    blockers.add(gid[e.consumer])
                else:
                    rewire += e.rewire_effort
        apps = [estate.apps[a] for a in grp]
        info.append({
            "id": i, "apps": tuple(sorted(grp)), "rewire": rewire, "blockers": blockers,
            "decom": sum(a.decom_effort for a in apps),
            "saving": sum(a.annual_saving for a in apps),
            "max_crit": max(a.criticality for a in apps),
            "renewal": min(a.renewal_wave for a in apps),
        })
    return info


def plan_naive(estate: Estate, capacity: int = CAPACITY) -> Plan:
    """Rank by annual cost, retire in that order. No rewiring, no dependency checks, no freeze."""
    plan = Plan("naive_cost_first")
    apps = sorted(estate.retire_candidates(), key=lambda a: (-a.annual_saving, a.app_id))
    cumulative = 0
    for a in apps:
        start_wave = cumulative // capacity + 1
        cumulative += a.decom_effort
        done = -(-cumulative // capacity)          # ceil
        plan.tasks.append(Task("decommission", -1, (a.app_id,), a.decom_effort, start_wave, done))
    plan.waves_used = max((t.done_wave for t in plan.tasks), default=0)
    return plan


def plan_governed(estate: Estate, capacity: int = CAPACITY, urgency: float = 1.5) -> Plan:
    """Dependency-aware: rewire live dependents first, retire dependents before providers,
    honour change-freeze waves and a per-wave cap on critical decommissions."""
    g, groups, gid = _groups(estate)
    info = _group_info(estate, g, groups, gid)
    by_id = {x["id"]: x for x in info}
    unlocks: dict[int, int] = {x["id"]: 0 for x in info}
    for x in info:
        for b in x["blockers"]:
            unlocks[b] += x["saving"]   # retiring b unlocks x's savings

    rewire_left = {x["id"]: x["rewire"] for x in info}
    decom_left = {x["id"]: x["decom"] for x in info}
    rewire_done: dict[int, int] = {x["id"]: 0 for x in info if x["rewire"] == 0}
    retired: dict[int, int] = {}
    started: dict[tuple[str, int], int] = {}
    plan = Plan("governed_dependency_aware")

    def priority(x, wave):
        own = x["saving"] + 0.5 * unlocks[x["id"]]
        effort = max(1, x["rewire"] + x["decom"])
        u = urgency if wave >= x["renewal"] - 1 else 1.0
        return u * own / effort

    for wave in range(1, MAX_WAVES + 1):
        if len(retired) == len(info):
            break
        cap = capacity
        crit_decoms = 0
        order = sorted(info, key=lambda x: -priority(x, wave))
        finished_decom: list[int] = []
        finished_rewire: list[int] = []
        # decommission pass: only groups whose rewires are done in a PREVIOUS wave
        # and whose retire-set consumers retired in a PREVIOUS wave
        for x in order:
            i = x["id"]
            if i in retired:
                continue
            if rewire_left[i] > 0 or rewire_done.get(i, wave) >= wave:
                continue
            if any(b not in retired or retired[b] >= wave for b in x["blockers"]):
                continue
            if x["max_crit"] >= 3:
                if wave in FREEZE_WAVES or crit_decoms >= MAX_CRITICAL_DECOMS_PER_WAVE:
                    continue
            if cap <= 0:
                break
            started.setdefault(("decommission", i), wave)
            take = min(cap, decom_left[i])
            decom_left[i] -= take
            cap -= take
            if decom_left[i] == 0:
                finished_decom.append(i)
                if x["max_crit"] >= 3:
                    crit_decoms += 1
        # rewire pass with remaining capacity
        for x in order:
            i = x["id"]
            if cap <= 0:
                break
            if rewire_left[i] > 0 and i not in retired:
                started.setdefault(("rewire", i), wave)
                take = min(cap, rewire_left[i])
                rewire_left[i] -= take
                cap -= take
                if rewire_left[i] == 0:
                    finished_rewire.append(i)
        for i in finished_rewire:
            rewire_done[i] = wave
        for i in finished_decom:
            retired[i] = wave
    for x in info:
        i = x["id"]
        if x["rewire"] > 0 and i in rewire_done:
            plan.tasks.append(Task("rewire", i, x["apps"], x["rewire"],
                                   started[("rewire", i)], rewire_done[i]))
        if i in retired:
            plan.tasks.append(Task("decommission", i, x["apps"], x["decom"],
                                   started[("decommission", i)], retired[i]))
    plan.waves_used = max((t.done_wave for t in plan.tasks), default=0)
    return plan


# ----------------------------------------------------------------------------- validator
@dataclass
class Violations:
    orphaned_links: int = 0
    critical_orphans: int = 0
    freeze_violations: int = 0
    concurrency_violations: int = 0
    unscheduled_groups: int = 0
    orphan_detail: list[tuple[str, str, int]] = field(default_factory=list)

    @property
    def total(self) -> int:
        return (self.orphaned_links + self.freeze_violations
                + self.concurrency_violations + self.unscheduled_groups)


def validate_plan(estate: Estate, plan: Plan) -> Violations:
    """Independent check. A decommission of R in wave w is an orphan event for every consumer D
    of R that is neither retired in a wave < w nor covered by a rewire task finished in a wave < w."""
    v = Violations()
    retired_wave: dict[str, int] = {}
    rewired: dict[str, int] = {}          # provider app -> wave its non-retiring dependents were rewired
    for t in plan.tasks:
        for a in t.apps:
            if t.kind == "decommission":
                retired_wave[a] = t.done_wave
            else:
                rewired[a] = t.done_wave
    scheduled = set(retired_wave)
    v.unscheduled_groups = sum(1 for a in estate.retire_candidates() if a.app_id not in scheduled)
    crit_per_wave: dict[int, int] = {}
    for t in plan.tasks:
        if t.kind != "decommission":
            continue
        if max(estate.apps[a].criticality for a in t.apps) >= 3:
            if t.done_wave in FREEZE_WAVES:
                v.freeze_violations += 1
            crit_per_wave[t.done_wave] = crit_per_wave.get(t.done_wave, 0) + 1
        for r in t.apps:
            for e in estate.dependents_of(r):
                if e.consumer in t.apps:
                    continue
                consumer_gone = e.consumer in retired_wave and retired_wave[e.consumer] < t.done_wave
                covered = r in rewired and rewired[r] < t.done_wave
                if not consumer_gone and not covered:
                    v.orphaned_links += 1
                    crit = estate.apps[e.consumer].criticality >= 3
                    v.critical_orphans += 1 if crit else 0
                    v.orphan_detail.append((r, e.consumer, t.done_wave))
    v.concurrency_violations = sum(1 for n in crit_per_wave.values() if n > MAX_CRITICAL_DECOMS_PER_WAVE)
    return v


# ----------------------------------------------------------------------------- metrics
@dataclass
class PlanMetrics:
    name: str
    waves: int
    apps_retired: int
    claimed_saving: int        # annual run-rate claimed from every retirement in the plan
    net_of_rollbacks: int       # claimed minus savings reversed by rollbacks
    rollbacks: int
    orphaned_links: int
    critical_orphans: int
    rework_effort: int         # emergency rewires (2x) + wasted decom effort on rollbacks
    renewal_penalty: int       # licence paid again because retirement missed its renewal wave
    freeze_violations: int
    saving_by_wave: list[int]  # cumulative verified run-rate at end of each wave
    effective_waves: int = 0   # waves needed once rework effort is included


def measure(estate: Estate, plan: Plan, capacity: int = CAPACITY) -> PlanMetrics:
    v = validate_plan(estate, plan)
    rolled_back: set[str] = set()
    rework = 0
    for r, consumer, _ in v.orphan_detail:
        e = next(x for x in estate.edges if x.consumer == consumer and x.provider == r)
        rework += 2 * e.rewire_effort
        if estate.apps[consumer].criticality >= 3:
            rolled_back.add(r)
    retired_wave = {a: t.done_wave for t in plan.tasks if t.kind == "decommission" for a in t.apps}
    for r in rolled_back:
        rework += estate.apps[r].decom_effort
    claimed = sum(estate.apps[a].annual_saving for a in retired_wave)
    verified = claimed - sum(estate.apps[a].annual_saving for a in rolled_back)
    penalty = sum(estate.apps[a].annual_licence for a, w in retired_wave.items()
                  if w > estate.apps[a].renewal_wave and a not in rolled_back)
    waves = plan.waves_used
    by_wave = []
    for w in range(1, waves + 1):
        by_wave.append(sum(estate.apps[a].annual_saving for a, rw in retired_wave.items()
                           if rw <= w and a not in rolled_back))
    base_effort = sum(t.effort for t in plan.tasks)
    effective = -(-(base_effort + rework) // capacity)
    return PlanMetrics(plan.name, waves, len(retired_wave), claimed, verified, len(rolled_back),
                       v.orphaned_links, v.critical_orphans, rework, penalty,
                       v.freeze_violations, by_wave, max(waves, effective))


def renewal_lower_bound(estate: Estate) -> int:
    """Licence cost that NO plan can avoid paying again, even with unlimited capacity: the app's
    earliest feasible retirement wave (dependency chain depth only) is later than its renewal wave.
    Separates structural misses (a negotiation problem) from capacity misses (a resourcing problem)."""
    g, groups, gid = _groups(estate)
    info = {x["id"]: x for x in _group_info(estate, g, groups, gid)}
    memo: dict[int, int] = {}

    def earliest(i: int) -> int:
        if i in memo:
            return memo[i]
        x = info[i]
        base = 2 if x["rewire"] > 0 else 1
        memo[i] = max([base] + [earliest(b) + 1 for b in x["blockers"]])
        return memo[i]

    total = 0
    for i, x in info.items():
        w = earliest(i)
        for a in x["apps"]:
            if w > estate.apps[a].renewal_wave:
                total += estate.apps[a].annual_licence
    return total
