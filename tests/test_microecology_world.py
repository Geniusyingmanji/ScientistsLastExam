"""Scientific, transactional and evidence-boundary checks for the first world."""
import copy
import json
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest

from sle.microecology_demo import INITIAL, run_demo, schedules
from sle.microecology_kernel import A, B, C, X, Y, Z, Mechanism, MicroecologyKernel
from sle.microecology_lab import MicroecologyLab
from sle.microecology_verification import validate_claims
from sle.world_protocol import EventLog, InvalidAction, digest
from sle.world_session import WorldSession, replay_report


def act(session, operation, arguments=None, request_id=None):
    return session.step({"request_id": request_id or "test-%d" % (session.steps + 1),
                         "operation": operation, "arguments": arguments or {}})


def create(lab, initial=None):
    return lab.execute("create", initial or copy.deepcopy(INITIAL))["vessel_id"]


def simple_claim(**updates):
    value = {"id": "an-unlisted-numerical-proposition", "statement": "A grows more after an extra nutrient pulse.",
             "initial": copy.deepcopy(INITIAL), "control": [],
             "treatment": [{"at_h": 16, "operation": "feed", "arguments": {"amount_mmol": 0.02}}],
             "readout": {"species": "A", "time_h": 24}, "expected_difference": [0.05, 1.0], "replicates": 4}
    value.update(updates)
    return value


@pytest.mark.parametrize("seed", [0, 7, 42])
def test_numerical_solution_is_nonnegative_conservative_and_cross_solver_consistent(seed):
    lab = MicroecologyLab(seed)
    handle = create(lab)
    start = lab.vessels[handle].state.copy()
    reference = MicroecologyKernel(lab.kernel.mechanism, method="Radau", rtol=1e-10, atol=1e-12)
    expected = reference.advance(start, 48, 30)
    actual = lab.kernel.advance(start, 48, 30)
    assert actual.min() >= 0
    assert abs(actual.sum() - start.sum()) < 1e-9
    np.testing.assert_allclose(actual, expected, rtol=2e-6, atol=2e-8)


def test_extinct_species_do_not_spontaneously_appear_and_no_food_cannot_create_carbon():
    lab = MicroecologyLab(9)
    initial = copy.deepcopy(INITIAL)
    initial.update(nutrient=0)
    initial["biomass"].update(B=0, C=0)
    handle = create(lab, initial)
    lab.execute("advance", {"hours": 48})
    state = lab.vessels[handle].state
    assert state[B] == state[C] == state[X] == state[Y] == state[Z] == 0
    assert 0 < state[A] < INITIAL["biomass"]["A"]
    assert abs(lab.carbon_residual()) < 1e-10


def test_sampling_filtering_transfer_feed_and_depletion_account_for_all_material():
    lab = MicroecologyLab(7)
    source, target = create(lab), create(lab)
    lab.execute("advance", {"hours": 12})
    sample = lab.execute("sample", {"vessel_id": source, "volume_ml": 1, "cell_free": True})
    assert lab.vessels[source].volume_ml == 9
    assert np.all(lab.vessels[sample["vessel_id"]].state[[A, B, C]] == 0)
    assert sample["lineage"]["source_id"] == source
    before = lab.vessels[target].state.copy()
    source_state = lab.vessels[source].state.copy()
    lab.execute("transfer", {"source_id": source, "target_id": target, "volume_ml": 2})
    source_state[[A, B, C]] = 0
    np.testing.assert_allclose(lab.vessels[target].state, 0.8 * before + 0.2 * source_state)
    lab.execute("feed", {"vessel_id": target, "amount_mmol": 0.01})
    lab.execute("deplete", {"vessel_id": target, "channel": "peak-01", "fraction": 0.7})
    lab.execute("advance", {"hours": 4})
    assert lab.time_h == 16
    assert abs(lab.carbon_residual()) < 1e-10


def test_measurements_do_not_advance_or_perturb_dynamics_and_repeats_have_new_noise():
    first, second = MicroecologyLab(7), MicroecologyLab(7)
    left, right = create(first), create(second)
    readings = [first.execute("measure", {"vessel_id": left, "instrument": "counts"}) for _ in range(10)]
    assert first.time_h == 0
    assert len({r["observation_id"] for r in readings}) == 10
    assert len({r["values"]["A"] for r in readings}) > 1
    first.execute("advance", {"hours": 24})
    second.execute("advance", {"hours": 24})
    np.testing.assert_array_equal(first.vessels[left].state, second.vessels[right].state)


def test_global_clock_and_partitioned_integration_agree():
    lab, other = MicroecologyLab(7), MicroecologyLab(7)
    one, two = create(lab), create(lab)
    reference = create(other)
    for _ in range(12):
        lab.execute("advance", {"hours": 2})
    other.execute("advance", {"hours": 24})
    np.testing.assert_array_equal(lab.vessels[one].state, lab.vessels[two].state)
    np.testing.assert_allclose(lab.vessels[one].state, other.vessels[reference].state, rtol=1e-7, atol=1e-9)


@pytest.mark.parametrize("operation,args", [
    ("advance", {"hours": float("nan")}),
    ("advance", {"hours": -1}),
    ("advance", {"hours": True}),
    ("sample", {"vessel_id": "vessel-0001", "volume_ml": 10, "cell_free": False}),
    ("sample", {"vessel_id": "vessel-0001", "volume_ml": 1, "cell_free": 1}),
    ("deplete", {"vessel_id": "vessel-0001", "channel": "inhibitor", "fraction": 1}),
    ("feed", {"vessel_id": "vessel-0001", "amount_mmol": -1}),
    ("transfer", {"source_id": "vessel-0001", "target_id": "vessel-0001", "volume_ml": 1}),
])
def test_invalid_actions_do_not_mutate_world(operation, args):
    lab = MicroecologyLab(7)
    handle = create(lab)
    before = lab.vessels[handle].state.copy()
    with pytest.raises(InvalidAction):
        lab.execute(operation, args)
    np.testing.assert_array_equal(lab.vessels[handle].state, before)
    assert lab.time_h == 0 and lab.vessels[handle].volume_ml == 10


def test_integration_failure_rolls_back_all_vessels_without_charging():
    session = WorldSession(7)
    act(session, "create", INITIAL)
    act(session, "create", INITIAL)
    original = session.lab.kernel.advance
    calls = []

    def fail_second(*args):
        calls.append(1)
        if len(calls) == 2:
            raise RuntimeError("PRIVATE_STATE_SECRET")
        return original(*args)

    before = [v.state.copy() for v in session.lab.vessels.values()]
    with patch.object(session.lab.kernel, "advance", side_effect=fail_second):
        result = act(session, "advance", {"hours": 12})
    assert result == {"ok": False, "error": "environment_failure"}
    assert session.spent == 20 and session.lab.time_h == 0
    assert "PRIVATE_STATE_SECRET" not in json.dumps(session.report())
    for prior, vessel in zip(before, session.lab.vessels.values()):
        np.testing.assert_array_equal(prior, vessel.state)


def test_request_retry_is_idempotent_and_cannot_change_payload():
    session = WorldSession(7)
    first = act(session, "create", INITIAL, "prepare")
    assert act(session, "create", INITIAL, "prepare") == first
    assert session.spent == 10 and session.steps == 1 and len(session.lab.vessels) == 1
    assert act(session, "inventory", {}, "prepare")["error"] == "request_id_conflict"


def test_budget_rejection_does_not_consume_experiment_or_mutate_time():
    session = WorldSession(7, budget=10)
    act(session, "create", INITIAL)
    response = act(session, "advance", {"hours": 1})
    assert response["error"] == "experiment_budget_exceeded"
    assert session.lab.time_h == 0 and session.spent == 10
    assert act(session, "inventory")["ok"]


def test_public_boundary_hides_recipe_parameters_and_channel_semantics():
    session = WorldSession(923781)
    act(session, "create", INITIAL)
    act(session, "measure", {"vessel_id": "vessel-0001", "instrument": "chemistry"})
    public = json.dumps(session.report())
    for token in ("923781", "operator_recipe", "uptake_a", "inhibition_c", "crossfeed", '"inhibitor"', '"waste"'):
        assert token not in public
    assert session.report(private=True)["operator_recipe"]["seed"] == 923781


def test_fresh_confirmation_keeps_mechanism_and_mapping_but_has_new_measurement_noise():
    lab = MicroecologyLab(7)
    fresh = lab.fresh("confirmation-test")
    a, b = create(lab), create(fresh)
    assert fresh.kernel.mechanism == lab.kernel.mechanism and fresh._channels == lab._channels
    assert lab.execute("measure", {"vessel_id": a, "instrument": "counts"})["values"] != fresh.execute("measure", {"vessel_id": b, "instrument": "counts"})["values"]


def test_unlisted_claim_and_its_opposite_are_evaluated_from_new_experiments():
    session = WorldSession(7)
    positive = simple_claim()
    negative = simple_claim(id="opposite", expected_difference=[-1, -0.05])
    response = act(session, "commit", {"claims": [positive, negative]})
    assert response["ok"]
    assert [r["status"] for r in response["verification"]["results"]] == ["prediction_supported", "prediction_refuted"]
    assert session.lab.time_h == 0 and not session.lab.vessels
    assert act(session, "create", INITIAL)["error"] == "exploration_closed"
    assert act(session, "commit", {"claims": [negative]})["error"] == "exploration_closed"
    assert act(session, "interpret", {"claim_sha256": "wrong", "text": "test"})["error"] == "claim_binding_mismatch"
    assert act(session, "interpret", {"claim_sha256": response["claim_sha256"], "text": "The positive effect was supported; the opposite was refuted."})["ok"]
    assert session.state == "completed"
    assert replay_report(session.report(private=True))["status"] == "exact_replay_passed"


@pytest.mark.parametrize("change", [
    {"readout": {"species": [], "time_h": 24}},
    {"replicates": True},
    {"expected_difference": [0.1, 0.1]},
    {"evidence_ids": ["invented-observation"]},
    {"treatment": [{"at_h": 25, "operation": "feed", "arguments": {"amount_mmol": 0.01}}]},
    {"treatment": [{"at_h": 10, "operation": "execute_python", "arguments": {"code": "1"}}]},
])
def test_invalid_claims_are_rejected_before_freeze(change):
    session = WorldSession(7)
    response = act(session, "commit", {"claims": [simple_claim(**change)]})
    assert not response["ok"]
    assert session.state == "exploring" and session.claims is None


def test_confirmation_budget_checked_before_freeze():
    session = WorldSession(7, confirmation_budget=1)
    response = act(session, "commit", {"claims": [simple_claim()]})
    assert response["error"] == "confirmation_budget_exceeded" and session.state == "exploring"


def test_confirmation_cost_handles_long_wait_and_fractional_schedule():
    session = WorldSession(7)
    claim = simple_claim(readout={"species": "A", "time_h": 96},
                         treatment=[{"at_h": 12.5, "operation": "feed", "arguments": {"amount_mmol": .01}}],
                         expected_difference=[-1, 1])
    _, expected = validate_claims([claim])
    response = act(session, "commit", {"claims": [claim]})
    assert response["ok"] and response["verification"]["charged_units"] == expected


def test_evidence_replay_detects_tampering_and_source_changes():
    session = WorldSession(7)
    act(session, "create", INITIAL)
    act(session, "advance", {"hours": 8})
    act(session, "measure", {"vessel_id": "vessel-0001", "instrument": "counts"})
    report = session.report(private=True)
    assert replay_report(report)["status"] == "exact_replay_passed"
    corrupt = copy.deepcopy(report)
    corrupt["events"][-1]["payload"]["observation"]["values"]["A"] += 1
    with pytest.raises(ValueError):
        replay_report(corrupt)
    with patch("sle.world_session.source_binding", return_value={}):
        with pytest.raises(ValueError, match="source_and_runtime"):
            replay_report(report)


@pytest.fixture(scope="module")
def completed_demo():
    session = WorldSession(7)
    return session, run_demo(session)


def test_complete_public_screening_demo_and_c_dependent_rescue(completed_demo):
    session, demo = completed_demo
    results = {r["claim_id"]: r for r in demo["verification"]["results"]}
    assert session.state == "completed"
    assert demo["model_api_calls"] == 0
    assert results["C-rescue"]["mean_difference"] > .3
    assert results["A-response"]["mean_difference"] > .3
    assert abs(results["C-absent-control"]["mean_difference"]) < .015
    assert results["deliberately-wrong-direction"]["status"] == "prediction_refuted"
    assert all(r["status"] == "prediction_supported" for name, r in results.items() if name != "deliberately-wrong-direction")
    assert abs(session.lab.carbon_residual()) < 1e-9
    assert replay_report(session.report(private=True))["status"] == "exact_replay_passed"


def test_dynamics_show_a_temporal_lag_not_an_instantaneous_population_jump(completed_demo):
    _, demo = completed_demo
    selected = demo["traces"]["remove-" + demo["selected_channel"]]
    control = demo["traces"]["ABC"]
    at8 = next(i for i, row in enumerate(control) if row["time_h"] == 8)
    at24 = next(i for i, row in enumerate(control) if row["time_h"] == 24)
    assert abs(selected[at8]["counts"]["A"] - control[at8]["counts"]["A"]) < .02
    assert selected[at24]["counts"]["A"] - control[at24]["counts"]["A"] > .3


def test_output_directory_is_never_overwritten(tmp_path):
    from argparse import Namespace
    from sle.world_cli import command
    sentinel = tmp_path / "public-report.json"
    sentinel.write_text("keep this")
    with pytest.raises(ValueError, match="already exists"):
        command(Namespace(world_command="demo", output_dir=str(tmp_path)))
    assert sentinel.read_text() == "keep this"


def test_forecast_interval_score_penalizes_width_and_misses():
    from sle.microecology_verification import interval_score
    assert interval_score(-.01, .01, 0) == pytest.approx(.02)
    assert interval_score(-100, 100, 0) == 200
    assert interval_score(-.01, .01, .1) == pytest.approx(1.82)


def test_forecast_is_frozen_scored_and_replayable_separately_from_effect_band():
    session = WorldSession(1234)
    claim = simple_claim(expected_difference=[-100, 100],
                         forecast={"coverage": 0.9, "interval": [-.01, .01]})
    response = act(session, "commit", {"claims": [claim]})
    assert response["ok"]
    result = response["verification"]["results"][0]
    assert result["status"] == "prediction_supported"  # Wide legacy band is not forecast quality.
    assert result["effect_band_width"] == 200
    forecast = result["forecast_evaluation"]
    assert not forecast["covered"] and forecast["interval_score"] > forecast["width"]
    assert forecast["target"] == "mean_treatment_minus_control_across_declared_sensor_replicates"
    assert replay_report(session.report(private=True))["status"] == "exact_replay_passed"


@pytest.mark.parametrize("forecast", [
    {"coverage": .95, "interval": [0, 1]},
    {"coverage": .9, "interval": [1, 0]},
    {"coverage": .9, "interval": [0, float("nan")]},
    {"coverage": .9, "interval": [0, 1], "extra": 1},
])
def test_invalid_forecast_is_rejected_before_commit(forecast):
    session = WorldSession()
    result = act(session, "commit", {"claims": [simple_claim(forecast=forecast)]})
    assert not result["ok"] and session.state == "exploring"
