"""Public-rule regressions using real legal world specifications; no model API."""
import ast
import copy
import json
from pathlib import Path

import pytest

import env.claim_semantics as semantics
from env.claim_semantics import claim_eligibility, policy_description
from env.registry import load_world
from env.scoring import validate_submission, verify_claims


def decide(world, control, treatment, channel, row):
    return claim_eligibility(world.name, world.validate(control), world.validate(treatment),
                             {"row": row, "channel": channel}, world.axis_field)


def reaction_specs():
    control = {"temperature_k": 325.0, "initial_mM": [1.0, 0.0, 0.0, 0.0],
               "times_s": [0.0, 5.0, 6.0, 6.25, 7.0], "interventions": []}
    treatment = copy.deepcopy(control)
    treatment["interventions"] = [{"time_s": 6.0, "kind": "add", "amounts_mM": [0, 0, 0.8, 0]}]
    return control, treatment


def test_observed_reaction_immediate_addition_is_exact_but_ineligible():
    world, _ = load_world("reaction_kinetics", 7)
    control, treatment = reaction_specs()
    # Demonstrate the actual loophole: the known 0.8 mM addition is sampled
    # immediately, before the added material can undergo any reaction.
    difference = world.run(treatment)["values"][2][2] - world.run(control)["values"][2][2]
    assert difference == pytest.approx(0.8, abs=1e-12)
    decision = decide(world, control, treatment, "C", 2)
    assert decision == {"eligible": False, "reason": "readout_too_soon_after_event"}


def test_near_instant_addition_fails_but_delayed_added_and_downstream_readouts_pass():
    world, _ = load_world("reaction_kinetics", 46)
    control, treatment = reaction_specs()
    assert not decide(world, control, treatment, "C", 3)["eligible"]  # 0.25 s after addition.
    assert decide(world, control, treatment, "C", 4)["eligible"]  # Inclusive 1 s lag.
    assert decide(world, control, treatment, "D", 4)["eligible"]  # Other species can carry an effect.


def test_temperature_event_also_requires_evolution_in_either_arm():
    world, _ = load_world("reaction_kinetics", 7)
    control, treatment = reaction_specs()
    control["interventions"] = [{"time_s": 6.5, "kind": "temperature", "temperature_k": 340}]
    assert decide(world, control, treatment, "D", 4)["reason"] == "readout_too_soon_after_event"


def micro_spec(events=None):
    return {"initial": {"A": 0.1, "B": 0.1, "C": 0.1, "nutrient": 4.0},
            "temperature_c": 30, "times_h": [0, 12, 12.5, 13, 14], "events": events or []}


@pytest.mark.parametrize("name", ["microecology", "microecology_causal"])
def test_microdepletion_and_feed_require_one_hour_but_future_events_do_not(name):
    world, _ = load_world(name, 1439)
    control = micro_spec()
    treatment = micro_spec([{"time_h": 12, "deplete": {"channel": "peak-01", "fraction": 0.8}}])
    assert decide(world, control, treatment, "peak-01", 1)["reason"] == "readout_too_soon_after_event"
    assert not decide(world, control, treatment, "A", 2)["eligible"]
    assert decide(world, control, treatment, "A", 3)["eligible"]
    control["events"] = [{"time_h": 14, "feed": 1.0}]
    assert decide(world, control, treatment, "A", 3)["eligible"]
    control["events"] = [{"time_h": 12.5, "feed": 1.0}]
    assert not decide(world, control, treatment, "A", 3)["eligible"]


def test_gene_drive_event_requires_half_hour_response():
    world, _ = load_world("gene_regulation", 7)
    control = {"initial_expression": [0.4] * 4, "times_h": [0, 1, 1.25, 1.5]}
    treatment = dict(control, interventions=[{"time_h": 1, "kind": "set_drive", "drive": [2.5, 0, 0, 0]}])
    assert not decide(world, control, treatment, "G1", 1)["eligible"]
    assert not decide(world, control, treatment, "G2", 2)["eligible"]
    assert decide(world, control, treatment, "G2", 3)["eligible"]


@pytest.mark.parametrize("world_name,axis,channel,minimum", [
    ("microecology", "times_h", "A", 1.0),
    ("microecology_causal", "times_h", "A", 1.0),
    ("coupled_oscillators", "times", "x_A", 0.25),
    ("reaction_kinetics", "times_s", "B", 1.0),
    ("heat_transport", "times", "probe_1_temperature", 0.5),
    ("gene_regulation", "times_h", "G1", 0.5),
    ("hysteresis_material", "times", "response", 0.5),
    ("orbital_dynamics", "times", "vx", 0.25),
])
def test_all_declared_initial_state_resolution_boundaries(world_name, axis, channel, minimum):
    # Standalone semantics needs no world construction, parameter access or
    # numerical evaluation. Canonical shape/physical-range validation is upstream.
    control = {axis: [0, minimum - 1e-5, minimum]}
    treatment = copy.deepcopy(control)
    assert claim_eligibility(world_name, control, treatment, {"row": 0, "channel": channel}, axis)["reason"] == "readout_before_temporal_resolution"
    assert not claim_eligibility(world_name, control, treatment, {"row": 1, "channel": channel}, axis)["eligible"]
    assert claim_eligibility(world_name, control, treatment, {"row": 2, "channel": channel}, axis)["eligible"]


def test_material_ramp_knot_does_not_assign_response_or_restart_lag():
    world, _ = load_world("hysteresis_material", 7)
    control = {"reset": "negative", "preparation": [], "protocol": [{"time": 0, "field": 0}], "times": [0, 0.5, 10]}
    treatment = copy.deepcopy(control)
    treatment["protocol"] = [{"time": 0, "field": 0}, {"time": 10, "field": 0.8}]
    assert decide(world, control, treatment, "response", 2)["eligible"]


def test_oscillator_clamped_readout_fails_in_either_arm_but_downstream_and_cuts_pass():
    world, _ = load_world("coupled_oscillators", 7)
    control = {"times": [0, 0.25, 1], "initial_position": [0, .4, 0, 0]}
    treatment = dict(control, clamp=["A"])
    for channel in ("x_A", "v_A"):
        assert decide(world, control, treatment, channel, 2)["reason"] == "public_clamp_assigns_readout"
        assert not decide(world, treatment, control, channel, 2)["eligible"]
    assert decide(world, control, treatment, "x_B", 2)["eligible"]
    cut = dict(control, cut_edges=[["A", "B"]])
    assert decide(world, control, cut, "x_A", 1)["eligible"]


def test_ising_clamped_magnetization_and_two_clamped_endpoints_fail_in_either_arm():
    world, _ = load_world("ising_spin", 7)
    control = {"temperatures": [0.35, 0.5, 1.0]}
    assigned = dict(control, clamp={"A": 1, "B": -1})
    for channel in ("m_A", "m_B", "c_A_B"):
        assert decide(world, control, assigned, channel, 0)["reason"] == "public_clamp_assigns_readout"
        assert not decide(world, assigned, control, channel, 0)["eligible"]
    assert decide(world, control, assigned, "m_C", 0)["eligible"]
    assert decide(world, control, assigned, "c_A_C", 0)["eligible"]


def test_ising_single_endpoint_clamp_keeps_unknown_downstream_correlations_eligible():
    world, _ = load_world("ising_spin", 46)
    control = {"temperatures": [0.35, 1.0], "clamp": {"A": 1}}
    treatment = {"temperatures": [0.35, 1.0], "clamp": {"B": -1}}
    assert decide(world, control, treatment, "c_A_B", 0)["eligible"]
    unclamped = {"temperatures": [0.35, 1.0]}
    suppression = dict(unclamped, suppress_bonds=[{"nodes": ["A", "B"], "fraction": 1.0}])
    assert decide(world, unclamped, suppression, "m_C", 0)["eligible"]


def test_matched_time_is_required_for_time_dependent_worlds():
    result = claim_eligibility("reaction_kinetics", {"times_s": [1.0]}, {"times_s": [2.0]},
                               {"row": 0, "channel": "A"}, "times_s")
    assert result == {"eligible": False, "reason": "unmatched_readout_coordinate"}


def test_ising_temperature_itself_can_be_the_treatment():
    world, _ = load_world("ising_spin", 7)
    control = {"temperatures": [0.35]}
    treatment = {"temperatures": [2.0]}
    assert decide(world, control, treatment, "m_A", 0)["eligible"]
    assert decide(world, control, treatment, "c_A_B", 0)["eligible"]
    assert not decide(world, control, dict(treatment, clamp={"A": 1}), "m_A", 0)["eligible"]


def _reaction_submission(control, treatment, row, interval):
    return {"predictor_code": "def predict(spec):\n    return [[0.0]*4 for _ in spec['times_s']]\n",
            "explanation": "Integration fixture for the public claim-eligibility rule.",
            "claims": [{"id": "addition-effect", "statement": "Change in C after adding 0.8 mM C.",
                        "control": control, "treatment": treatment, "readout": {"row": row, "channel": "C"},
                        "interval": interval, "evidence_ids": ["obs-0001"], "scope": "Specified temperature, initial state and addition."}]}


def test_real_reaction_immediate_claim_fails_submission_and_direct_verification_scores_zero():
    world, _ = load_world("reaction_kinetics", 7)
    control, treatment = reaction_specs()
    value = _reaction_submission(world.validate(control), world.validate(treatment), 2, [0.79, 0.81])
    with pytest.raises(ValueError, match="ineligible.*readout_too_soon_after_event"):
        validate_submission(value, world, [{"id": "obs-0001"}])
    report = verify_claims(world, value["claims"], "integration-immediate")
    item = report["claims"][0]
    assert report["score"] == 0 and report["verified_nonzero_effects"] == 0
    assert item["eligibility"] == {"eligible": False, "reason": "readout_too_soon_after_event"}
    assert item["covered"] and item["mean_difference"] == pytest.approx(0.8, abs=0.01)
    assert not item["verified_nonzero_effect"]


def test_real_reaction_delayed_claim_can_commit_and_receive_positive_verification_score():
    world, _ = load_world("reaction_kinetics", 46)
    control, treatment = reaction_specs()
    # A test-only oracle interval checks integration, not an agent's discovery.
    difference = world.run(treatment)["values"][4][2] - world.run(control)["values"][4][2]
    value = _reaction_submission(control, treatment, 4, [difference - 0.01, difference + 0.01])
    checked = validate_submission(value, world, [{"id": "obs-0001"}])
    report = verify_claims(world, checked["claims"], "integration-delayed")
    assert report["claims"][0]["eligibility"]["eligible"]
    assert report["score"] > 0 and report["verified_nonzero_effects"] == 1


@pytest.mark.parametrize("updates,expected", [
    ({"world_name": "unknown"}, "unsupported_world"),
    ({"axis_field": "wrong"}, "mismatched_axis_field"),
    ({"readout": {"row": True, "channel": "A"}}, "invalid_readout"),
    ({"readout": {"row": 99, "channel": "A"}}, "invalid_readout"),
    ({"readout": {"row": 0, "channel": "unknown"}}, "invalid_readout"),
    ({"control": {"times_s": [float("nan")]}}, "invalid_public_spec"),
    ({"control": {"times_s": [10**1000]}}, "invalid_public_spec"),
    ({"control": {"times_s": [True]}}, "invalid_public_spec"),
    ({"control": {"times_s": [1], "interventions": [{"time_s": float("inf")}] }}, "invalid_public_spec"),
    ({"control": {"times_s": [1], "interventions": [None]}}, "invalid_public_spec"),
])
def test_malformed_inputs_fail_closed(updates, expected):
    args = {"world_name": "reaction_kinetics", "control": {"times_s": [1.0]},
            "treatment": {"times_s": [1.0]}, "readout": {"row": 0, "channel": "A"}, "axis_field": "times_s"}
    args.update(updates)
    assert claim_eligibility(**args) == {"eligible": False, "reason": expected}


def test_policy_is_detached_public_json_and_module_has_no_operator_imports():
    policy = policy_description()
    assert policy["minimum_lag"]["reaction_kinetics"]["value"] == 1.0
    assert "not hidden time constants" in policy["resolution_interpretation"]
    json.dumps(policy, allow_nan=False)
    policy["minimum_lag"]["reaction_kinetics"]["value"] = 999
    assert policy_description()["minimum_lag"]["reaction_kinetics"]["value"] == 1.0
    tree = ast.parse(Path(semantics.__file__).read_text())
    imports = [alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names]
    assert set(imports) == {"math", "numbers"}
    assert not any(isinstance(node, ast.ImportFrom) for node in ast.walk(tree))
