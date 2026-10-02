"""Twelfth-world adapters and public eligibility; three engineering World calls.

No author calibration, candidate execution or model/network calls. The only real
World calls are two fresh source receipts and one injected numerical failure.
"""
from copy import deepcopy
import json
import math

import numpy as np
import pytest

from env import campaign, presentation_profiles, research_runner
from env.analysis_api import ModelSnapshots
from env.calibration import _initial
from env.claim_calibration import NULL_ENVIRONMENTS, null_cases
from env.claim_semantics import claim_eligibility, policy_description
from env.evidence_packet import AXIS, SPECS, build_packet
from env.presentation_profiles import present_problem
from env.prospective import ProspectiveSession
from env.prospective_runner import ProspectiveTask, _observation_contract, verify_directory
from env.registry import ENVIRONMENTS, EXPERIMENTAL_ENVIRONMENTS, load_world
from env.scoring import canonical_hash, score_contract, validate_submission
from env.spin_echo.kernel import Kernel
from env.spin_echo.protocol import validate_spec
from env.spin_echo.world import World
from env.task_profiles import TASK_PROFILE_NAMES, get_task_profile


NAME = "spin_echo"
PREVIOUS = ("microecology", "coupled_oscillators", "reaction_kinetics", "heat_transport",
            "gene_regulation", "ising_spin", "hysteresis_material", "microecology_causal",
            "orbital_dynamics", "pattern_formation", "electrical_impedance")


@pytest.fixture(autouse=True)
def no_external_execution(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("spin echo integration must not execute network or candidate code")
    # Keep socket's class identity intact for modules importing ssl.
    monkeypatch.setattr("socket.socket.connect", forbidden)
    monkeypatch.setattr("socket.socket.connect_ex", forbidden)
    monkeypatch.setattr("socket.create_connection", forbidden)
    monkeypatch.setattr(ProspectiveTask, "_predict", forbidden)


def specimen(times=None, pulses=None, initial=None):
    return validate_spec({"initial_magnetization": [.3, .4, .5] if initial is None else initial,
                          "times_ms": [0., 1., 10., 11., 20.] if times is None else times,
                          "pulses": [] if pulses is None else pulses})


def pulse(time, angle=math.pi, phase=0.):
    return {"time_ms": time, "angle_rad": angle, "phase_rad": phase}


def decide(control, treatment=None, row=-1, channel="magnetization_x", axis="times_ms"):
    row = len(control["times_ms"]) - 1 if row == -1 else row
    return claim_eligibility(NAME, control, control if treatment is None else treatment,
                             {"row": row, "channel": channel}, axis)


def test_explicit_twelfth_registration_and_public_contract_invariant_across_strata():
    assert ENVIRONMENTS == PREVIOUS + (NAME,)
    assert EXPERIMENTAL_ENVIRONMENTS == ("microecology_causal", "orbital_dynamics",
                                        "pattern_formation", "electrical_impedance", NAME)
    worlds = [World(7, _operator_stratum=label) for label in World.operator_strata]
    for task in TASK_PROFILE_NAMES:
        public = []
        for world in worlds:
            description = world.describe()
            description.update(task_profile=get_task_profile(task, NAME), score_contract=score_contract())
            public.append(present_problem(description, environment=NAME))
        assert public == [public[0]] * 3
        text = json.dumps(public[0])
        for secret in World.operator_strata + ("offsets_hz", "r2_per_s", "world_seed", "panel_seed"):
            assert secret not in text
        # Scoring publishes its own aggregation weights; ensemble weights must
        # be absent from the instrument description, not confused with those.
        assert "weights" not in json.dumps(worlds[0].describe())
    assert worlds[0].version == "spin_echo-0.1.0-experimental"
    assert worlds[0].axis_field == "times_ms"
    with pytest.raises(ValueError, match="not audited"):
        present_problem(worlds[0].describe(), "apparatus_only")


def test_public_initial_baseline_and_records_adapter_never_simulate(monkeypatch):
    world, baseline = load_world(NAME, 7)
    monkeypatch.setattr(Kernel, "trajectory", lambda *args: pytest.fail("public adapter must not simulate"))
    spec = specimen()
    assert _initial(NAME, spec, world.channels) == [.3, .4, .5]
    assert np.asarray(baseline([], spec)).shape == (5, 3)
    record = {"spec": spec, "observation": {"axis": spec["times_ms"], "channels": list(world.channels),
                                           "values": [[.3, .4, .5]] * 5}}
    predicted = np.asarray(baseline([record], spec))
    assert predicted.shape == (5, 3) and np.isfinite(predicted).all()
    assert np.array_equal(predicted[0], spec["initial_magnetization"])


def test_public_millisecond_lag_exact_events_and_future_events():
    spec = specimen([0., .999, 1., 9., 10., 10.999, 11., 20.], [pulse(10.)])
    assert decide(spec, row=0)["reason"] == "readout_before_temporal_resolution"
    assert not decide(spec, row=1)["eligible"]
    assert decide(spec, row=2)["eligible"]
    assert decide(spec, row=3)["eligible"]  # Future event does not restart an earlier lag.
    assert decide(spec, row=4)["reason"] == "readout_too_soon_after_event"
    assert not decide(spec, row=5)["eligible"]
    assert decide(spec, row=6)["eligible"]
    earlier = deepcopy(spec)
    earlier["pulses"] = [pulse(10.5)]
    for left, right in ((earlier, spec), (spec, earlier)):
        assert decide(left, right, row=6)["reason"] == "readout_too_soon_after_event"
    shifted = deepcopy(spec)
    shifted["times_ms"][-1] = 21.
    assert decide(spec, shifted)["reason"] == "unmatched_readout_coordinate"
    assert decide(spec, axis="times")["reason"] == "mismatched_axis_field"


@pytest.mark.parametrize("channel", ["magnetization_x", "magnetization_y", "magnetization_z"])
def test_zero_preparation_excluded_in_either_arm_even_after_mixing_pulse(channel):
    good = specimen(pulses=[pulse(10., math.pi/2)])
    zero = specimen(pulses=[pulse(10., math.pi/2)], initial=[0., 0., 0.])
    for control, treatment in ((zero, good), (good, zero)):
        assert decide(control, treatment, channel=channel)["reason"] == "public_preparation_assigns_readout"


@pytest.mark.parametrize("angle", [-2*math.pi, -math.pi, 0., math.pi, 2*math.pi, math.pi-5e-13])
def test_known_z_under_integer_pi_rotations_does_not_earn_claim_credit(angle):
    spec = specimen(pulses=[pulse(10., angle, .37)])
    assert decide(spec, channel="magnetization_z")["reason"] == "public_preparation_assigns_readout"
    assert decide(spec)["eligible"]  # Transverse response still depends on unknown dynamics.


def test_known_z_uses_only_past_pulses_and_mixed_z_can_be_unknown():
    no_pulses = specimen()
    assert not decide(no_pulses, channel="magnetization_z")["eligible"]
    spec = specimen([0., 1., 5., 10., 11., 20.], [pulse(2.), pulse(10., math.pi/2)])
    assert decide(spec, row=2, channel="magnetization_z")["reason"] == "public_preparation_assigns_readout"
    assert decide(spec, row=4, channel="magnetization_z")["eligible"]
    # A later integer-pi pulse does not erase the prior unknown mixed z anchor.
    spec["pulses"].append(pulse(15., math.pi))
    assert decide(spec, channel="magnetization_z")["eligible"]
    barely_non_pi = specimen(pulses=[pulse(10., math.pi-1e-9)])
    assert decide(barely_non_pi, channel="magnetization_z")["eligible"]


@pytest.mark.parametrize("channel", ["magnetization_x", "magnetization_y", "magnetization_z"])
def test_pure_z_with_integer_pi_prefix_fixes_every_channel(channel):
    spec = specimen(pulses=[pulse(10.)], initial=[0., 0., .8])
    assert not decide(spec, channel=channel)["eligible"]
    spec["pulses"].append(pulse(19., math.pi/2))
    assert not decide(spec, row=3, channel=channel)["eligible"]  # Still before mixing.
    # The first mixing pulse creates later unknown transverse evolution, but z
    # is still only the known initial z times a calibrated cosine/sign factor.
    assert decide(spec, channel=channel)["eligible"] == (channel != "magnetization_z")


@pytest.mark.parametrize("first_angle", [math.pi/2, -math.pi/2, math.pi/3])
def test_pure_z_stays_known_after_first_mixing_until_later_transverse_dependency(first_angle):
    spec = specimen([0., 5., 10., 11., 20., 21., 25.],
                    [pulse(2., math.pi), pulse(10., first_angle, .37)], [0., 0., .8])
    assert decide(spec, row=3, channel="magnetization_z")["reason"] == "public_preparation_assigns_readout"
    assert decide(spec, channel="magnetization_z")["reason"] == "public_preparation_assigns_readout"
    spec["pulses"].append(pulse(20., math.pi/2, -.7))
    assert not decide(spec, row=3, channel="magnetization_z")["eligible"]  # Future pulse cannot reopen it.
    assert decide(spec, row=5, channel="magnetization_z")["eligible"]


def test_twelve_pulses_supported_without_expanding_old_event_caps():
    spec = specimen([25.], [pulse(1. + index) for index in range(12)])
    assert decide(spec)["eligible"]
    assert policy_description()["spin_echo_rule"]["maximum_pulses"] == 12
    spec["pulses"].append(pulse(13.))
    assert decide(spec)["reason"] == "invalid_public_spec"
    old = {"times": [25.], "impulses": [{"time": float(i)} for i in range(5)]}
    readout = {"row": 0, "channel": "vx"}
    assert claim_eligibility("orbital_dynamics", old, old, readout, "times")["reason"] == "invalid_public_spec"
    old["impulses"].pop()
    assert claim_eligibility("orbital_dynamics", old, old, readout, "times")["eligible"]


@pytest.mark.parametrize("field,value", [
    ("initial_magnetization", [0, 0]), ("initial_magnetization", [1, 1, 0]),
    ("initial_magnetization", [True, 0, 0]), ("initial_magnetization", [10**1000, 0, 0]),
    ("times_ms", [0, 2, 1, 20]), ("times_ms", [0, float("nan"), 20]),
    ("times_ms", [0, 251]), ("times_ms", list(range(130))), ("detuning_hz", 41),
    ("pulses", [pulse(0)]), ("pulses", [pulse(10), pulse(10)]),
    ("pulses", [pulse(10, math.inf)]), ("pulses", [pulse(10, phase=4)]),
    ("private_seed", 7),
])
def test_spin_policy_rejects_malformed_public_spec_in_either_arm(field, value):
    good, bad = specimen(), dict(specimen(), **{field: value})
    for left, right in ((good, bad), (bad, good)):
        assert decide(left, right, row=1)["reason"] == "invalid_public_spec"


def test_claim_submission_excludes_known_z_without_simulating(monkeypatch):
    world, _ = load_world(NAME, 7)
    monkeypatch.setattr(world, "run", lambda *args, **kwargs: pytest.fail("validation must not simulate"))
    claim = {"id": "echo-transfer", "statement": "Scoped delayed transverse contrast.",
             "control": specimen(), "treatment": specimen(pulses=[pulse(10.)]),
             "readout": {"row": 4, "channel": "magnetization_x"}, "interval": [-1., 1.],
             "evidence_ids": ["obs-1"], "scope": "Finite response, not unique mechanism."}
    submission = {"predictor_code": "def predict(spec):\n    return [[0.,0.,0.] for t in spec['times_ms']]\n",
                  "claims": [claim], "explanation": "Inert integration fixture."}
    assert validate_submission(submission, world, [{"id": "obs-1"}])["claims"][0]["readout"]["channel"] == "magnetization_x"
    claim["readout"]["channel"] = "magnetization_z"
    with pytest.raises(ValueError, match="public_preparation_assigns_readout"):
        validate_submission(submission, world, [{"id": "obs-1"}])


def test_source_noise_receipts_and_public_evidence_axis_binding(tmp_path):
    task = ProspectiveTask(NAME, 7, tmp_path / "sources")
    spec = specimen([0., 10., 20.])
    contract = task.describe()["observation_contract"]
    assert contract["axis_field"] == "times_ms"
    assert contract["noise_std"] == [.002]*3 and contract["noise_mean_bias_bound"] == [0.]*3
    first, second = task.observe_source(spec), task.observe_source(spec)  # Two actual smoke calls.
    assert first["observation"]["values"] != second["observation"]["values"]
    with pytest.raises(ValueError, match="cannot be reused"):
        task._observe(spec, noise_key=next(iter(task._noise_keys)))
    assert task._usage["experiment_attempts"] == 2
    task.close()
    assert verify_directory(task.directory)["replayed_tests"] == 0
    report = {"environment": NAME, "rounds": [], "history": [], "records": [first],
              "private_parameters": "OPERATOR_CANARY"}
    packet = build_packet(report)
    assert packet["observations"][0]["spec"] == first["spec"]
    assert packet["observations"][0]["observation"] == first["observation"]
    assert "OPERATOR_CANARY" not in json.dumps(packet)
    report["records"][0]["observation"]["axis"] = [0., 11., 20.]
    assert build_packet(report)["gaps"]


def test_numerical_failure_is_charged_and_preserved(tmp_path, monkeypatch):
    task = ProspectiveTask(NAME, 7, tmp_path / "failure")
    monkeypatch.setattr(Kernel, "MAX_FREE_PROPAGATIONS", 0)
    with pytest.raises(RuntimeError, match="propagation budget"):
        task.observe_source(specimen([1.]))  # One actual, deliberately failing smoke call.
    with pytest.raises(RuntimeError, match="closed"):
        task.observe_source(specimen([1.]))
    rows = [json.loads(p.read_text()) for p in sorted((task.directory / "receipts").glob("[0-9]*.json"))]
    failures = [r["payload"] for r in rows if r["kind"] == "observation_attempt_finished"]
    assert len(failures) == 1 and failures[0]["ok"] is False
    assert task._usage["experiment_attempts"] == 1


def test_snapshot_and_future_pulse_schema_without_prediction_or_observation(tmp_path):
    world, _ = load_world(NAME, 7)
    def fail(*args, **kwargs):
        pytest.fail("snapshot binding and request validation must not execute code or observe")
    store = ModelSnapshots(tmp_path / "models")
    code = "raise RuntimeError('inert fixture')\ndef predict(spec):\n    return [[MODEL['a'],0.,0.] for t in spec['times_ms']]\n"
    rivals = []
    for name, a in (("first", .2), ("second", .4)):
        saved = store.save_model(name, "v1", {"a": a}, code)
        rivals.append({"id": name, "model_snapshot": {key: saved[key] for key in ("name", "version", "sha256")},
                       "rationale": "Inert schema fixture.", "evidence_ids": ["source-1"], "tolerance": .01})
    target = specimen([25.], [pulse(1. + index) for index in range(12)])
    request = {"profile": "regime_transfer", "scope": "Fresh pulse-control schema fixture.",
               "rivals": rivals, "experiments": [{"id": "target", "role": "target", "spec": target}],
               "readout": [{"experiment_id": "target", "row": 0, "channel": "magnetization_x", "weight": 1.}],
               "replicates": 4, "revision_of": None, "change_note": ""}
    resolved, bindings = research_runner._resolve_rivals(request, store)
    assert len(bindings) == 2
    session = ProspectiveSession(_observation_contract(world), validate_spec=world.validate,
        predict=fail, observe=fail, persist=fail, runtime_id="spin-schema")
    source = specimen([1.])
    session._ingest([{"id": "source-1", "spec": source, "observation": {
        "axis": [1.], "channels": list(world.channels), "values": [[.3, .4, .5]]}}])
    assert session._request(resolved)["experiments"][0]["spec"] == target
    bad = deepcopy(resolved)
    bad["readout"][0]["channel"] = "private_moment"
    with pytest.raises(ValueError, match="channel"):
        session._request(bad)


def test_explicit_manifest_freeze_and_all_profiles_without_world_execution(monkeypatch):
    monkeypatch.setattr(World, "run", lambda *args, **kwargs: pytest.fail("freeze must not observe"))
    monkeypatch.setattr(campaign, "source_digest", lambda: "spin-integration-fixture")
    monkeypatch.setattr(research_runner, "source_digest", lambda: "spin-integration-fixture")
    choices = iter([7, 46, 1439, 8743, 100001, 100002])
    monkeypatch.setattr(campaign.secrets, "randbelow", lambda bound: next(choices))
    manifest = campaign.create_manifest("spin-integration", [NAME], instances=1, rounds=4, exploration_rounds=2)
    assert manifest["environments"] == [NAME]
    assert manifest["instances"][0]["world_seed"] == 100001
    assert manifest["score_contract"]["claim_eligibility"]["protocol"] == "public-claim-eligibility-0.9"
    for name in TASK_PROFILE_NAMES:
        current = research_runner.create_manifest("spin-profile", NAME, 7, profile=name)
        research_runner.validate_manifest(current)
        assert current["profile"]["catalog_version"] == "scientific-task-profiles-0.1.6"
        assert current["score"] is None and not current["automatic_depth_certification"]


def test_previous_eleven_contracts_and_seven_null_bank_are_unchanged():
    assert canonical_hash({n: load_world(n, 7)[0].describe() for n in PREVIOUS}) == \
        "041db69e570226a10dc690cb0f6a5a72fd3fa8684daf3aad509557cab32b112f"
    assert canonical_hash({n: _observation_contract(load_world(n, 7)[0]) for n in PREVIOUS}) == \
        "6b1d96b69becf61c24ba26e3a90cf7150f8fef0c3ae9ffccb73a375e8213b423"
    assert canonical_hash({n: {"spec": SPECS[n], "axis": AXIS[n]} for n in PREVIOUS}) == \
        "4134bc88cfac8e051f459d8b36f091f3d29e7f81e63dcc8ff2a21a5fdd31a04f"
    assert NULL_ENVIRONMENTS == PREVIOUS[:7]
    assert canonical_hash({n: null_cases(n) for n in NULL_ENVIRONMENTS}) == \
        "25b4d2ab981abaa977c02e81cd04120398be3cb60c9f9d023f05291eab3c5e42"
    with pytest.raises(ValueError, match="no audited null"):
        null_cases(NAME)
    contract = score_contract()
    assert canonical_hash(contract) == presentation_profiles._SCORE_HASH
    policy = contract["claim_eligibility"]
    assert policy["minimum_lag"].pop(NAME) == {"value": 1., "unit": "ms", "axis_field": "times_ms",
                                               "event_field": "pulses", "event_time_field": "time_ms"}
    rule = policy.pop("spin_echo_rule")
    assert "administrative" in rule["limits"] and "detectability" in rule["limits"]
    policy["protocol"] = "public-claim-eligibility-0.8"
    assert canonical_hash(contract) == "300effda40142b4a45b3b0d879aacb0020e6e7c4a3aed6820533b64925c65e72"
    for accessor, expected in ((get_task_profile, "062bfb9230e5bde24a5348615f7d2b54dc9b2cca00f8576908c787f8aa00e217"),
                              (lambda n: research_runner._research_profile(n, "pattern_formation"),
                               "8462087167a37b31a593cf222c70e876b203593d74eb8509109e8e237e76c18e")):
        profiles = {n: accessor(n) for n in TASK_PROFILE_NAMES}
        for profile in profiles.values():
            assert profile["catalog_version"] == "scientific-task-profiles-0.1.6"
            profile["catalog_version"] = "scientific-task-profiles-0.1.5"
            profile["applicable_environments"].remove(NAME)
        assert canonical_hash(profiles) == expected
