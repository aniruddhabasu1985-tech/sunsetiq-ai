import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
import pytest
from sunsetiq.data_gen import App, Edge, Estate, generate_estate
from sunsetiq.graph import build_graph, cutover_groups, transitive_dependents
from sunsetiq.readiness import score_all
from sunsetiq.sequencer import (FREEZE_WAVES, Plan, Task, measure, plan_governed, plan_naive,
                                validate_plan)


def mk(aid, role="retire", crit=1, lic=100_000, run=50_000, decom=5, renewal=9, sid=None):
    return App(aid, aid, "billing", "Consumer", lic, run, 100, crit, False, decom, renewal, role, sid)


def tiny():
    est = Estate()
    est.apps = {"S": mk("S", "survivor", 4), "R": mk("R", sid="S"), "D": mk("D", "keep", 3)}
    est.edges = [Edge("D", "R", "api", 2)]
    return est


def test_estate_is_deterministic():
    a, b = generate_estate(seed=3), generate_estate(seed=3)
    assert [x.annual_licence for x in a.apps.values()] == [x.annual_licence for x in b.apps.values()]
    assert len(a.edges) == len(b.edges)


def test_estate_size_and_roles():
    est = generate_estate()
    assert len(est.apps) == 200
    assert sum(1 for a in est.apps.values() if a.role == "survivor") == 10
    assert len(est.retire_candidates()) > 40


def test_cycles_become_cutover_groups():
    est = generate_estate()
    groups = cutover_groups(est, build_graph(est))
    assert sum(1 for gp in groups if len(gp) > 1) >= 3


def test_blast_radius_is_transitive():
    est = Estate(); est.apps = {k: mk(k) for k in "ABC"}
    est.edges = [Edge("B", "A", "api", 2), Edge("C", "B", "api", 2)]
    assert transitive_dependents(build_graph(est), "A") == {"B", "C"}


def test_readiness_bounded_and_banded():
    est = generate_estate()
    res = score_all(est, build_graph(est))
    assert all(0 <= r.score <= 100 for r in res.values())
    assert {r.band for r in res.values()} <= {"ready", "conditional", "blocked"}


def test_validator_flags_orphan():
    est = tiny()
    plan = Plan("bad", [Task("decommission", 0, ("R",), 5, 1, 1)])
    v = validate_plan(est, plan)
    assert v.orphaned_links == 1 and v.critical_orphans == 1


def test_validator_accepts_rewire_before_decom():
    est = tiny()
    plan = Plan("ok", [Task("rewire", 0, ("R",), 2, 1, 1), Task("decommission", 0, ("R",), 5, 2, 2)])
    assert validate_plan(est, plan).total == 0


def test_validator_rejects_same_wave_rewire_and_decom():
    est = tiny()
    plan = Plan("same", [Task("rewire", 0, ("R",), 2, 1, 1), Task("decommission", 0, ("R",), 5, 1, 1)])
    assert validate_plan(est, plan).orphaned_links == 1


def test_validator_flags_unscheduled():
    est = tiny()
    assert validate_plan(est, Plan("empty")).unscheduled_groups == 1


def test_governed_plan_clean_on_default_estate():
    est = generate_estate()
    assert validate_plan(est, plan_governed(est)).total == 0


@pytest.mark.parametrize("seed", [1, 2, 3, 11, 42])
def test_governed_plan_clean_across_seeds(seed):
    est = generate_estate(seed=seed)
    assert validate_plan(est, plan_governed(est)).total == 0


def test_naive_plan_breaks_things():
    est = generate_estate()
    v = validate_plan(est, plan_naive(est))
    assert v.orphaned_links > 0 and v.critical_orphans > 0


def test_governed_retires_everything_and_respects_freeze():
    est = generate_estate()
    plan = plan_governed(est)
    retired = {a for t in plan.tasks if t.kind == "decommission" for a in t.apps}
    assert retired == {a.app_id for a in est.retire_candidates()}
    for t in plan.tasks:
        if t.kind == "decommission" and max(est.apps[a].criticality for a in t.apps) >= 3:
            assert t.done_wave not in FREEZE_WAVES


def test_cycle_members_retire_together():
    est = generate_estate()
    plan = plan_governed(est)
    for t in plan.tasks:
        if t.kind == "decommission" and len(t.apps) > 1:
            assert len(t.apps) >= 2 and t.done_wave > 0


def test_measure_claimed_vs_verified():
    est = generate_estate()
    n, g = measure(est, plan_naive(est)), measure(est, plan_governed(est))
    assert n.net_of_rollbacks < n.claimed_saving
    assert g.net_of_rollbacks == g.claimed_saving and g.rollbacks == 0


def test_renewal_penalty_counts_late_retirement():
    est = tiny(); est.apps["R"].renewal_wave = 1
    plan = Plan("late", [Task("rewire", 0, ("R",), 2, 1, 1), Task("decommission", 0, ("R",), 5, 2, 2)])
    assert measure(est, plan).renewal_penalty == 100_000


def test_renewal_lower_bound_is_a_floor_for_any_valid_plan():
    from sunsetiq.sequencer import renewal_lower_bound
    for seed in (7, 11, 42):
        est = generate_estate(seed=seed)
        lb = renewal_lower_bound(est)
        for cap in (60, 120, 100_000):
            assert measure(est, plan_governed(est, cap), cap).renewal_penalty >= lb
