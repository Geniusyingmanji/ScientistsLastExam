"""Eleventh-world interface checks; no model API or candidate execution."""
from copy import deepcopy
import json

import numpy as np
import pytest

from env import campaign, presentation_profiles, research_runner
from env.analysis_api import ModelSnapshots, PROTOCOL as SNAPSHOT_PROTOCOL
from env.calibration import _initial, calibrate
from env.claim_calibration import NULL_ENVIRONMENTS, null_cases
from env.claim_semantics import claim_eligibility, policy_description
from env.electrical_impedance.kernel import Kernel
from env.electrical_impedance.protocol import example
from env.evidence_packet import AXIS, SPECS, build_packet
from env.presentation_profiles import present_problem
from env.prospective import ProspectiveSession
from env.prospective_runner import ProspectiveTask, _observation_contract, verify_directory
from env.registry import ENVIRONMENTS, EXPERIMENTAL_ENVIRONMENTS, load_world
from env.scoring import canonical_hash, prediction_metrics, score_contract, validate_submission
from env.task_profiles import TASK_PROFILE_NAMES, get_task_profile


NAME = "electrical_impedance"
PREVIOUS = ("microecology", "coupled_oscillators", "reaction_kinetics", "heat_transport",
            "gene_regulation", "ising_spin", "hysteresis_material", "microecology_causal",
            "orbital_dynamics", "pattern_formation")


@pytest.fixture(autouse=True)
def no_external_execution(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("electrical integration cannot run network or candidate code")
    monkeypatch.setattr("socket.socket", forbidden)
    monkeypatch.setattr("socket.create_connection", forbidden)
    monkeypatch.setattr(ProspectiveTask, "_predict", forbidden)


def specimen():
    return dict(example(), frequencies_hz=[2., 100., 5000.])


def decide(control, treatment, row=0, channel="voltage_real", axis="frequencies_hz"):
    return claim_eligibility(NAME, control, treatment, {"row": row, "channel": channel}, axis)


def test_eleventh_experimental_world_preserves_hidden_menu_and_all_full_tasks():
    assert ENVIRONMENTS == PREVIOUS + (NAME,)
    assert EXPERIMENTAL_ENVIRONMENTS == ("microecology_causal", "orbital_dynamics", "pattern_formation", NAME)
    worlds = [load_world(NAME, seed)[0] for seed in (7, 46, 1439, 8743)]
    assert [w.operator_stratum() for w in worlds].count("leaky_single_rc") == 0
    assert [w.operator_stratum() for w in worlds].count("leaky_double_rc") == 3
    assert [w.operator_stratum() for w in worlds].count("leaky_series_rlc") == 1
    for task in TASK_PROFILE_NAMES:
        descriptions = []
        for world in worlds:
            public = world.describe()
            public.update(task_profile=get_task_profile(task, NAME), score_contract=score_contract())
            descriptions.append(present_problem(public, "full_description", environment=NAME))
        assert descriptions == [descriptions[0]] * 4
        text = json.dumps(descriptions[0])
        for hidden in worlds[0].operator_strata + ("leakage_ohm", "capacitance", "inductance", "branches", "world_seed", "panel_seed"):
            assert hidden not in text
        assert "V peak" in text and "independent sinusoidal steady-state" in text
    with pytest.raises(ValueError, match="not audited"):
        present_problem(worlds[0].describe(), "apparatus_only")
    for task in ("model_revision", "boundary_mapping"):
        for old in ("coupled_oscillators", "ising_spin"):
            public = load_world(old, 7)[0].describe()
            public["task_profile"] = get_task_profile(task, old)
            with pytest.raises(ValueError, match="not audited"):
                present_problem(public, "apparatus_only")


def test_public_baseline_dimensions_and_no_assigned_initial_do_not_simulate(monkeypatch):
    world, baseline = load_world(NAME, 7)
    def forbidden(*args, **kwargs):
        pytest.fail("public adapters must not access hidden responses")
    monkeypatch.setattr(Kernel, "spectrum", forbidden)
    for axis in ([2.], np.geomspace(2, 5000, 65).tolist()):
        spec = dict(specimen(), frequencies_hz=axis)
        assert _initial(NAME, spec, world.channels) is None
        assert np.array(baseline([], spec)).shape == (len(axis), 2)
    record = {"spec": specimen(), "observation": {"axis": specimen()["frequencies_hz"],
              "channels": list(world.channels), "values": [[.8, -.1], [.5, -.2], [.4, .1]]}}
    assert np.array(baseline([record], specimen())).shape == (3, 2)


@pytest.mark.parametrize("channel", ["voltage_real", "voltage_imag"])
def test_frequency_contrasts_allow_different_coordinates_without_time_lag(channel):
    control = specimen()
    treatment = dict(control, frequencies_hz=[3., 200., 4000.])
    assert decide(control, treatment, 0, channel)["eligible"]
    assert decide(control, treatment, 2, channel)["eligible"]
    assert decide(control, dict(control, load_ohm=200), 0, channel)["eligible"]
    assert decide(control, treatment, 0, channel, "times")["reason"] == "mismatched_axis_field"
    policy = policy_description()
    assert NAME not in policy["minimum_lag"]
    rule = policy["frequency_rules"][NAME]
    assert rule["minimum_lag"] is None and rule["axis_field"] == "frequencies_hz"
    assert "frequencies may differ" in rule["readout_rule"]
    assert "combined contrast" in rule["readout_rule"]
    assert "instrument facts" in rule["limits"]


@pytest.mark.parametrize("field,value", [
    ("frequencies_hz", []), ("frequencies_hz", [2.] * 66), ("frequencies_hz", [2., 2.]),
    ("frequencies_hz", [3., 2.]), ("frequencies_hz", [1., 100.]), ("frequencies_hz", [2., 5001.]),
    ("frequencies_hz", [2., float("nan")]), ("frequencies_hz", [2., float("inf")]),
    ("frequencies_hz", [True]), ("frequencies_hz", [2., 10**1000]), ("frequencies_hz", (2.,)),
    ("source_ohm", 99.), ("load_ohm", 20001.), ("amplitude_v", True), ("times", [2.]),
])
def test_frequency_policy_checks_entire_axis_and_controls_in_either_arm(field, value):
    good, bad = specimen(), dict(specimen(), **{field: value})
    for control, treatment in ((good, bad), (bad, good)):
        assert decide(control, treatment)["reason"] == "invalid_public_spec"


@pytest.mark.parametrize("row,channel", [(True, "voltage_real"), (-1, "voltage_real"),
                                         (3, "voltage_real"), (0, "phase"), (1.5, "voltage_real")])
def test_frequency_readout_rejects_invalid_rows_and_channels(row, channel):
    assert decide(specimen(), specimen(), row, channel)["reason"] == "invalid_readout"


def test_first_frequency_is_an_observation_for_scoring_and_submission(monkeypatch):
    world, _ = load_world(NAME, 7)
    monkeypatch.setattr(world, "run", lambda *a, **kw: pytest.fail("validation must not simulate"))
    claim = {"id": "frequency-contrast", "statement": "Readout at two specified frequencies.",
             "control": dict(specimen(), frequencies_hz=[2.]),
             "treatment": dict(specimen(), frequencies_hz=[100.]),
             "readout": {"row": 0, "channel": "voltage_imag"}, "interval": [-.5, .5],
             "evidence_ids": ["source-1"], "scope": "Public frequency contrast only."}
    submission = {"predictor_code": "def predict(spec):\n    return [[0.,0.] for f in spec['frequencies_hz']]\n",
                  "claims": [claim], "explanation": "Inert validation fixture."}
    assert validate_submission(submission, world, [{"id": "source-1"}])["claims"][0]["readout"]["row"] == 0
    observed = {"axis": [2., 100.], "values": [[1., 0.], [0., 0.]]}
    metrics = prediction_metrics([[0., 0.], [0., 0.]], observed, world.scales)
    assert metrics["scored_rows"] == 2 and metrics["normalized_rmse"] == .5


def test_explicit_campaign_selection_does_not_join_existing_cohorts(monkeypatch):
    choices = iter([7, 46, 1439, 8743, 100001, 100002])
    monkeypatch.setattr(campaign.secrets, "randbelow", lambda bound: next(choices))
    manifest = campaign.create_manifest("electrical-integration", [NAME], instances=1,
        rounds=4, exploration_rounds=2, analysis_protocol=SNAPSHOT_PROTOCOL)
    assert manifest["environments"] == [NAME]
    assert manifest["instances"][0]["world_seed"] == 100001
    assert manifest["sampling_policy"]["balanced_strata_environments"] == []
    assert "operator_sampling_stratum" not in manifest["instances"][0]
    assert manifest["analysis_contract"]["protocol"] == SNAPSHOT_PROTOCOL


def test_source_receipts_noise_keys_and_evidence_frequency_binding(tmp_path):
    task = ProspectiveTask(NAME, 7, tmp_path / "source")
    contract = task.describe()["observation_contract"]
    assert contract["axis_field"] == "frequencies_hz"
    assert contract["noise_std"] == [.001, .001] and contract["noise_mean_bias_bound"] == [0., 0.]
    first = task.observe_source(specimen())
    second = task.observe_source(specimen())
    assert first["observation"]["values"] != second["observation"]["values"]
    assert any(row[1] < 0 for row in first["observation"]["values"])
    used_key = next(iter(task._noise_keys))
    with pytest.raises(ValueError, match="cannot be reused"):
        task._observe(specimen(), noise_key=used_key)
    assert task._usage["experiment_attempts"] == 2
    assert task._usage["experiment_units"] == 2 * task._world.cost(specimen())
    task.close()
    assert verify_directory(task.directory)["replayed_tests"] == 0
    report = {"environment": NAME, "rounds": [{"round": 1,
              "response": json.dumps({"note": "Source", "experiments": [specimen()]})}],
              "history": [{"round": 1, "note": "Source", "observations": [first], "outcome": "observed"}],
              "records": [first], "private_parameters": "OPERATOR_CANARY"}
    packet = build_packet(report)
    assert "unsupported_top_record" not in packet["gaps"]
    assert packet["observations"][0]["observation"] == first["observation"]
    assert packet["observations"][0]["spec"] == first["spec"]
    assert "OPERATOR_CANARY" not in json.dumps(packet)
    report["records"][0]["observation"]["axis"] = [3., 100., 5000.]
    assert build_packet(report)["gaps"]


def test_explicit_numerical_failure_is_charged_retained_and_terminal(tmp_path, monkeypatch):
    task = ProspectiveTask(NAME, 7, tmp_path / "failure")
    monkeypatch.setattr(Kernel, "MAX_SOLVES", 0)
    with pytest.raises(RuntimeError, match="solve budget"):
        task.observe_source(specimen())
    with pytest.raises(RuntimeError, match="closed"):
        task.observe_source(specimen())
    entries = [json.loads(p.read_text()) for p in sorted((task.directory / "receipts").glob("[0-9]*.json"))]
    finished = [row["payload"] for row in entries if row["kind"] == "observation_attempt_finished"]
    assert len(finished) == 1 and finished[0]["ok"] is False
    assert task._usage["experiment_attempts"] == 1


def test_future_frequency_evidence_and_snapshots_validate_without_running_code(tmp_path):
    world, _ = load_world(NAME, 7)
    def fail(*args, **kwargs):
        pytest.fail("schema and snapshot checks must never execute or observe")
    store = ModelSnapshots(tmp_path / "models")
    rivals = []
    for name, gain in (("left", .5), ("right", .7)):
        code = "raise RuntimeError('inert candidate')\ndef predict(spec):\n    return [[MODEL['gain'],0.] for f in spec['frequencies_hz']]\n"
        saved = store.save_model(name, "v1", {"gain": gain}, code)
        rivals.append({"id": name, "model_snapshot": {key: saved[key] for key in ("name", "version", "sha256")},
                       "rationale": "Schema fixture", "evidence_ids": ["source-1"], "tolerance": .01})
    source = dict(specimen(), frequencies_hz=[100.])
    target = dict(specimen(), frequencies_hz=[300.])
    request = {"profile": "mechanism_discrimination", "scope": "Unobserved-frequency schema fixture.",
               "rivals": rivals, "experiments": [{"id": "target", "role": "target", "spec": target}],
               "readout": [{"experiment_id": "target", "row": 0, "channel": "voltage_real", "weight": 1.}],
               "replicates": 4, "revision_of": None, "change_note": ""}
    resolved, bindings = research_runner._resolve_rivals(request, store)
    assert len(bindings) == 2
    session = ProspectiveSession(_observation_contract(world), validate_spec=world.validate,
        predict=fail, observe=fail, persist=fail, runtime_id="electrical-schema")
    session._ingest([{"id": "source-1", "spec": source, "observation": {
        "axis": [100.], "channels": list(world.channels), "values": [[.4, -.1]]}}])
    assert session._request(resolved)["experiments"][0]["spec"]["frequencies_hz"] == [300.]
    # Existing prospective transfer semantics require an apparatus/control change;
    # a new frequency alone remains valid for discrimination, not this transfer gate.
    with pytest.raises(ValueError, match="transfer target must change"):
        session._request(dict(resolved, profile="regime_transfer"))
    changed = deepcopy(resolved)
    changed["profile"] = "regime_transfer"
    changed["experiments"][0]["spec"]["load_ohm"] = 200.
    assert session._request(changed)["profile"] == "regime_transfer"
    bad = deepcopy(resolved); bad["readout"][0]["row"] = 1
    with pytest.raises(ValueError, match="readout row"):
        session._request(bad)
    bad = deepcopy(resolved); bad["readout"][0]["channel"] = "phase"
    with pytest.raises(ValueError, match="channel"):
        session._request(bad)


def test_small_generic_calibration_has_no_initial_method_and_preserves_null_bank():
    assert NULL_ENVIRONMENTS == PREVIOUS[:7]
    with pytest.raises(ValueError, match="no audited null"):
        null_cases(NAME)
    assert canonical_hash({n: null_cases(n) for n in NULL_ENVIRONMENTS}) == \
        "25b4d2ab981abaa977c02e81cd04120398be3cb60c9f9d023f05291eab3c5e42"
    result = calibrate([NAME], seeds=(7,), panel_count=1, max_seconds=20)
    assert result["status"] == "complete"
    assert "no assigned initial value" in result["initial_baseline_unavailable"][NAME]
    for query in result["instances"][0]["queries"]:
        assert "initial" not in query["methods"]
        assert all(method["scored_rows"] == 13 for method in query["methods"].values())
    methods = result["summary"][NAME]["methods"]
    assert methods["initial"]["requested_predictions"] == 0
    assert all(methods[name]["valid_predictions"] == 2 for name in ("zero", "public_0", "public_4", "public_12"))


def test_previous_ten_contracts_and_old_scientific_fingerprints_are_exact():
    assert canonical_hash({n: load_world(n, 7)[0].describe() for n in PREVIOUS}) == \
        "fe5c62e1653c39b149dca34ba93b4488f4d247e5aaecd19b28ac50af75e7ce2d"
    assert canonical_hash({n: _observation_contract(load_world(n, 7)[0]) for n in PREVIOUS}) == \
        "36196623f362a55c444ba3b40c8c5ebf35d8ee31647c653ab52e19fb42fb0333"
    assert canonical_hash({n: {"spec": SPECS[n], "axis": AXIS[n]} for n in PREVIOUS}) == \
        "76a217286e57c4918ef48fed1781aae0fb6d9bafa65322409a503450198c9411"
    contract = score_contract()
    assert canonical_hash(contract) == presentation_profiles._SCORE_HASH
    policy = contract["claim_eligibility"]
    assert policy["protocol"] == "public-claim-eligibility-0.8"
    assert set(policy.pop("frequency_rules")) == {NAME}
    policy["protocol"] = "public-claim-eligibility-0.7"
    assert canonical_hash(contract) == "665c0b8946b72e302e1ee250a671148677681a694f0c2fd3cda610d419c5adda"
    for accessor, expected in ((get_task_profile, "94f1704f45de0cf9095e5cef1a197eed9f27254f836ea5425bcbc64307103af7"),
                              (lambda n: research_runner._research_profile(n, "pattern_formation"),
                               "3c870a6cf020b6d07789eaa25eadc64f51be7e9d3cb3f8b40bb5d2e386557652")):
        profiles = {name: accessor(name) for name in TASK_PROFILE_NAMES}
        for profile in profiles.values():
            assert profile["catalog_version"] == "scientific-task-profiles-0.1.5"
            assert profile["applicable_environments"] == list(PREVIOUS) + [NAME]
            profile["catalog_version"] = "scientific-task-profiles-0.1.4"
            profile["applicable_environments"].remove(NAME)
        assert canonical_hash(profiles) == expected
