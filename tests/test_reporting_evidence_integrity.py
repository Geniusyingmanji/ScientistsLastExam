"""Scientific reports retain endpoint, source identity and fixed-plan denominators."""
from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path

import pytest

from scripts import batch_evolve as batch
from scripts import report_admission_criterion as admission
from scripts import report_cross_model as cross
from scripts.reporting_trajectory import read_events, read_incumbents, trajectory_selection_evidence


def write_run(path: Path, *, model="m", seed=0, mode="normal", algorithm="greedy_rewrite",
              runtime="r", budget=3, condition=None, baseline=.6, score=.2, accepted=False):
    path.mkdir(parents=True)
    manifest = {"task_id": "Mathematics/CapSet", "seed": seed,
                "feedback_mode": mode, "algorithm": algorithm, "budget": budget,
                "task_package_sha256": "package", "runtime_source_sha256": runtime,
                "llm_condition_sha256": condition or "condition:" + model,
                "llm_condition": {"model": model}}
    (path / "run_manifest.json").write_text(json.dumps(manifest))
    events = [{"step": 0, "valid": True, "score": baseline, "metrics": {
        "combined_score": baseline, "heldout_mechanism_score": baseline,
        "heldout_false_discovery_rate": .1, "heldout_correct_refusal_rate": .4}}]
    for step in range(1, budget + 1):
        event = {"step": step, "valid": True, "score": score, "metrics": {
            "combined_score": score, "heldout_mechanism_score": score,
            "heldout_false_discovery_rate": .2, "heldout_correct_refusal_rate": .8}}
        if accepted is not None:
            event["accepted"] = accepted and step == 1
        events.append(event)
    (path / "trajectory.jsonl").write_text("\n".join(map(json.dumps, events)))
    return manifest


def run_report(module, root, tmp_path, *extra):
    output = tmp_path / (module.__name__.split(".")[-1] + ".json")
    with contextlib.redirect_stdout(io.StringIO()):
        module.main(["--runs", str(root), "--output", str(output), *extra])
    return json.loads(output.read_text())


def test_shared_reader_marks_legacy_and_rejects_score_metric_disagreement(tmp_path):
    write_run(tmp_path / "legacy", score=.8, accepted=None)
    path = tmp_path / "legacy/trajectory.jsonl"
    assert read_incumbents(path)[-1]["score"] == .8
    evidence = trajectory_selection_evidence(read_events(path))
    assert evidence["status"] == "legacy_inferred"
    assert evidence["missing_acceptance_steps"] == [1, 2, 3]
    events = read_events(path)
    events[1]["metrics"]["combined_score"] = .9
    path.write_text("\n".join(map(json.dumps, events)))
    with pytest.raises(ValueError, match=r"legacy/trajectory.jsonl.*metrics.combined_score at step 1"):
        read_incumbents(path)


def test_cross_model_uses_recorded_incumbent_and_surfaces_unresolved_legacy(tmp_path):
    root = tmp_path / "runs"
    write_run(root / "recorded", model="recorded")
    write_run(root / "legacy", model="legacy", score=.8, accepted=None)
    report = run_report(cross, root, tmp_path)
    records = {row["model"]: row for row in report["run_records"]}
    assert records["recorded"]["best"] == .6
    assert records["legacy"]["selection_evidence"]["status"] == "legacy_inferred"
    assert report["excluded_run_count"] == 1
    assert report["shared_tasks"] == []


@pytest.mark.parametrize("changed", [{"runtime": "r2"}, {"algorithm": "openevolve"}, {"budget": 6}])
def test_cross_model_rejects_different_comparison_conditions(tmp_path, changed):
    root = tmp_path / "runs"
    write_run(root / "a", model="a", mode="selection_blind")
    write_run(root / "b", model="b", mode="selection_blind", **changed)
    report = run_report(cross, root, tmp_path)
    assert report["shared_tasks"] == []
    assert len(report["pairwise"][0]["excluded_for_contract_mismatch"]) == 1


def test_cross_model_does_not_pool_two_conditions_of_same_model(tmp_path):
    root = tmp_path / "runs"
    write_run(root / "a1", model="a", mode="selection_blind", condition="c1")
    write_run(root / "a2", model="a", mode="selection_blind", condition="c2", seed=1)
    write_run(root / "b", model="b", mode="selection_blind")
    report = run_report(cross, root, tmp_path)
    assert report["shared_tasks"] == []
    assert len(report["score_rows"]) == 3
    assert report["open_loop_scores"]["a"] == {}


def test_legacy_inferred_selection_cannot_admit_iteration(tmp_path):
    root = tmp_path / "runs"
    write_run(root / "cohort/legacy", score=.8, accepted=None)
    report = run_report(admission, root, tmp_path)
    assert report["rows"][0]["selection_evidence_status"] == "legacy_inferred"
    assert report["rows"][0]["verdict"] == "unresolved_selection"
    assert report["distinct_tasks_measuring_iteration"] == []


def test_cross_model_preserves_multiple_versions_regardless_of_row_order(tmp_path):
    root = tmp_path / "runs"
    root.mkdir()
    common = {"task": "T/X", "runtime_source_sha256": "r", "algorithm": "greedy_rewrite",
              "budget": 12, "verdict": "measures_iteration"}
    rows = [dict(common, model="a", llm_condition_sha256="ca", task_version="v1"),
            dict(common, model="a", llm_condition_sha256="ca", task_version="v2", verdict="thin_screen"),
            dict(common, model="b", llm_condition_sha256="cb", task_version="v1")]
    path = tmp_path / "admission.json"
    observed = []
    for ordering in (rows, list(reversed(rows))):
        path.write_text(json.dumps({"rows": ordering}))
        report = run_report(cross, root, tmp_path, "--admission", str(path))
        assert len(report["verdict_rows"]) == 3
        assert len(report["ambiguous_legacy_verdicts"]) == 1
        assert len(report["verdicts_same_version"]) == 1
        observed.append(report["verdicts_same_version"])
    assert observed[0] == observed[1]


def test_admission_separates_algorithms_and_preserves_run_paths(tmp_path):
    root = tmp_path / "runs"
    write_run(root / "cohort/a", algorithm="greedy_rewrite")
    write_run(root / "cohort/b", algorithm="openevolve")
    report = run_report(admission, root, tmp_path)
    assert report["schema_version"] == 3
    assert {r["algorithm"] for r in report["rows"]} == {"greedy_rewrite", "openevolve"}
    assert len({r["runs"][0]["run_directory"] for r in report["rows"]}) == 2
    write_run(root / "cohort/duplicate", algorithm="openevolve")
    with pytest.raises(ValueError, match="ambiguous duplicate run cell"):
        admission.collect(root)








def test_plan_denominator_is_fixed_and_legacy_scope_explicit():
    config = {"tasks": ["T/X", "T/Y"], "algorithms": ["greedy_rewrite"],
              "feedback_modes": ["normal", "selection_blind"], "seeds": [0, 1]}
    run = {"task": "T/X", "algorithm": "greedy_rewrite", "feedback_mode": "normal",
           "seed": 0, "best": .4, "summary": {"best_so_far_auc": .4,
           "budget_units": 3, "oracle_calls": 4, "wall_seconds": 1, "llm": {}}}
    from sle.runtime_identity import current_runtime_descriptor
    runtime = current_runtime_descriptor(())
    run.update(trusted_evaluator_runtime=runtime,
               trusted_evaluator_runtime_sha256=runtime["fingerprint_sha256"])
    report = batch.aggregate_runs([run], config=config)
    assert report["schema_version"] == 2
    assert report["denominator_scope"] == "fixed_plan"
    assert report["intent_to_evaluate"]["completion_rate"] == 1 / 8
    assert report["intent_to_evaluate"]["missing_runs"] == 7
    assert batch.aggregate_runs([run])["denominator_scope"] == "observed_runs_only_legacy"


def test_real_run_manifest_uses_summary_budget_and_sums_per_call_tokens(tmp_path):
    from sle.algorithms.common import ensure_run_manifest, write_summary
    from sle.llm import LLMClient, LLMConfig
    from sle.protocol import TrajectoryEvent, summarize_trajectory
    from sle.registry import find_task

    directory = tmp_path / "actual-format"
    directory.mkdir()
    spec = find_task("Chemistry/LennardJonesCluster")
    manifest = ensure_run_manifest(
        directory, spec=spec, llm=LLMClient(LLMConfig(model="fixture")),
        algorithm="greedy_rewrite", seed=0, feedback_mode="selection_blind", resume=False)
    assert "budget" not in manifest
    events = []
    for step in range(3):
        score = .6 if step == 0 else .2
        events.append(TrajectoryEvent(
            step=step, oracle_calls=step + 1, budget_units=step + 1,
            score=score, best_score=.6, valid=True, accepted=step == 0,
            wall_seconds=1, cumulative_wall_seconds=step + 1,
            candidate_sha256=str(step) * 64, parent_sha256="0" * 64,
            metrics={"combined_score": score, "valid": 1},
            llm={"input_tokens": 10 + step, "output_tokens": 20 + step,
                 "total_tokens": 30 + 2 * step} if step else {}).to_dict())
    (directory / "trajectory.jsonl").write_text("\n".join(map(json.dumps, events)))
    summary = summarize_trajectory(events, budget=3)
    summary.update(budget=2, task_id=spec.task_id, algorithm="greedy_rewrite", seed=0,
                   feedback_mode="selection_blind")
    write_summary(directory, summary)
    row = cross.read_runs(tmp_path)[0]
    assert row["status"] == "ok"
    assert row["budget"] == 2
    assert row["budget_source"] == "summary.json"
    assert row["best"] == .6
    assert row["input_tokens"] == 23
    assert row["output_tokens"] == 43
    assert row["trusted_evidence"] is False
    assert row["verification_status"] == "unverified"
    assert not cross.attributable_score_run(row)
    summary["budget"] = 3
    write_summary(directory, summary)
    row = cross.read_runs(tmp_path)[0]
    assert row["status"] == "incomplete_proposal_horizon"
    assert not cross.attributable_score_run(row)
