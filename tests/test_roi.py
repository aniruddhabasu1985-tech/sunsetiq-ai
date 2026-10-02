import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
from sunsetiq.data_gen import generate_estate
from sunsetiq.roi import ai_spend_at_scale, compute_roi, sensitivity

EST = generate_estate()


def test_every_input_is_labelled():
    r = compute_roi(EST, 59, 0.65)
    assert {l.label for l in r.lines} <= {"Given", "Calculated", "Assumed"}
    assert all(l.label for l in r.lines)


def test_break_even_rate_gives_zero_net_benefit():
    r0 = compute_roi(EST, 59, 0.65)
    r1 = compute_roi(EST, 59, 0.65, incident_rate=r0.break_even_incident_rate)
    assert abs(r1.net_benefit) < 1.0


def test_net_benefit_monotonic_in_incident_rate():
    vals = [row[1] for row in sensitivity(EST, 59, 0.65)["incident_rate"]]
    assert vals == sorted(vals)


def test_ratio_below_one_below_break_even():
    r0 = compute_roi(EST, 59, 0.65)
    lo = compute_roi(EST, 59, 0.65, incident_rate=r0.break_even_incident_rate * 0.5)
    assert lo.benefit_cost_ratio < 1 and lo.net_benefit < 0
    assert compute_roi(EST, 59, 0.65, incident_rate=1.0).benefit_cost_ratio > 1


def test_ai_spend_scales_linearly():
    s = ai_spend_at_scale({"a": 61.0, "b": 5.59})
    assert s["a"][1_000_000] == 61_000.0 and s["b"][10_000] == 55.9


def test_structural_floor_is_below_governed_renewal_penalty():
    from sunsetiq.sequencer import measure, plan_governed, renewal_lower_bound
    assert renewal_lower_bound(EST) <= measure(EST, plan_governed(EST)).renewal_penalty
