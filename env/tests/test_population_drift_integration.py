"""Thirteenth-world contracts and explicitly counted engineering smoke calls.

Three local wrapper/solver pairs are planned; the separate 33-positive-time
corner is reserved for root-owned native verification. No reference calibration,
network, model API or candidate execution belongs to these tests.
"""
from copy import deepcopy
import json
from pathlib import Path

import numpy as np
import pytest

from env import campaign, presentation_profiles, research_runner
from env.analysis_api import ModelSnapshots
from env.calibration import _initial
from env.claim_calibration import NULL_ENVIRONMENTS, null_cases
from env.claim_semantics import claim_eligibility, policy_description
from env.evidence_packet import AXIS, SPECS, build_packet
from env.population_drift import kernel as kernel_module
from env.population_drift.kernel import Kernel
from env.population_drift.protocol import validate_spec
from env.population_drift.world import World
from env.presentation_profiles import present_problem
from env.prospective import ProspectiveSession
from env.prospective_runner import ProspectiveTask, _observation_contract, verify_directory
from env.registry import ENVIRONMENTS, EXPERIMENTAL_ENVIRONMENTS, load_world
from env.scoring import canonical_hash, score_contract, validate_submission
from env.task_profiles import TASK_PROFILE_NAMES, get_task_profile

NAME = "population_drift"
PREVIOUS = ("microecology", "coupled_oscillators", "reaction_kinetics", "heat_transport",
            "gene_regulation", "ising_spin", "hysteresis_material", "microecology_causal",
            "orbital_dynamics", "pattern_formation", "electrical_impedance", "spin_echo")
SMOKE_WRAPPERS = {"test_source_noise_receipts_and_evidence_binding": 2,
                  "test_failed_solver_receipt_is_charged": 1,
                  "test_native_33_positive_time_corner": 1}


@pytest.fixture(autouse=True)
def isolated_instrumentation(request, monkeypatch, tmp_path):
    """Track wrapper and child separately, including failure, without extra calls."""
    def forbidden(*args, **kwargs):
        pytest.fail("population integration cannot call network or candidate code")
    monkeypatch.setattr("socket.socket.connect", forbidden)
    monkeypatch.setattr("socket.socket.connect_ex", forbidden)
    monkeypatch.setattr("socket.create_connection", forbidden)
    monkeypatch.setattr(ProspectiveTask, "_predict", forbidden)
    original_run, original_trajectory = World.run, Kernel.trajectory
    events, stack, counts = [], [], {"wrapper": 0, "solver": 0}
    budget = SMOKE_WRAPPERS.get(request.node.name, 0)
    ledger = tmp_path / "population-attempt-ledger.jsonl"

    def emit(record):
        events.append(record)
        with ledger.open("a") as stream:
            stream.write(json.dumps(record, sort_keys=True) + "\n")
            stream.flush()

    def execute(kind, function, *args, **kwargs):
        assert counts[kind] < budget, "unplanned population physics entry"
        counts[kind] += 1
        identifier = "%s-%d" % (kind, counts[kind])
        parent = stack[-1] if stack else None
        if kind == "wrapper":
            assert kwargs.get("noise_key"), "trusted observations must never use clean or empty keys"
        else:
            assert parent and parent.startswith("wrapper-"), "expected exactly one nested solver"
        emit({"id": identifier, "parent": parent, "kind": kind, "event": "began"})
        stack.append(identifier)
        try:
            result = function(*args, **kwargs)
        except BaseException as error:
            emit({"id": identifier, "parent": parent, "kind": kind, "event": "ended", "ok": False,
                  "error_type": type(error).__name__, "error": str(error)})
            raise
        else:
            emit({"id": identifier, "parent": parent, "kind": kind, "event": "ended", "ok": True})
            return result
        finally:
            stack.pop()

    monkeypatch.setattr(World, "run", lambda *a, **kw: execute("wrapper", original_run, *a, **kw))
    monkeypatch.setattr(Kernel, "trajectory", lambda *a, **kw: execute("solver", original_trajectory, *a, **kw))
    monkeypatch.setattr(Kernel, "transition_matrices", forbidden)
    yield {"events": events, "counts": counts, "ledger": ledger}
    assert counts == {"wrapper": budget, "solver": budget}
    assert len(events) == 4 * budget
    assert not stack


def specimen(times=None, initial=6, size=12, **controls):
    return validate_spec(dict(population_size=size, initial_A=initial,
                              times=[0., .25, 1., 10.] if times is None else times, **controls))


def decide(control, treatment=None, row=-1, channel="mean_A_frequency", axis="times"):
    return claim_eligibility(NAME, control, control if treatment is None else treatment,
        {"row": len(control["times"])-1 if row == -1 else row, "channel": channel}, axis)


def test_registration_public_contract_and_private_boundary():
    assert ENVIRONMENTS[:len(PREVIOUS) + 1] == PREVIOUS + (NAME,)
    assert EXPERIMENTAL_ENVIRONMENTS[:len(PREVIOUS[7:]) + 1] == PREVIOUS[7:] + (NAME,)
    worlds = [World(7, _operator_stratum=label) for label in World.operator_strata]
    for profile in TASK_PROFILE_NAMES:
        public = [present_problem(dict(w.describe(), task_profile=get_task_profile(profile, NAME),
                                        score_contract=score_contract()), environment=NAME) for w in worlds]
        assert public == [public[0]] * 4
        encoded = json.dumps(public[0])
        for forbidden in World.operator_strata + ("frequency_effect", "mutation_probability", "world_seed", "panel_seed", "_kernel"):
            assert forbidden not in encoded
    assert "probabilities" not in worlds[0].describe()  # Hidden distribution field, not explanatory prose.
    world = worlds[0]
    assert world.version == "population_drift-0.1.0-experimental"
    assert _observation_contract(world) == {
        "environment": NAME, "world_version": world.version, "axis_field": "times",
        "channels": list(world.channels), "scales": [1.] * 4,
        "noise_std": [.002] * 4, "noise_mean_bias_bound": [0.] * 4}
    with pytest.raises(ValueError, match="not audited"):
        present_problem(world.describe(), "apparatus_only")


def test_public_baseline_initial_and_parameter_blind_panels():
    world, baseline = load_world(NAME, 7)
    raw = specimen()
    assert _initial(NAME, raw, world.channels) == [.5, .5, 0., 0.]
    assert baseline([], raw) == [[.5, .5, 0., 0.]] * 4
    assert _initial(NAME, specimen(initial=0), world.channels) == [0., 0., 0., 1.]
    assert _initial(NAME, specimen(initial=12), world.channels) == [1., 0., 1., 0.]
    for kind in ("development", "conditions", "interventions"):
        panels = [World(7, _operator_stratum=s).panel(17, kind, count=2) for s in World.operator_strata]
        assert panels == [panels[0]] * 4
        for spec in panels[0]:
            assert world.validate(spec) == spec


@pytest.mark.parametrize("channel", World.channels)
@pytest.mark.parametrize("initial", [0, 6, 12])
def test_public_lag_and_boundary_preparation_do_not_use_hidden_mutation(channel, initial):
    raw = specimen(times=[0., .249, .25, 60.], initial=initial)
    assert not decide(raw, row=0, channel=channel)["eligible"]
    assert not decide(raw, row=1, channel=channel)["eligible"]
    assert decide(raw, row=2, channel=channel)["eligible"]
    treatment = deepcopy(raw)
    treatment["newborn_flip_probability"] = .1
    assert decide(raw, treatment, row=2, channel=channel)["eligible"]
    treatment["times"][2] = .251
    assert decide(raw, treatment, row=2, channel=channel)["reason"] == "unmatched_readout_coordinate"


@pytest.mark.parametrize("field,value", [
    ("population_size", True), ("population_size", 1), ("population_size", 33), ("population_size", 12.),
    ("initial_A", -1), ("initial_A", 13), ("initial_A", False), ("initial_A", 6.),
    ("times", [0., 60.1]), ("times", [1., 1.]), ("times", [1.]*34), ("times", [float("nan")]),
    ("selection_bias", .501), ("selection_bias", float("inf")), ("newborn_flip_probability", True),
    ("newborn_flip_probability", .101), ("unexpected", "operator-data"),
])
def test_malformed_canonical_public_spec_fails_closed_in_both_arms(field, value):
    good, bad = specimen([1.]), dict(specimen([1.]), **{field: value})
    for left, right in ((good, bad), (bad, good)):
        assert decide(left, right, row=0)["reason"] == "invalid_public_spec"


def test_readout_validation_and_policy_contract():
    raw = specimen()
    assert decide(raw, axis="temperatures")["reason"] == "mismatched_axis_field"
    assert decide(raw, channel="probabilities")["reason"] == "invalid_readout"
    assert decide(raw, row=4)["reason"] == "invalid_readout"
    assert policy_description()["minimum_lag"][NAME] == {
        "value": .25, "unit": "replacement-clock units", "axis_field": "times",
        "event_field": None, "event_time_field": None}


def test_submission_validation_never_simulates():
    world, _ = load_world(NAME, 7)
    claim = {"id": "boundary-escape", "statement": "A scoped boundary-occupancy contrast.",
        "control": specimen(initial=0), "treatment": specimen(initial=0, newborn_flip_probability=.1),
        "readout": {"row": 3, "channel": "boundary_B"}, "interval": [-1., 1.],
        "evidence_ids": ["obs-1"], "scope": "Current occupancy, not first-passage fixation."}
    submission = {"predictor_code": "def predict(spec):\n    return [[0.,0.,0.,0.] for t in spec['times']]\n",
                  "claims": [claim], "explanation": "Inert schema check."}
    assert validate_submission(submission, world, [{"id": "obs-1"}])["claims"][0]["readout"]["row"] == 3
    claim["readout"]["row"] = 0
    with pytest.raises(ValueError, match="valid post-initial observation"):
        validate_submission(submission, world, [{"id": "obs-1"}])


def test_source_noise_receipts_and_evidence_binding(tmp_path, isolated_instrumentation):
    task = ProspectiveTask(NAME, 7, tmp_path / "sources")
    spec = specimen([0., 1., 10.], initial=0)
    first, second = task.observe_source(spec), task.observe_source(spec)
    assert first["observation"]["values"] != second["observation"]["values"]
    with pytest.raises(ValueError, match="cannot be reused"):
        task._observe(spec, noise_key=next(iter(task._noise_keys)))
    assert task._usage["experiment_attempts"] == 2
    assert len(task._noise_keys) == 2 and all(task._noise_keys)
    task.close()
    assert verify_directory(task.directory)["replayed_tests"] == 0
    assert set(first["observation"]) == {"axis", "channels", "values"}
    report = {"environment": NAME, "rounds": [], "history": [], "records": [first], "private_parameters": "OPERATOR_CANARY"}
    packet = build_packet(report)
    assert packet["observations"][0]["spec"] == first["spec"]
    assert packet["observations"][0]["observation"] == first["observation"]
    assert "OPERATOR_CANARY" not in json.dumps(packet)
    report["records"][0]["observation"]["axis"] = [0., 2., 10.]
    assert build_packet(report)["gaps"]


def test_failed_solver_receipt_is_charged(tmp_path, monkeypatch, isolated_instrumentation):
    task = ProspectiveTask(NAME, 7, tmp_path / "failure")
    monkeypatch.setattr(Kernel, "MAX_EXPONENTIALS", 0)
    with pytest.raises(RuntimeError, match="exponential budget"):
        task.observe_source(specimen([1.]))
    with pytest.raises(RuntimeError, match="closed"):
        task.observe_source(specimen([1.]))
    assert task._usage["experiment_attempts"] == 1
    events = isolated_instrumentation["events"]
    assert [e["ok"] for e in events if e["event"] == "ended"] == [False, False]
    receipts = [json.loads(p.read_text()) for p in sorted((task.directory / "receipts").glob("[0-9]*.json"))]
    failures = [r["payload"] for r in receipts if r["kind"] == "observation_attempt_finished"]
    assert len(failures) == 1 and failures[0]["ok"] is False


def test_native_33_positive_time_corner(tmp_path, monkeypatch, isolated_instrumentation):
    """Root/native-only fixed engineering coverage; no reference accuracy claim."""
    original_expm, calls = kernel_module.expm, []
    def recorded_expm(value):
        calls.append(value.shape)
        return original_expm(value)
    monkeypatch.setattr(kernel_module, "expm", recorded_expm)
    task = ProspectiveTask(NAME, 7, tmp_path / "corner")
    spec = specimen(np.linspace(60./33, 60., 33).tolist(), size=32, initial=16,
                    selection_bias=.5, newborn_flip_probability=.1)
    result = task.observe_source(spec)
    assert calls == [(33, 33)] * 33
    assert np.asarray(result["observation"]["values"]).shape == (33, 4)
    assert np.isfinite(result["observation"]["values"]).all()
    assert task._usage["experiment_attempts"] == 1
    task.close()
    assert verify_directory(task.directory)["replayed_tests"] == 0


def test_snapshot_rival_binding_and_request_schema_without_execution(tmp_path):
    world, _ = load_world(NAME, 7)
    def fail(*args, **kwargs):
        pytest.fail("snapshot schema must not execute prediction or observation")
    store = ModelSnapshots(tmp_path / "models")
    code = "raise RuntimeError('inert fixture')\ndef predict(spec):\n    return [[MODEL['a'],0.,0.,0.] for t in spec['times']]\n"
    rivals = []
    for name, value in (("first", .2), ("second", .4)):
        saved = store.save_model(name, "v1", {"a": value}, code)
        rivals.append({"id": name, "model_snapshot": {k: saved[k] for k in ("name", "version", "sha256")},
                       "rationale": "Inert request fixture.", "evidence_ids": ["source-1"], "tolerance": .01})
    target = specimen([1.], newborn_flip_probability=.1)
    request = {"profile": "regime_transfer", "scope": "New newborn-control regime.", "rivals": rivals,
        "experiments": [{"id": "target", "role": "target", "spec": target}],
        "readout": [{"experiment_id": "target", "row": 0, "channel": "boundary_A", "weight": 1.}],
        "replicates": 4, "revision_of": None, "change_note": ""}
    resolved, bindings = research_runner._resolve_rivals(request, store)
    assert len(bindings) == 2
    session = ProspectiveSession(_observation_contract(world), validate_spec=world.validate,
        predict=fail, observe=fail, persist=fail, runtime_id="population-schema")
    source = specimen([1.])
    session._ingest([{"id": "source-1", "spec": source, "observation": {
        "axis": [1.], "channels": list(world.channels), "values": [[.4, .4, .1, .1]]}}])
    assert session._request(resolved)["experiments"][0]["spec"] == target
    bad = deepcopy(resolved)
    bad["readout"][0]["channel"] = "private_probabilities"
    with pytest.raises(ValueError, match="channel"):
        session._request(bad)


def test_explicit_manifest_all_profiles_and_no_default_promotion(monkeypatch):
    monkeypatch.setattr(campaign, "source_digest", lambda: "population-integration-fixture")
    monkeypatch.setattr(research_runner, "source_digest", lambda: "population-integration-fixture")
    choices = iter([7, 46, 1439, 8743, 100001, 100002])
    monkeypatch.setattr(campaign.secrets, "randbelow", lambda bound: next(choices))
    manifest = campaign.create_manifest("population-integration", [NAME], instances=1, rounds=4, exploration_rounds=2)
    assert manifest["environments"] == [NAME]
    assert manifest["instances"][0]["world_seed"] == 100001
    assert manifest["score_contract"]["claim_eligibility"]["protocol"] == "public-claim-eligibility-0.10"
    for name in TASK_PROFILE_NAMES:
        current = research_runner.create_manifest("population-profile", NAME, 7, profile=name)
        research_runner.validate_manifest(current)
        assert current["profile"]["catalog_version"] == "scientific-task-profiles-0.1.7"
        assert current["score"] is None and not current["automatic_depth_certification"]


def test_old_twelve_contracts_and_seven_null_bank_unchanged():
    assert canonical_hash({n: load_world(n, 7)[0].describe() for n in PREVIOUS}) == \
        "956ffd0fa0217a126cf759f42632d178161100979b050a9c8a41500a225a90c0"
    assert canonical_hash({n: _observation_contract(load_world(n, 7)[0]) for n in PREVIOUS}) == \
        "94e1e37225e25944437b41ae1b52c932437ce5349411d7716092a5a7ba5c468f"
    assert canonical_hash({n: {"spec": SPECS[n], "axis": AXIS[n]} for n in PREVIOUS}) == \
        "ec887d55281a50e8a45c73058742566bab79ac0d8fb76c4a05ebcb487ce79a14"
    assert NULL_ENVIRONMENTS == PREVIOUS[:7]
    assert canonical_hash({n: null_cases(n) for n in NULL_ENVIRONMENTS}) == \
        "25b4d2ab981abaa977c02e81cd04120398be3cb60c9f9d023f05291eab3c5e42"
    with pytest.raises(ValueError, match="no audited null"):
        null_cases(NAME)
    contract = score_contract()
    assert canonical_hash(contract) == presentation_profiles._SCORE_HASH
    contract["claim_eligibility"]["minimum_lag"].pop(NAME)
    contract["claim_eligibility"]["protocol"] = "public-claim-eligibility-0.9"
    assert canonical_hash(contract) == "a9d80c99e75cda6353741543844915b94284abbc59aaa1cbf2a975f0d07a9137"
    profiles = {n: get_task_profile(n) for n in TASK_PROFILE_NAMES}
    for profile in profiles.values():
        profile["catalog_version"] = "scientific-task-profiles-0.1.6"
        profile["applicable_environments"].remove(NAME)
    assert canonical_hash(profiles) == "5c6646e77d7bbe770752fd430d26377df5452f231e913872725763c618f6b3c5"
