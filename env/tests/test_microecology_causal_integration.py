"""Offline integration for the experimental world; no model API or code execution."""

from copy import deepcopy
import itertools
import json
import math
from types import SimpleNamespace

import numpy as np
import pytest
from scipy.special import ndtr

from env import campaign, prospective_runner
from env.analysis_api import PROTOCOL as SNAPSHOT_PROTOCOL, contract as snapshot_contract
from env.claim_semantics import claim_eligibility, policy_description
from env.microecology_causal.calibrate import DEVELOPMENT_SEEDS
from env.presentation_profiles import present_problem
from env.registry import ENVIRONMENTS, EXPERIMENTAL_ENVIRONMENTS, load_world
from env.runner import run_episode
from env.scoring import canonical_hash, score_contract, validate_submission, verify_claims
from env.task_profiles import TASK_PROFILE_NAMES, get_task_profile


NAME = "microecology_causal"


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def fail(*args, **kwargs):
        pytest.fail("integration tests must not access the network")
    monkeypatch.setattr("socket.socket", fail)
    monkeypatch.setattr("socket.create_connection", fail)


def specimen():
    return {"initial": {"A": .1, "B": .1, "C": .1, "nutrient": 4},
            "times_h": [0, 12, 12.5, 13, 24], "events": []}


def assembled_problem(world, task):
    result = world.describe()
    result["task_profile"] = get_task_profile(task, NAME)
    result["score_contract"] = score_contract()
    return present_problem(result, "full_description", environment=NAME)


def assert_no_private_labels(public, world):
    text = json.dumps(public)
    for forbidden in (*world.operator_strata, "operator_sampling_stratum", "world_seed",
                      "panel_seed", "confirmation_key", "_structure", "_kernel"):
        assert forbidden not in text


def test_registry_and_all_public_tasks_keep_the_structural_menu_private():
    assert ENVIRONMENTS[-1] == NAME and len(ENVIRONMENTS) == 8
    assert NAME in EXPERIMENTAL_ENVIRONMENTS
    worlds = [load_world(NAME, seed)[0] for seed in DEVELOPMENT_SEEDS]
    assert {world.operator_stratum() for world in worlds} == set(worlds[0].operator_strata)
    for task in TASK_PROFILE_NAMES:
        descriptions = [assembled_problem(world, task) for world in worlds]
        assert all(value == descriptions[0] for value in descriptions)
        assert NAME in descriptions[0]["task_profile"]["applicable_environments"]
        assert "experimental" in descriptions[0]["version"]
        assert_no_private_labels(descriptions[0], worlds[0])
    world, baseline = load_world(NAME, 7)
    predicted = baseline([], world.validate(specimen()))
    assert np.asarray(predicted).shape == (5, 7)
    assert np.isfinite(predicted).all()


def test_freeze_reserves_actual_development_seeds_and_balances_private_strata(monkeypatch):
    # Only exercise instance selection/panel schema for synthetic fixture seeds;
    # no outcomes are generated or added to scientific development calibration.
    choices = itertools.chain(DEVELOPMENT_SEEDS, range(100000, 101000))
    monkeypatch.setattr(campaign.secrets, "randbelow", lambda limit: next(choices))
    manifest = campaign.create_manifest("causal-integration", [NAME], instances=6,
                                        rounds=4, exploration_rounds=2,
                                        task_profile="mechanism_discrimination",
                                        balanced_strata=[NAME], analysis_protocol=SNAPSHOT_PROTOCOL)
    assert set(DEVELOPMENT_SEEDS) <= set(manifest["reserved_development_world_seeds"])
    assert manifest["analysis_contract"] == snapshot_contract()
    assert manifest["sampling_policy"]["balanced_strata_environments"] == [NAME]
    rows = manifest["instances"]
    assert len({row["world_seed"] for row in rows}) == 6
    labels = load_world(NAME, 7)[0].operator_strata
    assert [row["operator_sampling_stratum"] for row in rows] == list(labels) * 2
    for row in rows:
        assert row["world_seed"] not in DEVELOPMENT_SEEDS
        world, _ = load_world(NAME, row["world_seed"])
        assert world.operator_stratum() == row["operator_sampling_stratum"]
        for kind, expected in row["panel_hashes"].items():
            assert canonical_hash(world.panel(row["panel_seed"], kind, manifest["limits"]["panel_count"])) == expected
        assert_no_private_labels(assembled_problem(world, row["task_profile"]), world)
    assert manifest["planned_max_api_attempts"] == 24


def test_new_world_does_not_silently_enter_unaudited_apparatus_presentation():
    with pytest.raises(ValueError, match="not audited"):
        campaign.create_manifest("causal-unsupported-presentation", [NAME], instances=1,
                                 presentation_profile="apparatus_only")


def test_cli_freeze_accepts_explicit_experimental_selection(tmp_path, monkeypatch, capsys):
    from env.__main__ import main
    path = tmp_path / "manifest-private.json"
    monkeypatch.setattr("sys.argv", ["env", "freeze", "--cohort", "causal-cli-fixture",
                                   "--environments", NAME, "--instances", "3", "--rounds", "4",
                                   "--exploration-rounds", "2", "--balanced-strata", NAME,
                                   "--task-profile", "regime_transfer", "--output", str(path)])
    main()
    manifest = json.loads(path.read_text())
    output = json.loads(capsys.readouterr().out)
    assert output["episodes"] == 3 and output["max_api_attempts"] == 12
    assert manifest["environments"] == [NAME]
    assert manifest["task_profile"]["name"] == "regime_transfer"
    assert {row["operator_sampling_stratum"] for row in manifest["instances"]} == set(load_world(NAME, 7)[0].operator_strata)


def submission(row):
    control = specimen()
    treatment = deepcopy(control)
    treatment["events"] = [{"time_h": 12, "deplete": {"channel": "peak-01", "fraction": .8}}]
    return {"predictor_code": "def predict(spec):\n    return [[0.0]*7 for _ in spec['times_h']]\n",
            "claims": [{"id": "delayed-response", "statement": "Paired change after fraction removal.",
                        "control": control, "treatment": treatment, "readout": {"row": row, "channel": "A"},
                        "interval": [-.01, .01], "evidence_ids": ["obs-0001"],
                        "scope": "Only the stated preparation, history and readout time."}],
            "explanation": "Integration fixture; no scientific discovery assertion."}


def test_claim_commit_rejects_immediate_effect_accepts_delayed_and_requires_matched_time():
    world, _ = load_world(NAME, 46)
    records = [{"id": "obs-0001"}]
    for row in (1, 2):
        with pytest.raises(ValueError, match="readout_too_soon_after_event"):
            validate_submission(submission(row), world, records)
    value = validate_submission(submission(3), world, records)
    policy = policy_description()["minimum_lag"]
    assert policy[NAME] == policy["microecology"]
    assert claim_eligibility(NAME, value["claims"][0]["control"], value["claims"][0]["treatment"],
                             {"row": 3, "channel": "A"}, "times_h")["eligible"]
    unmatched = submission(3)
    unmatched["claims"][0]["treatment"]["times_h"][3] = 14
    with pytest.raises(ValueError, match="unmatched_readout_coordinate"):
        validate_submission(unmatched, world, records)
    report = verify_claims(world, submission(1)["claims"], "causal-integration-ineligible")
    assert report["score"] == 0 and report["verified_nonzero_effects"] == 0
    assert report["claims"][0]["eligibility"]["reason"] == "readout_too_soon_after_event"


def test_prospective_noise_adapter_has_the_valid_clipping_bias_bound():
    world, _ = load_world(NAME, 7)
    contract = prospective_runner._observation_contract(world)
    original = prospective_runner._observation_contract(load_world("microecology", 7)[0])
    sigma = np.asarray(contract["noise_std"])
    bound = np.asarray(contract["noise_mean_bias_bound"])
    assert bound == pytest.approx(sigma / math.sqrt(2 * math.pi))
    assert contract["noise_mean_bias_bound"] == original["noise_mean_bias_bound"]
    # Independent analytic mean of max(x + Gaussian, 0), for nonnegative x.
    x = np.linspace(0, 12, 101)[:, None] * sigma
    z = x / sigma
    bias = sigma * np.exp(-z*z/2) / math.sqrt(2*math.pi) - x * ndtr(-z)
    assert np.all(bias >= -1e-16) and np.all(bias <= bound + 1e-16)
    assert bias[0] == pytest.approx(bound)
    # The actual public readout at a zero-carbon preparation attains this bound
    # in expectation; fixed independent keys make this regression reproducible.
    zero = {"initial": dict.fromkeys(("A", "B", "C", "nutrient"), 0), "times_h": [0]}
    samples = np.asarray([world.run(zero, noise_key="clip-check-%d" % index)["values"][0]
                          for index in range(512)])
    assert np.all(samples >= 0)
    assert np.all(np.abs(samples.mean(axis=0) - bound) < 6 * sigma / math.sqrt(len(samples)))
    with pytest.raises(ValueError, match="not been approved"):
        prospective_runner._observation_contract(SimpleNamespace(name="unreviewed-world"))


def test_prospective_real_world_source_observation_and_receipt_replay(tmp_path):
    task = prospective_runner.ProspectiveTask(NAME, 46, tmp_path / "prospective")
    public = task.describe()
    expected_contract = prospective_runner._observation_contract(load_world(NAME, 46)[0])
    assert public["observation_contract"] == expected_contract
    assert_no_private_labels(public, load_world(NAME, 46)[0])
    record = task.observe_source(specimen())
    assert np.asarray(record["observation"]["values"]).shape == (5, 7)
    bundle = json.loads((task.directory / "bundle-private.json").read_text())
    assert bundle["usage"]["experiment_attempts"] == 1
    assert bundle["usage"]["predictor_attempts"] == 0
    receipt = json.loads((task.directory / "receipts" / "000001.json").read_text())
    assert receipt["payload"]["public_contract"] == expected_contract
    assert task.close()["status"] == "incomplete"
    assert prospective_runner.verify_directory(task.directory)["replayed_tests"] == 0


class OfflineClient:
    def __init__(self, replies):
        self.replies, self.prompts = iter(replies), []
        self.config = SimpleNamespace(model="offline-fixture", timeout_seconds=1)
        self.last_usage = self.total_usage = {}
        self.last_response_metadata = {"provider_reported_models": ["offline-fixture"]}
        self.last_stop_reason, self.last_transport_error = "stop", None

    def complete(self, prompt, system=None):
        self.prompts.append(json.loads(prompt))
        return json.dumps(next(self.replies))

    def transport_summary(self):
        return {"attempts": len(self.prompts), "automatic_retries": 0}


class OfflineAnalysis:
    def __init__(self, seconds):
        self.remaining, self.problem, self.closed = seconds, None, False

    def run(self, code, problem, records, history):
        self.problem = deepcopy(problem)
        return {"ok": True, "result": {"observations": len(records)}}

    def close(self):
        self.closed = True


def test_frozen_panels_to_real_runner_public_prompt_analysis_and_verification(tmp_path):
    # No candidate code or model API is invoked: prediction is an explicit
    # test-only implementation of the committed zero-output fixture.
    manifest = campaign.create_manifest("causal-runner-fixture", [NAME], instances=1,
                                        rounds=4, exploration_rounds=2,
                                        task_profile="mechanism_discrimination")
    instance = manifest["instances"][0]
    value = submission(3)
    value["claims"] = []
    client = OfflineClient([
        {"note": "Obtain a public record", "experiments": [specimen()]},
        {"note": "Inspect records", "analyze": {"code": "result = len(records)"}},
        {"note": "Commit fixture", "submit": value},
    ])
    analysis = OfflineAnalysis(2)
    def predict(path, query, seconds):
        assert path.read_text() == value["predictor_code"]
        return [[0.0] * 7 for _ in query["times_h"]]
    result = run_episode(instance, manifest["limits"], tmp_path, client,
                         analysis_factory=lambda seconds: analysis, predict_fn=predict)
    assert result["model_completed"] and result["experiment_count"] == 1
    assert analysis.closed and analysis.problem == client.prompts[0]["problem"]
    world, _ = load_world(NAME, instance["world_seed"])
    assert_no_private_labels(analysis.problem, world)
    assert result["task_profile"] == "mechanism_discrimination"
    assert len(result["panels"]["conditions"]) == manifest["limits"]["panel_count"]
    for kind in ("conditions", "interventions"):
        assert all(row["valid"] for row in result["panels"][kind])
        assert canonical_hash([row["spec"] for row in result["panels"][kind]]) == instance["panel_hashes"][kind]
    assert (tmp_path / "submission.json").exists() and (tmp_path / "report.json").exists()
