"""Archived scalar diagnostics only; no World, candidate execution or model API."""

import ast
from copy import deepcopy
import json
import math
from pathlib import Path

import pytest

from env import predictability_diagnostics as audit


def row(index, error, *, candidate=True, score=None, scored_rows=2):
    value = {"index": index, "normalized_rmse": error, "score": 100 * math.exp(-error/.1) if score is None else score,
             "scored_rows": scored_rows}
    if candidate:
        value["valid"] = True
    return value


def manifest(count=2, episodes=1, cohort="fixture"):
    return {"cohort": cohort, "instances": [{"episode_id": "case-%d" % index, "environment": "example"}
                                            for index in range(episodes)], "limits": {"panel_count": count}}


def report(index=0, candidate=(.1, .3), baseline=(.2, .2), **kwargs):
    value = {"episode_id": "case-%d" % index, "environment": "example", "status": "completed",
             "model_completed": True, "infrastructure_failure": None,
             "panels": {kind: [row(i, error) for i, error in enumerate(candidate)] for kind in audit.KINDS},
             "baseline_panels": {kind: [row(i, error, candidate=False) for i, error in enumerate(baseline)] for kind in audit.KINDS}}
    value.update(kwargs)
    return value


def condition(result):
    return next(item for item in result["public"]["world_summaries"] if item["panel_kind"] == "conditions")


def test_uniform_experiment_mse_ratio_of_means_and_original_scores():
    value = report()
    value["panels"]["conditions"][1]["scored_rows"] = 200
    value["baseline_panels"]["conditions"][1]["scored_rows"] = 200
    result = audit.audit_reports(manifest(), {"case-0": value})
    metrics = condition(result)["paired_metrics"]
    assert metrics["candidate_mean_mse"] == pytest.approx(.05)
    assert metrics["baseline_mean_mse"] == pytest.approx(.04)
    assert metrics["skill"] == pytest.approx(-.25)
    assert metrics["candidate_pooled_nrmse"] == pytest.approx(math.sqrt(.05))
    expected_score = 50 * (math.exp(-1) + math.exp(-3))
    assert metrics["candidate_original_prediction_score_mean"] == pytest.approx(expected_score)
    assert expected_score != pytest.approx(100 * math.exp(-math.sqrt(.05)/.1))
    assert metrics["candidate_lower_error_panels"] == metrics["candidate_higher_error_panels"] == 1


def test_index_pairing_is_not_list_position_and_skill_is_not_mean_panel_skill():
    value = report(candidate=(.1, .4), baseline=(.1, .2))
    value["baseline_panels"]["conditions"].reverse()
    metrics = condition(audit.audit_reports(manifest(), {"case-0": value}))["paired_metrics"]
    assert metrics["skill"] == pytest.approx(1 - (.01+.16)/(.01+.04))
    assert metrics["skill"] != pytest.approx((0 + (1-.16/.04))/2)
    assert metrics["equal_error_panels"] == 1


def test_higher_mean_exponential_score_can_coexist_with_worse_mean_mse():
    metrics = condition(audit.audit_reports(manifest(), {"case-0": report(candidate=(0,1))}))["paired_metrics"]
    assert metrics["candidate_original_prediction_score_mean"] > metrics["baseline_original_prediction_score_mean"]
    assert metrics["candidate_mean_mse"] > metrics["baseline_mean_mse"]
    assert metrics["skill"] < 0


def test_failure_denominators_retained_and_partial_valid_pairs_are_explicit():
    good = report()
    partial = report(1, status="invalid_predictor", model_completed=False)
    partial["panels"]["conditions"][1] = {"index": 1, "valid": False, "score": 0, "normalized_rmse": None}
    infra = report(2, status="failed", model_completed=False, infrastructure_failure="provider_error", panels={}, baseline_panels={})
    incomplete = report(3, status="incomplete", model_completed=False, panels={}, baseline_panels={})
    result = audit.audit_reports(manifest(episodes=5), {"case-0": good, "case-1": partial, "case-2": infra, "case-3": incomplete})
    public, summary = result["public"], condition(result)
    assert public["planned_episodes"] == 5
    assert public["episode_counts"] == {"completed": 1, "invalid_predictor": 1, "incomplete": 1,
        "other_model_failure": 0, "infrastructure_failure": 1, "missing_report": 1, "unreadable_report": 0}
    assert summary["counts"]["expected_panels"] == 10 and summary["counts"]["paired_panels"] == 3
    assert summary["counts"]["exclusion_reasons"] == {"candidate_invalid": 1, "candidate_missing": 6}
    assert summary["paired_panels_by_episode_category"]["invalid_predictor"] == 1
    assert summary["paired_panels_by_episode_category"]["completed"] == 2
    assert summary["paired_metrics"]["candidate_mean_mse"] == pytest.approx((.01+.09+.01)/3)
    assert "score" not in public and "aggregate_score" not in public


@pytest.mark.parametrize("bad", [None, True, -1, "0", float("nan"), float("inf"), 1e308, 10**1000])
def test_nonfinite_negative_or_overflowing_errors_are_unavailable_not_zero(bad):
    value = report()
    value["panels"]["conditions"][0]["normalized_rmse"] = bad
    summary = condition(audit.audit_reports(manifest(), {"case-0": value}))
    assert summary["counts"]["paired_panels"] == 1
    assert summary["counts"]["exclusion_reasons"] == {"candidate_malformed": 1}
    assert summary["paired_metrics"]["candidate_mean_mse"] == pytest.approx(.09)


@pytest.mark.parametrize("mutation,reason", [
    (lambda x: x["baseline_panels"]["conditions"].append(row(0,.3,candidate=False)), "baseline_duplicate_index"),
    (lambda x: x["panels"]["conditions"].append(row(0,.3)), "candidate_duplicate_index"),
    (lambda x: x["baseline_panels"]["conditions"].pop(0), "baseline_missing"),
    (lambda x: x["baseline_panels"]["conditions"][0].update(valid=False), "baseline_invalid"),
    (lambda x: x["baseline_panels"]["conditions"][0].update(score=101), "baseline_malformed"),
    (lambda x: x["baseline_panels"]["conditions"][0].update(scored_rows=3), "scored_rows_mismatch"),
    (lambda x: x["panels"]["conditions"][0].pop("valid"), "candidate_malformed"),
])
def test_ambiguous_or_incompatible_pairs_are_explicitly_excluded(mutation, reason):
    value = report()
    mutation(value)
    summary = condition(audit.audit_reports(manifest(), {"case-0": value}))
    assert summary["counts"]["paired_panels"] == 1
    assert summary["counts"]["exclusion_reasons"] == {reason: 1}


def test_unknown_indices_and_malformed_rows_do_not_increase_denominator_or_enter_pairs():
    value = report()
    value["panels"]["conditions"] += [row(4,0), {"index": True}, None]
    summary = condition(audit.audit_reports(manifest(), {"case-0": value}))
    assert summary["counts"]["unexpected_candidate_rows"] == 1
    assert summary["counts"]["malformed_candidate_rows"] == 2
    assert summary["counts"]["paired_panels"] == summary["counts"]["expected_panels"] == 2


@pytest.mark.parametrize("error", [0, 1e-7, 1e-6])
def test_near_zero_baseline_is_undefined_never_forced_zero_or_one(error):
    metrics = condition(audit.audit_reports(manifest(), {"case-0": report(baseline=(error,error))}))["paired_metrics"]
    assert metrics["skill"] is None and metrics["skill_undefined_reason"] == "baseline_near_zero"
    assert metrics["baseline_mean_mse"] == error**2


def test_a_zero_baseline_panel_does_not_destroy_well_defined_pooled_ratio():
    metrics = condition(audit.audit_reports(manifest(), {"case-0": report(baseline=(0,.2))}))["paired_metrics"]
    assert metrics["skill"] == pytest.approx(-1.5)


def test_no_pairs_is_explicit_null_and_private_canaries_cannot_escape_allowlist():
    value = report(panels={}, baseline_panels={}, world_seed="SECRET_SEED", explanation="SECRET_TEXT")
    value["records"] = [{"spec": "SECRET_SPEC", "observation": "SECRET_TARGET"}]
    value["stop_reason"] = "SECRET_STOP"
    original = deepcopy(value)
    result = audit.audit_reports(manifest(), {"case-0": value, "extra-private-name": value})
    assert value == original
    metrics = condition(result)["paired_metrics"]
    assert metrics["skill"] is None and metrics["candidate_mean_mse"] is None
    assert metrics["candidate_original_prediction_score_mean"] is None
    assert metrics["skill_undefined_reason"] == "no_valid_pairs"
    public = json.dumps(result["public"], allow_nan=False)
    assert "SECRET" not in public and "extra-private-name" not in public and "case-0" not in public
    assert result["public"]["unplanned_reports"] == 1


@pytest.mark.parametrize("change", [{"episode_id": "wrong"}, {"environment": "wrong"}, {"cohort": "wrong"}])
def test_report_identity_mismatch_cannot_be_attributed_to_planned_episode(change):
    result = audit.audit_reports(manifest(), {"case-0": report(**change)})
    assert result["public"]["episode_counts"]["unreadable_report"] == 1
    assert condition(result)["counts"]["paired_panels"] == 0


def write_fixture(root, name="fixture"):
    directory = root / name
    directory.mkdir()
    (directory / "manifest-private.json").write_text(json.dumps(manifest(cohort=name)))
    episode = directory / "episodes" / "case-0"
    episode.mkdir(parents=True)
    (episode / "report.json").write_text(json.dumps(report()))
    return directory


def test_archive_hashes_read_only_outputs_exclusive_and_batches_separate(tmp_path):
    left, right = write_fixture(tmp_path, "left"), write_fixture(tmp_path, "right")
    plan = tmp_path / "plan.json"
    plan.write_text(json.dumps({"protocol": audit.PROTOCOL, "cohorts": ["left", "right"]}))
    before = {str(path): path.read_bytes() for directory in (left,right) for path in directory.rglob("*.json")}
    output = tmp_path / "new-audit"
    public = audit.write_audit([left,right], output, analysis_plan=plan)
    assert [row["cohort"] for row in public["cohorts"]] == ["left", "right"]
    assert not any(key in public for key in ("aggregate", "total_score", "all_cohorts"))
    assert all(Path(path).read_bytes() == value for path,value in before.items())
    private = json.loads((output / "private-detail.json").read_text())
    assert len(private["cohorts"][0]["private_provenance"]["input_sha256"]) == 2
    assert json.loads((output / "public-summary.json").read_text()) == public
    with pytest.raises(FileExistsError):
        audit.write_audit([left,right], output, analysis_plan=plan)
    with pytest.raises(ValueError, match="separate"):
        audit.write_audit([left,right], left / "forbidden", analysis_plan=plan)


def test_missing_and_unreadable_reports_remain_planned_and_changed_inputs_fail(tmp_path):
    directory = write_fixture(tmp_path)
    path = directory / "episodes" / "case-0" / "report.json"
    path.write_text("{broken")
    result = audit.audit_cohort(directory)
    assert result["public"]["episode_counts"]["unreadable_report"] == 1
    provenance = result["private_provenance"]["input_sha256"]
    path.write_text("{}")
    with pytest.raises(ValueError, match="input changed"):
        audit.verify_inputs(provenance)
    path.unlink()
    assert audit.audit_cohort(directory)["public"]["episode_counts"]["missing_report"] == 1


def test_no_world_candidate_network_or_scorer_import_and_python38_syntax():
    tree = ast.parse(Path(audit.__file__).read_text(), feature_version=(3,8))
    modules = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            modules.append(node.module)
    assert set(modules) <= {"argparse", "collections", "hashlib", "json", "math", "pathlib", "re"}
