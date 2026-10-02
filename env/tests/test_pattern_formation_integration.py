"""Offline tenth-world integration; no model API, candidate execution or depth grade."""
from copy import deepcopy
import json

import numpy as np
import pytest

from env import campaign, presentation_profiles
from env.analysis_api import ModelSnapshots, PROTOCOL as SNAPSHOT_PROTOCOL, contract as snapshot_contract
from env.calibration import _initial, calibrate
from env.claim_calibration import NULL_ENVIRONMENTS, null_cases
from env.claim_semantics import claim_eligibility, policy_description
from env.evidence_packet import AXIS, SPECS, build_packet
from env.presentation_profiles import present_problem
from env.prospective_runner import ProspectiveTask, _observation_contract, verify_directory
from env.registry import ENVIRONMENTS, EXPERIMENTAL_ENVIRONMENTS, load_world
from env.scoring import canonical_hash, prediction_metrics, score_contract, validate_submission, verify_claims
from env.task_profiles import TASK_PROFILE_NAMES, get_task_profile


NAME = "pattern_formation"
PREVIOUS = ("microecology", "coupled_oscillators", "reaction_kinetics", "heat_transport",
            "gene_regulation", "ising_spin", "hysteresis_material", "microecology_causal",
            "orbital_dynamics")


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def fail(*args, **kwargs):
        pytest.fail("pattern integration tests must not access the network")
    monkeypatch.setattr("socket.socket", fail)
    monkeypatch.setattr("socket.create_connection", fail)


def specimen():
    return {"length": 24., "drive": 0., "initial": {"mean": 0., "modes": [
        {"mode": 4, "amplitude": .08, "phase": .5}]}, "times": [0., .125, .25, 1.]}


def submission(row):
    control = specimen()
    treatment = deepcopy(control)
    treatment["initial"]["mean"] = .1
    return {"predictor_code": "def predict(spec):\n    return [[0.0]*16 for _ in spec['times']]\n",
            "claims": [{"id": "reset-contrast", "statement": "Specified paired probe contrast.",
                        "control": control, "treatment": treatment, "readout": {"row": row, "channel": "probe_00"},
                        "interval": [.09, .11], "evidence_ids": ["obs-0001"],
                        "scope": "Fixture only; no mechanism or discovery claim."}],
            "explanation": "Offline integration fixture."}


def test_tenth_experimental_registration_preserves_private_generation_layers():
    assert ENVIRONMENTS == PREVIOUS + (NAME,)
    assert EXPERIMENTAL_ENVIRONMENTS == ("microecology_causal", "orbital_dynamics", NAME)
    worlds = [load_world(NAME, seed)[0] for seed in (7, 46, 1439, 8743)]
    # Preserve the actual unbalanced development cohort, never search for replacements.
    assert [w.operator_stratum() for w in worlds].count("anchored_forcing") == 3
    assert [w.operator_stratum() for w in worlds].count("negative_r0_unforced") == 1
    assert "positive_r0_unforced" not in [w.operator_stratum() for w in worlds]
    for task in TASK_PROFILE_NAMES:
        descriptions = []
        for world in worlds:
            public = world.describe()
            public.update(task_profile=get_task_profile(task, NAME), score_contract=score_contract())
            descriptions.append(present_problem(public, "full_description", environment=NAME))
        assert descriptions == [descriptions[0]] * 4
        encoded = json.dumps(descriptions[0])
        for private in worlds[0].operator_strata + ("q0", "r0", "forcing_mode", "world_seed", "private_parameters"):
            assert private not in encoded
        assert "64-site" in encoded and "No stochastic process" in encoded
    with pytest.raises(ValueError, match="not audited"):
        present_problem(worlds[0].describe(), "apparatus_only", environment=NAME)
    world, baseline = load_world(NAME, 7)
    assert np.asarray(baseline([], world.validate(specimen()))).shape == (4, 16)


def test_explicit_campaign_selection_uses_generic_snapshot_contract_without_execution(monkeypatch):
    choices = iter([7, 46, 1439, 8743, 100001, 100002])
    monkeypatch.setattr(campaign.secrets, "randbelow", lambda bound: next(choices))
    manifest = campaign.create_manifest("pattern-integration", [NAME], instances=1, rounds=4,
                                        exploration_rounds=2, analysis_protocol=SNAPSHOT_PROTOCOL)
    assert manifest["environments"] == [NAME]
    assert manifest["analysis_contract"] == snapshot_contract()
    assert manifest["instances"][0]["world_seed"] == 100001
    assert manifest["sampling_policy"]["balanced_strata_environments"] == []
    assert "operator_sampling_stratum" not in manifest["instances"][0]
    for kind, digest in manifest["instances"][0]["panel_hashes"].items():
        world, _ = load_world(NAME, 100001)
        assert canonical_hash(world.panel(100002, kind, manifest["limits"]["panel_count"])) == digest


@pytest.mark.parametrize("channel", ["probe_%02d" % index for index in range(16)])
def test_claim_resolution_excludes_assignments_and_requires_matched_coordinates(channel):
    control = specimen()
    treatment = deepcopy(control)
    treatment["drive"] = .1
    decide = lambda row: claim_eligibility(NAME, control, treatment, {"row": row, "channel": channel}, "times")
    assert decide(0)["reason"] == "readout_before_temporal_resolution"
    assert decide(1)["reason"] == "readout_before_temporal_resolution"
    assert decide(2)["eligible"] and decide(3)["eligible"]
    treatment["times"][2] += 1e-8
    assert decide(2)["reason"] == "unmatched_readout_coordinate"
    control["times"] = treatment["times"] = np.linspace(0, 60, 33).tolist()
    assert decide(32)["eligible"]
    treatment["times"] = np.linspace(0, 60, 34).tolist()
    assert decide(32)["reason"] == "invalid_public_spec"
    rule = policy_description()["minimum_lag"][NAME]
    assert rule == {"value": .25, "unit": "T", "axis_field": "times", "event_field": None, "event_time_field": None}


def test_known_reset_claim_has_no_credit_and_valid_later_claim_needs_no_hidden_validation(monkeypatch):
    world, _ = load_world(NAME, 7)
    for row, reason in ((0, "post-initial observation"), (1, "readout_before_temporal_resolution")):
        with pytest.raises(ValueError, match=reason):
            validate_submission(submission(row), world, [{"id": "obs-0001"}])
    with monkeypatch.context() as patch:
        patch.setattr(world, "run", lambda *a, **kw: pytest.fail("submission validation must not simulate"))
        assert validate_submission(submission(2), world, [{"id": "obs-0001"}])["claims"]
    report = verify_claims(world, submission(0)["claims"], "pattern-assignment-fixture")
    assert report["score"] == 0 and report["verified_nonzero_effects"] == 0
    assert report["claims"][0]["eligibility"]["reason"] == "readout_before_temporal_resolution"
    assert report["claims"][0]["mean_difference"] == pytest.approx(.1, abs=.006)


def test_public_initial_adapter_and_noise_contract_retain_aliased_probe_assignment(monkeypatch):
    world, _ = load_world(NAME, 7)
    contract = _observation_contract(world)
    assert contract["axis_field"] == "times" and contract["channels"] == list(world.channels)
    assert contract["noise_std"] == [.002] * 16 and contract["noise_mean_bias_bound"] == [0.] * 16
    spec = specimen()
    spec["initial"] = {"mean": 0., "modes": [{"mode": 8, "amplitude": .2, "phase": 0.}]}
    with monkeypatch.context() as patch:
        patch.setattr("env.pattern_formation.kernel.Kernel.trajectory", lambda *a: pytest.fail("known reset must be public-only"))
        assigned = _initial(NAME, spec, world.channels)
    assert np.max(np.abs(assigned)) < 2e-15
    spec["times"] = [0.]
    assert np.max(np.abs(np.asarray(world.run(spec)["values"])[0] - assigned)) < 1e-15
    # Assigned t0 cells never improve a nontrivial prediction score.
    observed = {"axis": [0., 1.], "values": [[100.] * 16, [1.] * 16]}
    metrics = prediction_metrics([[0.] * 16, [1.] * 16], observed, world.scales)
    assert metrics["scored_rows"] == 1 and metrics["score"] == 100.


def test_prospective_receipts_and_packet_preserve_nested_public_controls(tmp_path):
    task = ProspectiveTask(NAME, 7, tmp_path / "prospective-pattern")
    assert task.describe()["observation_contract"]["noise_mean_bias_bound"] == [0.] * 16
    assert not task.describe()["discovery_depth_certified"]
    spec = specimen()
    spec["initial"]["modes"].append({"mode": 8, "amplitude": -.12, "phase": -1.})
    record = task.observe_source(spec)
    assert task.close()["status"] == "incomplete"
    assert verify_directory(task.directory)["replayed_tests"] == 0
    report = {"environment": NAME, "rounds": [{"round": 1, "response": json.dumps({"note": "Source", "experiments": [spec]})}],
              "history": [{"round": 1, "note": "Source", "observations": [record], "outcome": "observed"}],
              "records": [record], "private_parameters": "OPERATOR_CANARY"}
    packet = build_packet(report)
    assert packet["observations"] and "unsupported_top_record" not in packet["gaps"]
    assert "OPERATOR_CANARY" not in json.dumps(packet)
    assert packet["observations"][0]["spec"] == record["spec"]
    assert packet["observations"][0]["observation"] == record["observation"]
    assert AXIS[NAME] == "times"


def test_prospective_numerical_failure_is_terminal_and_not_silently_clipped(tmp_path, monkeypatch):
    task = ProspectiveTask(NAME, 7, tmp_path / "failed-pattern")
    monkeypatch.setattr("env.pattern_formation.kernel.MAX_EVALUATIONS", 0)
    with pytest.raises(RuntimeError, match="RHS work limit"):
        task.observe_source(specimen())
    with pytest.raises(RuntimeError, match="closed"):
        task.observe_source(specimen())
    entries = [json.loads(p.read_text()) for p in sorted((task.directory / "receipts").glob("[0-9]*.json"))]
    finished = [e["payload"] for e in entries if e["kind"] == "observation_attempt_finished"]
    assert len(finished) == 1 and finished[0]["ok"] is False


def test_generic_snapshot_binding_is_inert_and_accepts_pattern_submission(tmp_path):
    store = ModelSnapshots(tmp_path / "snapshots")
    sentinel = tmp_path / "must-not-execute"
    code = "open(" + repr(str(sentinel)) + ", 'w').write('executed')\n" + submission(2)["predictor_code"]
    receipt = store.save_model("pattern-model", "v1", {"scope": "public controls", "mode": 4}, code)
    ref = {k: receipt[k] for k in ("name", "version", "sha256")}
    frozen, binding = store.resolve_submission({"model_snapshot": ref, "claims": [], "explanation": "Snapshot integration only."})
    world, _ = load_world(NAME, 7)
    assert validate_submission(frozen, world, [])["claims"] == []
    assert binding["sha256"] == ref["sha256"] and not sentinel.exists()


def test_generic_calibration_is_explicit_and_does_not_expand_audited_nulls():
    assert NULL_ENVIRONMENTS == PREVIOUS[:7]
    with pytest.raises(ValueError, match="no audited null"):
        null_cases(NAME)
    assert canonical_hash({n: null_cases(n) for n in NULL_ENVIRONMENTS}) == \
        "25b4d2ab981abaa977c02e81cd04120398be3cb60c9f9d023f05291eab3c5e42"
    result = calibrate([NAME], seeds=(7,), panel_count=1, max_seconds=20)
    assert result["status"] == "complete" and len(result["instances"]) == 1
    assert all(m["valid_predictions"] == 2 and m["invalid_predictions"] == 0
               for m in result["summary"][NAME]["methods"].values())


def test_previous_nine_world_scientific_schemas_noise_and_policy_are_unchanged():
    assert canonical_hash({n: {"spec": SPECS[n], "axis": AXIS[n]} for n in PREVIOUS}) == \
        "f47117f8c4ec37e5bcbc9cc99ee27976cf62a5fa0ec6b697056df1ea2e389272"
    assert canonical_hash({n: _observation_contract(load_world(n, 7)[0]) for n in PREVIOUS}) == \
        "4c7c88909d3de294ad5dd6f5694a24dec76d2e428fc6d395e8a35285f496b6a9"
    policy = policy_description()
    policy.pop("protocol")
    policy["minimum_lag"].pop(NAME)
    assert canonical_hash(policy) == "eaddf457c8785075b69f46c7064e01da6e4d4d8529e3af1589d23f882123dc5e"
    expected = ("2361d13d49b27e0cb0371e7f44aea1373c8c8d8ab37bde8a763c2f77e741842c",
        "7cda13cff601e67884a38d56a8e2a96a14c1ede9e626d522172d7e9d58370038",
        "55628e1c1db4fc3df9e8bca459657a72a1e4da28ef0c556680f382bff3ac1acf",
        "f8c09f372cefa3db105f6d843c4a77cb61ec11cbe7b32c422ee7d907ec19edd8",
        "e7a14b963b2f936e463c016f0768ad74b00478c7963ef14419239edb89cdb77e",
        "4101a4788fd43ae618092f02ac45a41fbbe01ff45a2e7dc446327f0cb4ed8572",
        "eb5fb9f07b7e668044922f33d483c83408ac7adca655cb8e585fb7856617e01e",
        "41c81f366b4ae3757f32f8145bfefd150251334dde4b73099ed0ae42c69ef5b7",
        "1c77f6f7f689b0b5dd6db7bd364618cad33513973d0eecf041a216667b988c80")
    assert tuple(canonical_hash(load_world(n, 7)[0].describe()) for n in PREVIOUS) == expected


def test_metadata_revision_is_deliberate_and_old_score_scientific_contract_reconstructs():
    previous = {"open_discovery": "73f62e5b9ab0d1fde2c8dee12e78d90f476f25998e8f755d0e25865da1aa696d",
                "mechanism_discrimination": "4a3d009cb0978c0610eb2f1439362e0b0f6b42a157af1d5038707a21fce09b62",
                "regime_transfer": "633db647625a3f3131635b5156ca54f023cb4769b4c7034ea3bcf985c2aa769c"}
    for name in previous:
        profile = get_task_profile(name)
        assert profile["catalog_version"] == "scientific-task-profiles-0.1.4"
        assert canonical_hash(profile) == presentation_profiles._TASK_HASHES[name]
        assert canonical_hash(profile) != previous[name]
        profile["catalog_version"] = "scientific-task-profiles-0.1.2"
        profile["applicable_environments"].remove(NAME)
        assert canonical_hash(profile) == previous[name]
    contract = score_contract()
    assert contract["claim_eligibility"]["protocol"] == "public-claim-eligibility-0.7"
    assert canonical_hash(contract) == presentation_profiles._SCORE_HASH
    contract["claim_eligibility"]["protocol"] = "public-claim-eligibility-0.6"
    contract["claim_eligibility"]["minimum_lag"].pop(NAME)
    assert canonical_hash(contract) == "969e75b5a96947617af996535b8b8e5b854ff1190bea385d02db65dfd8ddc420"
