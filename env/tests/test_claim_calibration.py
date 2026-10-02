"""Null calibration checks: public controls, independent noise, budgets and counts."""

import ast
from collections import Counter
from copy import deepcopy
import json
import math
from pathlib import Path
import time
from unittest.mock import patch

import numpy as np
import pytest
from scipy.stats import norm, t

from env import claim_calibration as calibration
from env.registry import load_world
from env.scoring import canonical_hash, verify_claims


@pytest.mark.parametrize("environment", calibration.NULL_ENVIRONMENTS)
@pytest.mark.parametrize("seed", calibration.DEVELOPMENT_SEEDS)
def test_prespecified_public_nulls_have_eligible_distinct_arms_and_zero_clean_effect(environment, seed):
    world, _ = load_world(environment, seed)
    for case in calibration.null_cases(environment):
        result = calibration._check_null(world, case, seed)
        assert result["null_confirmed"]
        assert result["eligibility"]["eligible"]
        assert canonical_hash(result["control"]) != canonical_hash(result["treatment"])
        assert abs(result["clean_difference"]) <= 1e-4 * result["declared_sigma"]
        coordinate = result["control"][world.axis_field][result["readout"]["row"]]
        assert coordinate > 0
        if environment in ("coupled_oscillators", "ising_spin"):
            # The readout is free, although the deliberately inoperative bond
            # joins two clamped sites; this avoids a forbidden clamped outcome.
            assert result["readout"]["channel"] in ("x_C", "m_C")
            assert "C" not in result["control"]["clamp"]


def test_null_factory_returns_fresh_specs_without_any_hidden_world_argument():
    cases = calibration.null_cases("ising_spin")
    cases[0]["control"]["clamp"]["A"] = -1
    assert calibration.null_cases("ising_spin")[0]["control"]["clamp"]["A"] == 1
    with pytest.raises(ValueError):
        calibration.null_cases("unregistered")


def test_clean_null_failure_retains_actual_diagnostic_difference():
    world, _ = load_world("ising_spin", 7)
    case = calibration.null_cases("ising_spin")[0]
    original = world.run

    def altered(spec, *, noise_key=None):
        observation = original(spec, noise_key=noise_key)
        if spec["suppress_bonds"]:
            observation["values"][0][world.channels.index("m_C")] += 0.01
        return observation

    with patch.object(world, "run", side_effect=altered):
        result = calibration._check_null(world, case, 7)
    assert not result["null_confirmed"]
    assert result["clean_difference"] == pytest.approx(0.01)
    assert len(result["clean_arm_values"]) == 2


def test_reference_intervals_use_frozen_eight_pair_statistics_and_prediction_not_estimation_radius():
    differences = np.array([-0.01, 0.02, 0.004, 0.008, -0.005, 0.0, -0.012, 0.002])
    result = calibration.reference_intervals(differences, 0.01)
    # Future mean variance and estimated center variance both contribute.
    radius = t.ppf(0.95, 7) * np.std(differences, ddof=1) * math.sqrt(2 / 8)
    assert result["exploration_student_prediction"] == pytest.approx([differences.mean() - radius, differences.mean() + radius])
    fixed = norm.ppf(0.95) * 0.01 * math.sqrt(2 / 8)
    assert result["fixed_zero_normal"] == pytest.approx([-fixed, fixed])
    shifted = calibration.reference_intervals(differences + 0.012, 0.01)
    assert shifted["fixed_zero_normal"] == result["fixed_zero_normal"]
    assert np.subtract(shifted["exploration_student_prediction"], result["exploration_student_prediction"]) == pytest.approx([0.012, 0.012])
    assert calibration.reference_intervals([0] * 8, 0.01)["exploration_student_prediction"] == [0, 0]


@pytest.mark.parametrize("values,sigma", [([0] * 7, 0.01), ([0] * 9, 0.01), ([float("nan")] * 8, 0.01), ([[0]] * 8, 0.01), ([0] * 8, 0), ([0] * 8, True), ([0] * 8, float("inf"))])
def test_reference_intervals_reject_invalid_or_wrong_count_data(values, sigma):
    with pytest.raises(ValueError):
        calibration.reference_intervals(values, sigma)


def test_wilson_matches_known_zero_event_and_half_event_intervals():
    assert calibration.wilson_interval(0, 100) == pytest.approx([0, 0.03699349820698568])
    assert calibration.wilson_interval(50, 100) == pytest.approx([0.4038315303659956, 0.5961684696340044])
    assert calibration.wilson_interval(0, 0) is None
    for successes, total in ((-1, 10), (11, 10), (True, 10), (0, -1), (1, 2.0)):
        with pytest.raises(ValueError):
            calibration.wilson_interval(successes, total)


def _tracked_ising(events):
    world, _ = load_world("ising_spin", 7)
    tracked = calibration._TrackedWorld(world, 7, events.append, time.monotonic() + 30, time.process_time() + 30)
    case = calibration.null_cases("ising_spin")[0]
    case.update({arm: world.validate(case[arm]) for arm in ("control", "treatment")})
    return tracked, case


def test_replication_freezes_both_intervals_before_independent_full_single_slot_verifications():
    events = []
    world, case = _tracked_ising(events)
    frozen_before_confirmation = []

    def observed_verify(world, claims, confirmation_key):
        frozen = [event for event in events if event["kind"] == "frozen"]
        assert len(frozen) == 1 and set(frozen[0]["intervals"]) == set(calibration.STRATEGIES)
        assert len(claims) == 1
        assert len(claims[0]["evidence_ids"]) == 16
        frozen_before_confirmation.append(deepcopy(claims))
        return verify_claims(world, claims, confirmation_key)

    with patch.object(calibration, "verify_claims", side_effect=observed_verify):
        assert calibration._replication(world, case, 7, 0, events.append) == 0
    starts = [event for event in events if event["kind"] == "query" and event["state"] == "started"]
    assert Counter(event["phase"] for event in starts) == {"exploration": 16, "verification:fixed_zero_normal": 16, "verification:exploration_student_prediction": 16}
    assert len({event["noise_key"] for event in starts}) == len(starts) == 48
    batches = [event for event in events if event["kind"] == "batch"]
    assert len(batches) == len(frozen_before_confirmation) == 2
    for batch in batches:
        assert batch["status"] == "complete"
        assert not batch["verification"]["duplicate"]
        assert batch["verification"]["eligibility"]["eligible"]
        assert batch["verification"]["replicates"] == 8
    # Exact re-execution uses the same public specs and keys, not cached truth.
    repeated = []
    repeat_world, repeat_case = _tracked_ising(repeated)
    calibration._replication(repeat_world, repeat_case, 7, 0, repeated.append)
    repeat_batches = [event for event in repeated if event["kind"] == "batch"]
    assert [event["verification"] for event in batches] == [event["verification"] for event in repeat_batches]


def test_failed_verifier_attempt_is_visible_and_does_not_discard_other_strategy():
    events = []
    world, case = _tracked_ising(events)

    def fail_first(world, claims, key):
        if key.endswith("fixed_zero_normal"):
            raise RuntimeError("deliberate verifier failure")
        return verify_claims(world, claims, key)

    with patch.object(calibration, "verify_claims", side_effect=fail_first):
        assert calibration._replication(world, case, 7, 0, events.append) == 1
    batches = [event for event in events if event["kind"] == "batch"]
    assert [event["status"] for event in batches] == ["failed", "complete"]
    assert "deliberate verifier failure" in batches[0]["error"]
    assert len([event for event in events if event["kind"] == "batch_started"]) == 2
    summary = calibration._summarize(batches, 2)
    assert summary["failed"] == summary["not_completed"] == 1
    assert summary["empirical_coverage"]["denominator"] == 1


def test_three_slot_reporting_is_conditional_bound_not_fake_duplicated_episode():
    batch = {"status": "complete", "interval": [-0.1, 0.1], "verification": {"covered": True, "verified_nonzero_effect": True, "three_se_exceeded": True}}
    result = calibration._summarize([batch], 1)
    bound = result["conditional_three_slot_union_bound"]
    assert not bound["episode_rate_measured"]
    assert bound["plug_in_upper_bound"] == bound["wilson_upper_endpoint_times_three"] == 1
    assert "adaptive" in bound["scope"]
    empty = calibration._summarize([], 5)
    assert empty["verified_nonzero_false_positive"]["rate"] is None
    assert empty["conditional_three_slot_union_bound"]["plug_in_upper_bound"] is None


def test_boundary_micro_sensor_really_has_zero_mass_and_positive_values():
    world, _ = load_world("microecology", 7)
    case = calibration.null_cases("microecology")[0]
    assert world.run(case["control"])["values"][2][0] == 0
    samples = [world.run(case["control"], noise_key="boundary-check-%d" % i)["values"][2][0] for i in range(40)]
    assert 5 < samples.count(0) < 35
    assert all(value >= 0 for value in samples)
    # This point mass violates the exact-Gaussian reference assumptions.
    assert sum(samples) > 0


def test_query_wrapper_budget_and_exceptions_keep_attempt_counts_honest():
    events = []
    world, case = _tracked_ising(events)
    world.deadline = time.monotonic() - 1
    with pytest.raises(calibration.CalibrationBudgetExceeded):
        world.run(case["control"], noise_key="must-not-run")
    assert not events
    world.deadline = time.monotonic() + 10
    with patch.object(world.world, "run", side_effect=ValueError("deliberate sensor failure")):
        with pytest.raises(ValueError, match="sensor failure"):
            world.run(case["control"], noise_key="failure")
    assert [event["state"] for event in events] == ["started", "failed"]
    assert all(event["world_seed"] == 7 for event in events)


@pytest.mark.parametrize("kwargs", [{"names": []}, {"names": ["ising_spin", "ising_spin"]}, {"names": ["unknown"]}, {"repetitions": 301}, {"repetitions": True}, {"workers": 0}, {"workers": 5}, {"max_seconds": float("inf")}, {"max_seconds": -1}, {"cpu_seconds_per_world": 0}])
def test_calibration_rejects_unbounded_invalid_work_before_spawning(kwargs):
    arguments = dict(names=["ising_spin"], repetitions=1, max_seconds=5, cpu_seconds_per_world=3, workers=1)
    arguments.update(kwargs)
    with pytest.raises(ValueError):
        calibration.calibrate(**arguments)


def test_real_process_smoke_checks_all_four_seeds_then_accounts_every_query_and_batch():
    report = calibration.calibrate(["ising_spin", "microecology"], repetitions=2, max_seconds=20, cpu_seconds_per_world=8, workers=2)
    assert report["status"] == "complete"
    assert report["operator_only"] and report["source_stable"]
    assert report["reference_formulas"]["gaussian_three_se_reference_only"] == pytest.approx(0.019942126131992522)
    for row in report["worlds"]:
        expected_preflight = 16 if row["environment"] == "microecology" else 8
        expected_calls = expected_preflight + 2 * 48
        assert row["total_query_counts"] == {"attempted": expected_calls, "completed": expected_calls, "failed": 0, "incomplete": 0}
        assert sum(row["planned_query_counts"].values()) == expected_calls
        assert len(row["preflight"]) == expected_preflight // 2
        assert {entry["world_seed"] for entry in row["preflight"]} == set(calibration.DEVELOPMENT_SEEDS)
        assert row["preflight_complete"]
        assert len(row["batch_attempts"]) == len(row["batches"]) == 4
        assert not row["failures"] and not row["pending_queries"]
        for summary in row["summary"].values():
            assert summary["planned"] == summary["attempted"] == summary["completed"] == 2
            assert summary["failed"] == summary["not_completed"] == 0
    json.dumps(report, allow_nan=False)


def test_short_deadline_returns_explicit_incomplete_denominators_and_stops_workers():
    started = time.monotonic()
    report = calibration.calibrate(["ising_spin", "heat_transport"], repetitions=300, max_seconds=0.01, cpu_seconds_per_world=8, workers=1)
    assert time.monotonic() - started < 5
    assert report["status"] == "partial_or_failed"
    for row in report["worlds"]:
        assert row["status"] != "complete"
        assert row["failures"]
        for summary in row["summary"].values():
            assert summary["not_completed"] > 0
            assert summary["empirical_coverage"]["denominator"] == summary["completed"]
        counts = row["total_query_counts"]
        assert counts["attempted"] == counts["completed"] + counts["failed"] + counts["incomplete"]


def test_module_is_python38_syntax_and_does_not_change_the_verifier():
    ast.parse(Path(calibration.__file__).read_text(), feature_version=(3, 8))
    assert calibration.CONFIRMATION_REPLICATES == 8
    assert calibration.verify_claims is verify_claims
