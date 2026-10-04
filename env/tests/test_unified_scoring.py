"""Scientific invariants of the opt-in common protocol; no API calls."""
from copy import deepcopy
import json
import math
from unittest.mock import patch

import numpy as np
import pytest

from env import scoring as legacy
from env import unified_scoring as scoring
from env.registry import load_world, FRONTIER_ENVIRONMENTS
from env.runner import DEFAULT_LIMITS, run_episode, SYSTEM
from env.tests.test_pilot_protocol import FakeClient, FakeAnalysis

WORLDS = ("microecology", "coupled_oscillators", "reaction_kinetics", "heat_transport",
          "gene_regulation", "ising_spin", "hysteresis_material") + FRONTIER_ENVIRONMENTS


def submission(claims=()):
    return {"predictor_code": "def predict(spec): return []", "claims": list(claims), "explanation": "Test scope."}


def claim(control, treatment, channel, row=0, identifier="c1"):
    return {"id": identifier, "statement": "The stated quantitative contrast.", "control": control,
            "treatment": treatment, "readout": {"row": row, "channel": channel},
            "interval": [-.02, .02], "evidence_ids": ["obs-0001"], "scope": "Only these controls."}


def test_contract_is_detached_and_reports_actual_32_pair_target():
    original = legacy.score_contract()
    contract = scoring.score_contract()
    assert "32 independent" in contract["claims"]
    assert "not a proper scoring rule" in contract["claims"]
    contract["weights"]["claims"] = 1
    assert scoring.WEIGHTS["claims"] == .2
    assert legacy.score_contract() == original
    assert legacy.CONFIRMATION_REPLICATES == 8


@pytest.mark.parametrize("environment", FRONTIER_ENVIRONMENTS)
def test_frontier_claim_validation_is_public_only(environment):
    world, _ = load_world(environment, 9)
    control, treatment = world.panel(27, "interventions", 2)
    item = claim(control, treatment, world.channels[0], row=len(control[world.axis_field])-1)
    # Select the same valid row in both panels (their lengths can differ).
    item["readout"]["row"] = min(len(control[world.axis_field]), len(treatment[world.axis_field]))-1
    if environment == "catalyst_aging":
        item["readout"]["row"] = next(i for i, e in enumerate(control["event_indices"])
                                         if control["events"][e-1]["kind"] == "reaction")
    with patch.object(world, "run", side_effect=AssertionError("hidden simulator called")):
        checked = scoring.validate_submission(submission([item]), world, [{"id": "obs-0001"}])
    assert checked["claims"][0]["readout"] == item["readout"]


def test_ecology_zero_habitat_static_row_is_valid_and_fresh_replicates_independent():
    world, _ = load_world("field_ecology", 9)
    control = world.validate({"habitat_values": [0.], "visits": ["rapid"]})
    treatment = world.validate({"habitat_values": [0.], "visits": ["intensive"]})
    first = claim(control, treatment, world.channels[0])
    first["interval"] = [-1., 1.]
    reverse = dict(deepcopy(first), id="reverse", control=treatment, treatment=control)
    alias = dict(deepcopy(first), id="alias", readout={"row": 0, "channel": "any_visit_detection"})
    checked = scoring.validate_submission(submission([first, reverse, alias]), world, [{"id": "obs-0001"}])
    keys = []
    original = world.run
    def recorded(spec, *, noise_key=None):
        keys.append(noise_key)
        return original(spec, noise_key=noise_key)
    with patch.object(world, "run", side_effect=recorded):
        result = scoring.verify_claims(world, checked["claims"], "confirmation")
    assert len(keys) == len(set(keys)) == 3*32*2
    assert [c["duplicate"] for c in result["claims"]] == [False, True, True]
    assert result["score"] == pytest.approx(result["claims"][0]["score"]/3)
    row = result["claims"][0]
    assert row["replicates"] == 32
    delta = np.asarray(row["replicate_arm_values"]["treatment"])-row["replicate_arm_values"]["control"]
    assert delta == pytest.approx(row["replicate_differences"])
    assert row["standard_error"] == pytest.approx(delta.std(ddof=1)/math.sqrt(32))
    lower, upper = first["interval"]
    assert row["interval_score"] == pytest.approx(upper-lower+20*max(lower-delta.mean(), delta.mean()-upper, 0))
    assert row["mechanism_certified"] is False


def test_frontier_alias_padding_cannot_create_a_claim():
    world, _ = load_world("field_ecology", 9)
    control = {"habitat_values": [0.], "visits": ["rapid"]}
    treatment = {"habitat_values": [0., 1.], "visits": ["rapid", "intensive"]}
    with pytest.raises(ValueError, match="identical_physical"):
        scoring.validate_submission(submission([claim(control, treatment, world.channels[0])]), world, [{"id": "obs-0001"}])


def test_molecular_first_configuration_retained_and_errors_do_not_cancel():
    world, _ = load_world("molecular_forces", 9)
    spec = world.panel(27, "conditions", 1)[0]
    truth = world.run(spec)
    pred = np.asarray(truth["values"])
    pred[0, 0] += world.scales[0]
    pred[1, 0] -= world.scales[0]
    result = scoring.prediction_metrics(pred, truth, world.scales, world=world, spec=spec)
    assert result["scored_rows"] == 4
    assert result["scored_cell_mask"][0][0]
    assert result["normalized_rmse"] == pytest.approx(math.sqrt(2/40))
    assert result["score"] < 11


def test_ecology_zero_habitat_retained():
    world, _ = load_world("field_ecology", 9)
    spec = world.validate({"habitat_values": [0., 1.], "visits": ["rapid", "intensive"]})
    truth = world.run(spec)
    pred = np.asarray(truth["values"])
    pred[0, :] += 1
    result = scoring.prediction_metrics(pred, truth, world.scales, world=world, spec=spec)
    assert result["scored_rows"] == 2
    assert result["normalized_rmse"] == pytest.approx(math.sqrt(.5))


def test_public_clamps_excluded_while_dynamic_unknowns_retained():
    world, _ = load_world("coupled_oscillators", 9)
    spec = world.validate({"times": [0., 1.], "clamp": ["A"], "initial_position": [0., 1., 0., 0.]})
    truth = world.run(spec)
    pred = np.asarray(truth["values"])
    pred[0, :] = 123
    pred[:, [0, 4]] = 123
    result = scoring.prediction_metrics(pred, truth, world.scales, world=world, spec=spec)
    assert result["score"] == 100
    assert result["scored_cells"] == 6


@pytest.mark.parametrize("environment", WORLDS)
def test_runner_explicit_protocol_preserves_blind_freeze_and_full_prediction(environment, tmp_path):
    from env.unified_panels import generate_panel
    world, _ = load_world(environment, 9)
    instance = {"episode_id": "unified-test-"+environment, "environment": environment, "world_seed": 9,
                "panel_seed": 271, "confirmation_key": "private-confirmation", "scoring_protocol": scoring.PROTOCOL}
    instance["panel_hashes"] = {kind: scoring.canonical_hash(generate_panel(world, 271, kind, 1))
                               for kind in ("conditions", "interventions")}
    client = FakeClient([{"note": "Freeze.", "submit": submission()}])
    limits = dict(DEFAULT_LIMITS, rounds=1, exploration_rounds=0, panel_count=1, wall_seconds=300)
    def predict(path, spec, seconds):
        assert (tmp_path/"submission.json").exists()
        assert not client.prompts[0]["problem"].get("clean_truth")
        return world.run(spec)["values"]
    with patch("env.runner.load_world", return_value=(world, lambda records, spec: world.run(spec)["values"])), patch("env.runner.source_digest", return_value="test"):
        report = run_episode(instance, limits, tmp_path, client, analysis_factory=FakeAnalysis, predict_fn=predict)
    assert report["status"] == "completed", report
    assert report["score"] == 80
    assert report["scoring_protocol"] == scoring.PROTOCOL
    assert report["subscores"] == {"conditions": 100., "interventions": 100., "claims": 0.}
    assert client.prompts[0]["problem"]["submission_contract"]["claim_replicates_per_arm"] == 32
    text = json.dumps(client.prompts)
    for private in ("world_seed", "panel_seed", "private-confirmation", "clean_truth"):
        assert private not in text
    assert "mean of eight fresh" in SYSTEM  # legacy system byte content retained


def test_unified_invalid_batch_collects_no_partial_observations(tmp_path):
    world, _ = load_world("field_ecology", 9)
    client = FakeClient([{"note": "Batch", "experiments": [
        {"habitat_values": [0.], "visits": ["rapid"]}, {"bad": "spec"}]},
        {"note": "Finish", "submit": submission()}])
    instance = {"episode_id": "batch-test", "environment": world.name, "world_seed": 9,
                "panel_seed": 17, "confirmation_key": "key", "scoring_protocol": scoring.PROTOCOL}
    with patch("env.runner.load_world", return_value=(world, lambda records, spec: world.run(spec)["values"])):
        report = run_episode(instance, dict(DEFAULT_LIMITS, rounds=2, exploration_rounds=1, panel_count=1), tmp_path,
                             client, analysis_factory=FakeAnalysis, predict_fn=lambda path, spec, seconds: world.run(spec)["values"])
    assert report["experiment_count"] == 0
    assert report["history"][0]["outcome"] == "invalid_action"
    assert report["status"] == "completed"


def test_unified_snapshot_submission_and_truthful_system(tmp_path, monkeypatch):
    from env.analysis_api import PROTOCOL as SNAPSHOT_PROTOCOL
    from env.tests.test_model_snapshots import _OfflineClient, _PublicFitWorld, _WorkerShim
    world = _PublicFitWorld()
    class Client(_OfflineClient):
        def complete(self, prompt, system):
            self.system = system
            return super().complete(prompt, system)
    client = Client()
    monkeypatch.setattr("env.runner.load_world", lambda *args: (world, lambda records, spec: [[0] for _ in spec["times"]]))
    monkeypatch.setattr("env.runner.source_digest", lambda: "test-source")
    monkeypatch.setattr("env.unified_panels.public_panel_domain", lambda environment: {"fixture": "public test"})
    instance = {"episode_id": "unified-snapshot", "environment": world.name, "world_seed": 9,
                "panel_seed": 271, "confirmation_key": "private", "scoring_protocol": scoring.PROTOCOL,
                "analysis_protocol": SNAPSHOT_PROTOCOL}
    limits = dict(DEFAULT_LIMITS, rounds=4, exploration_rounds=3, wall_seconds=300, verification_reserve_seconds=0, panel_count=1)
    def predict(path, spec, seconds):
        namespace = {}
        exec(path.read_text(), namespace)  # Only the fixed offline test program.
        return namespace["predict"](spec)
    result = run_episode(instance, limits, tmp_path, client, analysis_factory=_WorkerShim, predict_fn=predict)
    assert result["status"] == "completed"
    assert result["score"] == 80
    assert result["frozen_model_snapshot"]["name"] == "fitted"
    assert result["history"][1]["outcome"] == "analysis_failed"
    assert "32 independent" in client.system
    assert "mean of eight" not in client.system
    assert "must be after t=0" not in client.system
    assert "save_model" in client.system
