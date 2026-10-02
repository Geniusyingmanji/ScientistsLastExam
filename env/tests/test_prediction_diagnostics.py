"""Synthetic private-matrix diagnostics; never run a candidate or a World."""
import ast
from copy import deepcopy
import json
import math
from pathlib import Path

import pytest

from env import prediction_diagnostics as diagnostics
from env.prediction_semantics import SUPPORTED, classify_cells, known_controls_only


def panel(environment="coupled_oscillators", spec=None, index=0):
    if spec is None:
        spec = {"times": [0, 1, 2], "clamp": ["A"]} if environment == "coupled_oscillators" else {"temperatures": [1, 2], "clamp": {"A": 1}}
    rule = SUPPORTED[environment]
    classified = classify_cells(environment, spec, rule["channels"], rule["axis"], world_version=rule["version"])
    values = known_controls_only(classified)
    return {"index": index, "valid": True, "spec": deepcopy(spec), "prediction_values": deepcopy(values),
            "clean_truth": {"axis": list(spec[rule["axis"]]), "channels": list(rule["channels"]), "values": values}}


def diagnose(value, environment="coupled_oscillators", **kwargs):
    return diagnostics.diagnose_panel(environment, SUPPORTED[environment]["version"], value, **kwargs)


def test_partial_clamp_retains_free_nodes_and_public_normalization():
    value = panel()
    for row in value["prediction_values"]:
        for column in (1, 2, 3, 5, 6, 7):
            row[column] = .2 if column < 4 else .4
    result = diagnose(value)
    assert result["status"] == "ok"
    assert result["cell_counts"] == {"all_cells": 24, "legacy_scored_rows": 2,
        "legacy_scored_cells": 16, "excluded_initial_cells": 8, "direct_control_cells": 4,
        "residual_cells": 12, "direct_fraction_of_legacy_cells": .25}
    assert result["residual_metrics"]["normalized_rmse"] == pytest.approx(.2)
    assert result["residual_metrics"]["exponential_score"] == pytest.approx(100 * math.exp(-2))
    assert result["original_metrics_recomputed"]["normalized_rmse"] == pytest.approx(.2 * math.sqrt(.75))
    assert result["direct_control_metrics"]["normalized_rmse"] == 0
    assert result["channel_residual_metrics"][0] == {"channel": "x_A", "cells": 0, "normalized_rmse": None}
    assert result["channel_residual_metrics"][5]["normalized_rmse"] == pytest.approx(.2)
    assert result["residual_minus_original_exponential_score"] < 0


@pytest.mark.parametrize("environment,spec", [
    ("coupled_oscillators", {"times": [0, 1, 2], "clamp": list("ABCD")}),
    ("ising_spin", {"temperatures": [.35, 1, 6], "clamp": dict(zip("ABCDEF", [1, -1, 1, -1, 1, -1]))}),
])
def test_all_clamped_is_no_scientific_cells_never_a_residual_100(environment, spec):
    result = diagnose(panel(environment, spec), environment)
    assert result["status"] == "no_scientific_cells"
    assert result["cell_counts"]["residual_cells"] == 0
    assert result["residual_metrics"] is None
    assert result["residual_minus_original_exponential_score"] is None
    assert result["original_metrics_recomputed"]["exponential_score"] == 100
    assert all(item["normalized_rmse"] is None for item in result["channel_residual_metrics"])


def test_single_t0_only_row_has_no_residual_cells():
    value = panel(spec={"times": [0], "initial_position": [1, -.5, .1, .3]})
    result = diagnose(value)
    assert result["status"] == "no_scientific_cells"
    assert result["cell_counts"]["legacy_scored_rows"] == 1
    assert result["cell_counts"]["direct_control_cells"] == 8


def test_single_clamped_endpoint_pair_remains_in_residual():
    value = panel("ising_spin", {"temperatures": [1, 2], "clamp": {"A": 1, "B": -1}})
    column = value["clean_truth"]["channels"].index("c_A_C")
    for row in value["prediction_values"]:
        row[column] = .1
    result = diagnose(value, "ising_spin")
    assert result["status"] == "ok"
    assert result["cell_counts"]["direct_control_cells"] == 6
    assert result["cell_counts"]["residual_cells"] == 36
    assert result["residual_metrics"]["normalized_rmse"] == pytest.approx(.1 / math.sqrt(18))
    by_channel = {entry["channel"]: entry for entry in result["channel_residual_metrics"]}
    assert by_channel["c_A_C"]["cells"] == 2
    assert by_channel["c_A_B"]["cells"] == 0
    assert by_channel["m_C"]["cells"] == 2


def test_cell_fraction_does_not_determine_score_change_or_even_its_sign():
    free_error = panel()
    direct_error = panel()
    for row in free_error["prediction_values"]:
        row[1] = 1
    for row in direct_error["prediction_values"]:
        row[0] = 1
    left, right = diagnose(free_error), diagnose(direct_error)
    assert left["cell_counts"] == right["cell_counts"]
    assert left["residual_minus_original_exponential_score"] < 0
    assert right["residual_minus_original_exponential_score"] > 0
    assert right["residual_metrics"]["exponential_score"] == 100
    assert right["direct_control_metrics"]["normalized_rmse"] > 0
    assert not right["mechanism_certified"]


@pytest.mark.parametrize("environment,spec", [
    ("coupled_oscillators", {"times": [0, .5, 1]}),
    ("ising_spin", {"temperatures": [.5, 1, 2]}),
])
def test_no_direct_cells_matches_unmodified_prediction_formula(environment, spec):
    from env.scoring import prediction_metrics
    value = panel(environment, spec)
    for row_index, row in enumerate(value["prediction_values"]):
        for column in range(len(row)):
            row[column] += (row_index + column) * .01
    scales = [1] * 4 + [2] * 4 if environment == "coupled_oscillators" else [1] * 21
    original = prediction_metrics(value["prediction_values"], value["clean_truth"], scales)
    result = diagnose(value, environment)
    assert result["status"] == "ok"
    assert result["cell_counts"]["direct_control_cells"] == 0
    assert result["residual_metrics"]["normalized_rmse"] == pytest.approx(original["normalized_rmse"])
    assert result["residual_metrics"]["exponential_score"] == pytest.approx(original["score"])
    assert result["residual_minus_original_exponential_score"] == 0
    assert result["direct_control_metrics"] is None


def test_missing_matrix_stays_unknown_even_if_old_metrics_look_perfect():
    value = panel(spec={"times": [0, 1], "clamp": list("ABCD")})
    del value["prediction_values"]
    value.update(score=100, normalized_rmse=0, channel_normalized_rmse=[0] * 8)
    result = diagnose(value)
    assert result["status"] == "unknown" and result["reason"] == "missing_prediction_values"
    assert result["residual_metrics"] is None and result["original_metrics_recomputed"] is None
    assert result["cell_counts"]["residual_cells"] == 0


def test_explicit_invalid_prediction_is_not_reinterpreted_as_missing_data():
    value = panel()
    value.update(valid=False, prediction_values=None)
    result = diagnose(value)
    assert result["status"] == "invalid" and result["reason"] == "recorded_prediction_invalid"


@pytest.mark.parametrize("bad", [None, [], [[0]], [[0] * 8], [[0] * 8] * 4, "matrix"])
def test_absent_or_malformed_matrices_are_not_filled(bad):
    value = panel()
    value["prediction_values"] = bad
    result = diagnose(value)
    assert result["status"] == ("unknown" if bad is None else "invalid")
    assert result["residual_metrics"] is None


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -float("inf"), True, "0", 1e13])
def test_invalid_numbers_anywhere_are_rejected_before_masking(bad):
    value = panel(spec={"times": [0, 1], "clamp": list("ABCD")})
    value["prediction_values"][0][0] = bad  # Excluded initial row and clamped channel.
    result = diagnose(value)
    assert result["status"] == "invalid" and result["reason"] == "invalid_prediction_matrix"


@pytest.mark.parametrize("mutation,reason", [
    (lambda x: x["clean_truth"].update(axis=[0, 1, 3]), "clean_target_axis_mismatch"),
    (lambda x: x["clean_truth"].update(channels=list(reversed(x["clean_truth"]["channels"]))), "channel_contract_mismatch"),
    (lambda x: x["clean_truth"].update(values=[[0]]), "invalid_clean_target_matrix"),
    (lambda x: x["clean_truth"]["values"][1].__setitem__(0, .01), "clean_target_conflicts_with_public_control"),
    (lambda x: x["clean_truth"]["values"][0].__setitem__(1, .01), "clean_target_conflicts_with_public_control"),
    (lambda x: x["spec"].update(clamp=["invalid"]), "invalid_public_spec_or_axis"),
])
def test_invalid_target_or_public_contract_is_reported(mutation, reason):
    value = panel()
    mutation(value)
    result = diagnose(value)
    assert result["status"] == "invalid" and result["reason"] == reason
    assert result["residual_metrics"] is None


def test_roundoff_in_public_constant_is_allowed_but_mask_never_uses_target():
    value = panel()
    value["clean_truth"]["values"][1][0] = 1e-12
    result = diagnose(value)
    assert result["status"] == "ok"
    assert result["cell_counts"]["direct_control_cells"] == 4
    assert result["residual_metrics"]["normalized_rmse"] == 0


@pytest.mark.parametrize("environment,version,reason", [
    ("heat_transport", "heat_transport-0.2.0", "unsupported_environment"),
    ("gene_regulation", "gene_regulation-0.2.0", "unsupported_environment"),
    ("coupled_oscillators", "coupled_oscillators-9", "unsupported_world_version"),
    ("coupled_oscillators", None, "missing_or_invalid_environment_version"),
])
def test_unknown_semantics_never_get_residual_scores(environment, version, reason):
    result = diagnostics.diagnose_panel(environment, version, panel())
    assert result["status"] == "unknown" and result["reason"] == reason
    assert result["residual_metrics"] is None


def test_baseline_record_uses_same_target_and_requires_matching_index():
    value = panel(index=3)
    baseline = {"index": 3, "prediction_values": deepcopy(value["prediction_values"])}
    baseline["prediction_values"][1][1] = 1
    original = deepcopy((value, baseline))
    result = diagnose(value, prediction_record=baseline)
    assert result["status"] == "ok" and result["residual_metrics"]["normalized_rmse"] > 0
    assert (value, baseline) == original
    baseline["index"] = 4
    assert diagnose(value, prediction_record=baseline)["reason"] == "prediction_record_index_mismatch"


def test_report_preserves_missing_invalid_and_empty_attempts_without_new_score():
    empty = panel(spec={"times": [0, 1], "clamp": list("ABCD")}, index=0)
    missing = panel(index=1)
    del missing["prediction_values"]
    invalid = panel(index=2)
    invalid["valid"] = False
    report = {"episode_id": "synthetic", "environment": "coupled_oscillators", "world_version": SUPPORTED["coupled_oscillators"]["version"],
              "score": 99, "panels": {"interventions": [empty, missing, invalid]},
              "baseline_panels": {"interventions": [{"index": 2, "prediction_values": deepcopy(invalid["prediction_values"])},
                                                      {"index": 0, "prediction_values": deepcopy(empty["prediction_values"])}]}}
    snapshot = deepcopy(report)
    result = diagnostics.diagnose_report(report)
    assert result["status"] == "completed"
    assert result["status_counts"]["panels"] == {"no_scientific_cells": 1, "unknown": 1, "invalid": 1}
    assert result["status_counts"]["baseline_panels"] == {"no_scientific_cells": 1, "unknown": 1, "ok": 1}
    assert result["aggregate_replacement_score"] is None and not result["formal_score_modified"]
    assert report == snapshot
    json.dumps(result, allow_nan=False)


def test_report_rejects_duplicate_or_unmatched_baseline_entries():
    report = {"environment": "coupled_oscillators", "world_version": SUPPORTED["coupled_oscillators"]["version"],
              "panels": {"conditions": [panel()]}, "baseline_panels": {"conditions": [{"index": 0}, {"index": 0}]}}
    assert diagnostics.diagnose_report(report)["reason"] == "invalid_or_duplicate_panel_index"
    report["baseline_panels"]["conditions"] = [{"index": 3}]
    assert diagnostics.diagnose_report(report)["reason"] == "unmatched_baseline_index"


def test_module_has_no_world_candidate_api_filesystem_or_scoring_import():
    tree = ast.parse(Path(diagnostics.__file__).read_text(), feature_version=(3, 8))
    imports = [node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
    imports += [alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names]
    assert set(imports) <= {"collections", "math", "numbers", "prediction_semantics"}
    assert not any(isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in {
        "open", "exec", "eval", "compile", "__import__"} for node in ast.walk(tree))


def test_extra_baseline_panel_kind_cannot_be_silently_ignored():
    report = {"panels": {"conditions": []}, "baseline_panels": {"interventions": [{"index": 0}]}}
    assert diagnostics.diagnose_report(report)["reason"] == "unmatched_baseline_panel_kind"


def test_empty_report_is_explicit_and_has_no_replacement_score():
    result = diagnostics.diagnose_report({"panels": {}})
    assert result["status_counts"] == {"panels": {}, "baseline_panels": {}}
    assert result["aggregate_replacement_score"] is None
