import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
import pytest
from sunsetiq.audit import AuditLog
from sunsetiq.benefits import (LOOSE_V1, VERIFIED_V1, BenefitsTracker, DefinitionMismatch, DefinitionRegistry,
                               SavingsDefinition, compute)
from sunsetiq.data_gen import generate_estate
from sunsetiq.sequencer import plan_governed, plan_naive


def test_definition_hash_is_stable_and_distinct():
    assert LOOSE_V1.digest == LOOSE_V1.digest and LOOSE_V1.digest != VERIFIED_V1.digest


def test_registry_blocks_silent_redefinition():
    reg = DefinitionRegistry()
    reg.register(LOOSE_V1)
    with pytest.raises(DefinitionMismatch):
        reg.register(SavingsDefinition("loose_v1", False, True, False, False))


def test_registry_logs_to_audit():
    log = AuditLog(); DefinitionRegistry(log).register(VERIFIED_V1)
    assert log.entries[0]["event"] == "definition_registered" and log.verify()[0]


def test_diff_shows_levers():
    d = DefinitionRegistry.diff(LOOSE_V1, VERIFIED_V1)
    assert set(d) == {"count_rolled_back", "count_orphaned_as_done", "net_cost_to_achieve", "net_missed_renewal"}


def test_cross_definition_comparison_refused():
    est = generate_estate(); p = plan_governed(est)
    tr = BenefitsTracker(DefinitionRegistry())
    with pytest.raises(DefinitionMismatch):
        tr.gap(compute(est, p, LOOSE_V1), compute(est, p, VERIFIED_V1))


def test_naive_plan_gap_between_definitions_is_large_governed_is_not_from_orphans():
    est = generate_estate()
    n_l, n_v = compute(est, plan_naive(est), LOOSE_V1), compute(est, plan_naive(est), VERIFIED_V1)
    g_l, g_v = compute(est, plan_governed(est), LOOSE_V1), compute(est, plan_governed(est), VERIFIED_V1)
    assert n_l.annual_run_rate > n_v.annual_run_rate           # rollbacks/orphans stripped out
    assert g_l.annual_run_rate == g_v.annual_run_rate          # nothing to strip from a clean plan


def test_loose_equals_gross_run_rate_of_all_retirements():
    est = generate_estate()
    assert compute(est, plan_governed(est), LOOSE_V1).annual_run_rate == \
        sum(a.annual_saving for a in est.retire_candidates())


def test_cost_to_achieve_only_in_verified():
    est = generate_estate(); p = plan_governed(est)
    assert compute(est, p, LOOSE_V1).cost_to_achieve == 0 and compute(est, p, VERIFIED_V1).cost_to_achieve > 0
