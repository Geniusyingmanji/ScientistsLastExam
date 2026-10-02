"""Offline shared-interface regressions; no model API or discovery verdict."""
from copy import deepcopy
import json

import numpy as np
import pytest

from env.calibration import _initial, calibrate
from env.claim_calibration import NULL_ENVIRONMENTS
from env.claim_semantics import claim_eligibility, policy_description
from env.evidence_packet import AXIS, SPECS, build_packet
from env.presentation_profiles import present_problem
from env.prospective_runner import ProspectiveTask, _observation_contract, verify_directory
from env.registry import ENVIRONMENTS, EXPERIMENTAL_ENVIRONMENTS, load_world
from env.scoring import canonical_hash, score_contract, validate_submission, verify_claims
from env.task_profiles import TASK_PROFILE_NAMES, get_task_profile


NAME = "orbital_dynamics"
PREVIOUS = ("microecology", "coupled_oscillators", "reaction_kinetics", "heat_transport",
            "gene_regulation", "ising_spin", "hysteresis_material", "microecology_causal")


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def fail(*args, **kwargs):
        pytest.fail("orbital integration tests must not access the network")
    monkeypatch.setattr("socket.socket", fail)
    monkeypatch.setattr("socket.create_connection", fail)


def specimen():
    return {"position": [1.2, 0], "velocity": [0, .8],
            "times": [0, .25, 1, 1.125, 1.25, 2], "impulses": []}


def decide(control, treatment, row, channel="vx"):
    return claim_eligibility(NAME, control, treatment, {"row": row, "channel": channel}, "times")


def submission(row):
    control = specimen()
    treatment = dict(control, impulses=[{"time": 1, "delta_v": [.15, -.11]}])
    return {"predictor_code": "def predict(spec):\n    return [[0.0]*4 for _ in spec['times']]\n",
            "claims": [{"id": "impulse-effect", "statement": "The stated paired velocity change.",
                        "control": control, "treatment": treatment, "readout": {"row": row, "channel": "vx"},
                        "interval": [.14, .16], "evidence_ids": ["obs-0001"],
                        "scope": "Specified controls and readout only; integration fixture."}],
            "explanation": "No scientific discovery assertion."}


def test_registered_experimental_world_has_public_tasks_and_loadable_baseline():
    assert ENVIRONMENTS == PREVIOUS + (NAME, "pattern_formation")
    assert EXPERIMENTAL_ENVIRONMENTS == ("microecology_causal", NAME, "pattern_formation")
    worlds = [load_world(NAME, seed)[0] for seed in (7, 46, 1439, 8743)]
    for task_name in TASK_PROFILE_NAMES:
        descriptions = []
        for world in worlds:
            public = world.describe()
            public.update(task_profile=get_task_profile(task_name, NAME), score_contract=score_contract())
            descriptions.append(present_problem(public, "full_description", environment=NAME))
        assert descriptions == [descriptions[0]] * 4
        text = json.dumps(descriptions[0])
        assert all(label not in text for label in worlds[0].operator_strata)
        assert "private_parameters" not in text and "world_seed" not in text
    world, baseline = load_world(NAME, 7)
    prediction = np.asarray(baseline([], world.validate(specimen())))
    assert prediction.shape == (6, 4) and np.isfinite(prediction).all()
    with pytest.raises(ValueError, match="not audited"):
        present_problem(world.describe(), "apparatus_only", environment=NAME)


@pytest.mark.parametrize("channel", ["x", "y", "vx", "vy"])
def test_pilot_lag_excludes_assigned_and_short_lag_readouts_in_either_arm(channel):
    world, _ = load_world(NAME, 7)
    control = world.validate(specimen())
    treatment = world.validate(dict(control, impulses=[{"time": 1, "delta_v": [.15, -.11]}]))
    assert decide(control, treatment, 0, channel)["reason"] == "readout_before_temporal_resolution"
    assert decide(control, treatment, 1, channel)["eligible"]  # Future impulse is irrelevant.
    for left, right in ((control, treatment), (treatment, control)):
        for row in (2, 3):
            assert decide(left, right, row, channel)["reason"] == "readout_too_soon_after_event"
        assert decide(left, right, 4, channel)["eligible"]
    policy = policy_description()
    assert policy["protocol"] == "public-claim-eligibility-0.7"
    assert policy["minimum_lag"][NAME] == {"value": .25, "unit": "T", "axis_field": "times",
                                            "event_field": "impulses", "event_time_field": "time"}


def test_later_impulses_neither_reopen_nor_revoke_earlier_readout_eligibility():
    world, _ = load_world(NAME, 7)
    control = world.validate(specimen())
    treatment = world.validate(dict(control, impulses=[{"time": 1, "delta_v": [.15, 0]},
                                                       {"time": 2, "delta_v": [0, .1]}]))
    assert decide(control, treatment, 3)["reason"] == "readout_too_soon_after_event"
    assert decide(control, treatment, 4)["eligible"]
    assert decide(control, treatment, 5)["reason"] == "readout_too_soon_after_event"
    # Inclusive boundary; a meaningful sub-boundary offset remains ineligible.
    changed = deepcopy(treatment)
    changed["times"][4] = 1.25 - 1e-8
    paired = dict(control, times=changed["times"])
    assert not decide(paired, changed, 4)["eligible"]
    assert decide(control, changed, 4)["reason"] == "unmatched_readout_coordinate"
    maximum = world.validate(dict(control, times=np.linspace(0, 12, 65).tolist()))
    assert decide(maximum, maximum, 64)["eligible"]
    oversized = dict(maximum, times=np.linspace(0, 12, 66).tolist())
    assert decide(oversized, oversized, 64)["reason"] == "invalid_public_spec"


def test_assigned_impulse_claim_cannot_commit_or_gain_verification_credit():
    world, _ = load_world(NAME, 46)
    for row, reason in ((0, "valid post-initial observation"),
                        (2, "readout_too_soon_after_event"), (3, "readout_too_soon_after_event")):
        with pytest.raises(ValueError, match=reason):
            validate_submission(submission(row), world, [{"id": "obs-0001"}])
    assert validate_submission(submission(4), world, [{"id": "obs-0001"}])["claims"]
    report = verify_claims(world, submission(2)["claims"], "orbital-assignment-fixture")
    assert report["score"] == 0 and report["verified_nonzero_effects"] == 0
    assert report["claims"][0]["eligibility"]["reason"] == "readout_too_soon_after_event"
    assert report["claims"][0]["mean_difference"] == pytest.approx(.15, abs=.01)


def test_additive_unclipped_noise_contract_and_public_initial_state():
    world, _ = load_world(NAME, 7)
    contract = _observation_contract(world)
    assert contract["axis_field"] == "times" and contract["channels"] == ["x", "y", "vx", "vy"]
    assert contract["noise_std"] == list(world.noise_std)
    assert contract["noise_mean_bias_bound"] == [0.] * 4
    assert _initial(NAME, world.validate(specimen()), world.channels) == [1.2, 0., 0., .8]
    zero = dict(specimen(), times=[0])
    rows = np.asarray([world.run(zero, noise_key="unclipped-%d" % i)["values"][0] for i in range(32)])
    error = rows - _initial(NAME, zero, world.channels)
    assert np.all(error.min(axis=0) < 0) and np.all(error.max(axis=0) > 0)


def test_prospective_source_receipts_and_public_evidence_packet_preserve_orbital_axis(tmp_path):
    task = ProspectiveTask(NAME, 7, tmp_path / "orbital-prospective")
    assert task.describe()["observation_contract"]["noise_mean_bias_bound"] == [0.] * 4
    impulse = {"time": 1., "delta_v": [.15, -.11]}
    record = task.observe_source(dict(specimen(), impulses=[impulse]))
    assert task.close()["status"] == "incomplete"
    assert verify_directory(task.directory)["replayed_tests"] == 0
    report = {"environment": NAME,
              "rounds": [{"round": 1, "response": json.dumps({"note": "Source", "experiments": [record["spec"]]})}],
              "history": [{"round": 1, "note": "Source", "observations": [record], "outcome": "observed"}],
              "records": [record], "private_parameters": "OPERATOR_CANARY"}
    packet = build_packet(report)
    assert packet["observations"] and "unsupported_top_record" not in packet["gaps"]
    assert "OPERATOR_CANARY" not in json.dumps(packet)
    preserved = packet["observations"][0]
    assert preserved["spec"]["impulses"] == [impulse]
    assert preserved["observation"]["axis"] == record["spec"]["times"]
    assert preserved["observation"]["values"] == record["observation"]["values"]
    assert AXIS[NAME] == "times"


def test_generic_orbital_calibration_is_explicit_and_does_not_expand_null_set():
    assert NULL_ENVIRONMENTS == PREVIOUS[:-1]
    result = calibrate([NAME], seeds=(7,), panel_count=1, max_seconds=20)
    assert result["status"] == "complete" and len(result["instances"]) == 1
    methods = result["summary"][NAME]["methods"]
    assert all(method["valid_predictions"] == 2 and method["invalid_predictions"] == 0
               for method in methods.values())


def test_registration_preserves_old_scientific_envelopes_and_task_content():
    # Captured before ninth-world integration. Only explicit version/applicability
    # additions are removed; existing scientific schemas and noise stay exact.
    assert canonical_hash({n: {"spec": SPECS[n], "axis": AXIS[n]} for n in PREVIOUS}) == \
        "d4c244a4b56422a1b6a0f246d6e7ba8536498eff6655dd6cd3fd3fa8d452608f"
    assert canonical_hash({n: _observation_contract(load_world(n, 7)[0]) for n in PREVIOUS}) == \
        "cd2f13fea58cd7705161ab8c6ca9a31e2fdef5d0d25431f16595adea5f8690e8"
    policy = policy_description()
    policy.pop("protocol")
    policy["minimum_lag"].pop(NAME)
    policy["minimum_lag"].pop("pattern_formation")
    assert canonical_hash(policy) == "506bdbd878ae2e283c5fa2b016f0e4e03cc21cad400a9d1df83b7be15b81563f"
    expected = {"open_discovery": "5a401bb7683e2684ea8ddc56d9b943f85ed36cb76f382f7dd30804fc4c6798fc",
                "mechanism_discrimination": "dab1f8be65639dbdeb2b4c555e51cce52281adfb9bff5bf945e6a1291c143050",
                "regime_transfer": "14f1a985e3a13595606ad58d13cf48a434faa0cfee10e2f56344dd5f580286e4"}
    for name in TASK_PROFILE_NAMES:
        profile = get_task_profile(name)
        profile.pop("catalog_version")
        profile.pop("applicable_environments")
        assert canonical_hash(profile) == expected[name]
