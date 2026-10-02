"""Public-instrument semantic checks; no World or real target is imported."""
import ast
from copy import deepcopy
import inspect
import itertools
import json
from pathlib import Path

import pytest

from env import prediction_semantics as semantics


def classify(name, spec, channels=None, version=None):
    rule = semantics.SUPPORTED[name]
    return semantics.classify_cells(name, spec, rule["channels"] if channels is None else channels,
                                    rule["axis"], world_version=version)


def test_oscillator_clamp_and_initial_state_have_distinct_reasons():
    spec = {"times": [0, 1, 2], "clamp": ["B"],
            "initial_position": [.7, 0, -.3, .1], "initial_velocity": [.2, 0, -.5, 1]}
    original = deepcopy(spec)
    result = classify("coupled_oscillators", spec)
    assert result["known_values"][0] == [.7, 0, -.3, .1, .2, 0, -.5, 1]
    assert result["known_values"][1] == [None, 0, None, None, None, 0, None, None]
    assert result["reasons"][0][0] == "prescribed_initial_state"
    assert result["reasons"][0][1] == "oscillator_clamp"
    summary = semantics.summarize_cells(result)
    assert summary["all_cells"] == 24 and summary["directly_known_cells"] == 12
    assert summary["scored_cells"] == 16 and summary["directly_known_scored_cells"] == 4
    assert summary["direct_fraction_scored_cells"] == .25
    assert summary["scored_row_indices"] == [1, 2]
    assert spec == original


def test_sole_initial_row_is_scored_by_legacy_rule():
    result = classify("coupled_oscillators", {"times": [0], "initial_position": [1, 0, 0, 0]})
    summary = semantics.summarize_cells(result)
    assert summary["scored_rows"] == 1 and summary["direct_fraction_scored_cells"] == 1
    assert semantics.known_controls_only(result) == [[1, 0, 0, 0, 0, 0, 0, 0]]


def test_only_exact_t0_is_assigned_no_temporal_tolerance():
    result = classify("coupled_oscillators", {"times": [1e-13, .1]})
    assert not any(any(row) for row in result["known_mask"])
    assert semantics.summarize_cells(result)["excluded_initial_cells"] == 0


def test_unforced_zero_state_is_conservatively_unclassified():
    result = classify("coupled_oscillators", {"times": [0, 1]})
    assert all(result["known_mask"][0])
    assert not any(result["known_mask"][1])


def test_drive_force_and_cuts_do_not_assign_free_response():
    result = classify("coupled_oscillators", {"times": [1, 2], "cut_edges": [["A", "B"], ["A", "C"], ["A", "D"]],
                                             "drive": {"node": "A", "amplitude": 2, "frequency": 0, "phase": 1.5}})
    assert not any(any(row) for row in result["known_mask"])


@pytest.mark.parametrize("count", range(7))
def test_spin_known_count_is_means_plus_both_fixed_pairs(count):
    clamp = {node: 1 if index % 2 == 0 else -1 for index, node in enumerate("ABCDEF"[:count])}
    result = classify("ising_spin", {"temperatures": [.35, 1, 6], "clamp": clamp})
    known_per_row = count + count * (count - 1) // 2
    assert all(sum(row) == known_per_row for row in result["known_mask"])
    assert semantics.summarize_cells(result)["directly_known_scored_cells"] == 3 * known_per_row
    assert semantics.summarize_cells(result)["scored_rows"] == 3


def test_single_fixed_endpoint_is_not_a_known_numeric_pair():
    result = classify("ising_spin", {"temperatures": [1], "clamp": {"A": -1}}, channels=["c_A_B", "m_A", "m_B"])
    assert result["known_values"] == [[None, -1, None]]
    assert result["reasons"][0][0] == "one_clamped_endpoint_unknown_mean"
    assert semantics.known_controls_only(result) == [[0, -1, 0]]


def test_fixed_raw_pair_is_product_not_connected_covariance():
    result = classify("ising_spin", {"temperatures": [1, 2], "clamp": {"A": -1, "B": 1}}, channels=["c_A_B", "m_B", "m_A"])
    assert result["known_values"] == [[-1, 1, -1], [-1, 1, -1]]
    assert result["reasons"][0][0] == "spin_both_clamped_pair"


def test_constants_hold_under_arbitrary_weights_on_compatible_spin_states():
    clamp = {"A": -1, "C": 1, "F": -1}
    result = classify("ising_spin", {"temperatures": [1], "clamp": clamp})
    states = [state for state in itertools.product((-1, 1), repeat=6)
              if all(state["ABCDEF".index(node)] == value for node, value in clamp.items())]
    # Arbitrary unequal positive weights, independent of any world energy law.
    weights = [index + 1 for index in range(len(states))]
    for channel, value in zip(result["channels"], result["known_values"][0]):
        if value is None:
            continue
        nodes = [channel[2:]] if channel.startswith("m_") else channel[2:].split("_")
        moment = sum(weight * state["ABCDEF".index(nodes[0])] *
                     (state["ABCDEF".index(nodes[1])] if len(nodes) == 2 else 1)
                     for state, weight in zip(states, weights)) / sum(weights)
        assert moment == value


def test_strong_fields_or_full_bond_suppression_do_not_fix_free_spin_means():
    bonds = [{"nodes": [a, b], "fraction": 1} for a, b in itertools.combinations("ABCDEF", 2)]
    result = classify("ising_spin", {"temperatures": [.35, 6], "external_field": [2] * 6, "suppress_bonds": bonds})
    assert not any(any(row) for row in result["known_mask"])


@pytest.mark.parametrize("environment,axis", [("microecology", "times_h"), ("reaction_kinetics", "times_s"),
                                             ("heat_transport", "times"), ("gene_regulation", "times_h"),
                                             ("hysteresis_material", "times"), ("future_world", "coordinates")])
def test_other_environments_are_explicitly_unsupported(environment, axis):
    result = semantics.classify_cells(environment, {axis: [0, 1], "clamp": {"A": 1}}, ["m_A"], axis)
    assert result["supported"] is False
    assert result["known_values"] == [[None], [None]]
    assert result["reasons"] == [["unsupported_world"], ["unsupported_world"]]


def test_other_versions_and_unknown_channels_are_not_inferred():
    future = classify("ising_spin", {"temperatures": [1], "clamp": {"A": 1}}, version="ising_spin-9.0")
    assert not future["supported"] and not any(future["known_mask"][0])
    result = classify("ising_spin", {"temperatures": [1], "clamp": {"A": 1}}, channels=["m_A", "cov_A_B"])
    assert result["known_values"] == [[1, None]]
    assert result["reasons"][0][1] == "unsupported_channel"


@pytest.mark.parametrize("spec", [
    {"times": [0, 1], "clamp": ["A", "A"]},
    {"times": [0, 1], "clamp": ["E"]},
    {"times": [0, 1], "clamp": {"A": 0}},
    {"times": [0, 1], "clamp": ["A"], "initial_position": [1, 0, 0, 0]},
    {"times": [0, 1], "initial_velocity": [0, 0, 0, True]},
    {"times": [0, 1], "mass_add": [0, 0, 0, -1]},
    {"times": [0, 1], "cut_edges": [["A", "B"], ["B", "A"]]},
    {"times": [0, 1], "clamp": ["A"], "drive": {"node": "A", "amplitude": 1, "frequency": 1, "phase": 0}},
    {"times": [0, 1], "unknown": 1},
])
def test_malformed_oscillator_controls_are_rejected(spec):
    with pytest.raises(ValueError):
        classify("coupled_oscillators", spec)


@pytest.mark.parametrize("clamp", [{"A": 0}, {"A": True}, {"A": 1.0}, {"G": 1}, ["A"]])
def test_malformed_spin_clamps_are_rejected(clamp):
    with pytest.raises(ValueError):
        classify("ising_spin", {"temperatures": [1], "clamp": clamp})


@pytest.mark.parametrize("axis", [[], [0, 0], [1, 0], [float("nan")], [float("inf")], [True], [-1], [25], [0] * 242])
def test_invalid_axis_is_rejected(axis):
    with pytest.raises(ValueError):
        classify("coupled_oscillators", {"times": axis})


def test_wrong_axis_and_duplicate_channels_are_rejected():
    with pytest.raises(ValueError):
        semantics.classify_cells("ising_spin", {"times": [1]}, ["m_A"], "times")
    with pytest.raises(ValueError):
        classify("ising_spin", {"temperatures": [1]}, channels=["m_A", "m_A"])


def test_json_safe_detached_results_and_public_policy():
    one = classify("ising_spin", {"temperatures": [1], "clamp": {"A": 1}})
    two = classify("ising_spin", {"temperatures": [1], "clamp": {"A": 1}})
    one["known_mask"][0][0] = False
    assert two["known_mask"][0][0]
    policy = semantics.policy_description()
    policy["supported"]["ising_spin"]["max_rows"] = 999
    assert semantics.policy_description()["supported"]["ising_spin"]["max_rows"] == 32
    json.dumps(two, allow_nan=False)
    json.dumps(semantics.summarize_cells(two), allow_nan=False)


def test_module_has_no_target_input_world_import_io_or_dynamic_execution():
    assert set(inspect.signature(semantics.classify_cells).parameters) == {
        "environment", "spec", "channels", "axis_field", "world_version"}
    tree = ast.parse(Path(semantics.__file__).read_text(), feature_version=(3, 8))
    modules = [node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
    modules += [alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names]
    assert set(modules) <= {"collections", "copy", "math", "numbers"}
    assert not any(isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in {
        "open", "exec", "eval", "compile", "__import__"} for node in ast.walk(tree))
