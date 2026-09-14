#!/usr/bin/env python3
"""Gate a task against the contribution contract, without claiming certification.

New packages start as `candidate`. This does not promote them. It asks the questions
CONTRIBUTING.md already has scripts for, on one task, so a debug run with hy3 is not
the first time a missing key or a crashing evaluator shows up.

    python scripts/check_task_contribution.py --task MaterialsScience/PhaseDiagramDiscovery

Exit 0 requires all contribution checks, including declared shortcuts, to run and pass.
Exit 2 means incomplete/skipped/migration pending; exit 1 means a failed check.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.audit_documented_keys import (  # noqa: E402
    evaluator_problem_keys,
    submission_keys,
    subscript_keys,
)
from scripts.audit_tasks import (  # noqa: E402
    REQUIRED_FILES,
    REQUIRED_METADATA,
    _task_card_issues,
)
from scripts.check_evaluator_survives_bad_candidates import BAD_CANDIDATES  # noqa: E402
from scripts.check_numeric_keys_hold_numbers import offending_keys  # noqa: E402
from sle.certification import certification_status, load_certification  # noqa: E402
from sle.evaluate import INVALID_SCORE, evaluate_candidate  # noqa: E402
from sle.frontier import load_frozen_wave  # noqa: E402
from sle.registry import find_task, list_tasks  # noqa: E402
from scripts.shortcut_probe_contract import inspect_probe  # noqa: E402

DISCOVERY_AXES = (
    "development_false_discovery_rate",
    "false_discovery_rate",
    "heldout_false_discovery_rate",
)
DISCOVERY_REFUSAL = (
    "development_correct_refusal_rate",
    "correct_refusal_rate",
    "heldout_correct_refusal_rate",
)
DISCOVERY_MECHANISM = (
    "heldout_mechanism_score",
    "mechanism_score",
    "development_mechanism_score",
    "development_body_support_f1",
    "heldout_supported_correct_model_rate",
    "development_supported_correct_model_rate",
    "heldout_hypothesis_score",
    "development_hypothesis_score",
)
DISCOVERY_COVERAGE = (
    "heldout_discovery_coverage",
    "development_discovery_coverage",
    "development_supported_claim_coverage",
    "development_attempt_rate",
    "discovery_coverage",
)
BASELINE_ZERO_TOLERANCE = 0.05


def _fail(rows: list[dict], check: str, detail: str) -> None:
    rows.append({"check": check, "ok": False, "status": "failed", "detail": detail})


def _ok(rows: list[dict], check: str, detail: str = "") -> None:
    rows.append({"check": check, "ok": True, "status": "passed", "detail": detail})


def _skip(rows: list[dict], check: str, detail: str = "not evaluated") -> None:
    rows.append({"check": check, "ok": None, "status": "skipped", "detail": detail})


def _evaluate(spec, path, *, timeout_s):
    try:
        metrics = evaluate_candidate(spec, path, timeout_s=timeout_s)
        if not isinstance(metrics, dict) or any(
            type(metrics.get(key)) not in (int, float) or not math.isfinite(metrics[key])
            for key in ("combined_score", "valid")
        ):
            raise ValueError("non-finite or missing scalar metrics")
        return metrics
    except Exception as exc:
        return {"combined_score": INVALID_SCORE, "valid": 0.0, "infrastructure_failure": True,
                "error_message": "evaluation failed: " + type(exc).__name__}


def check_task(task_id: str, timeout_s: float = 180.0, *, skip_eval: bool = False) -> dict:
    spec = find_task(task_id, include_uncertified=True)
    rows: list[dict] = []
    listed = any(item.task_id == spec.task_id for item in list_tasks(None))
    if listed:
        _ok(rows, "listed_in_all", spec.task_id)
    else:
        _fail(rows, "listed_in_all", "not visible to python -m sle list --all")

    status = certification_status(spec.task_id)
    if spec.task_id in load_certification()["tasks"]:
        _ok(rows, "registered_in_certification", spec.task_id)
    else:
        _fail(rows, "registered_in_certification", "missing explicit certification.yaml record")
    if status not in {"candidate", "certified"}:
        _fail(rows, "certification_status", status)
    else:
        _ok(rows, "certification_status", status)
        if status == "certified":
            _ok(rows, "not_self_certified", "already certified; gate does not promote")
        else:
            _ok(rows, "not_self_certified", "candidate")

    missing_files = [path for path in REQUIRED_FILES if not (spec.task_dir / path).is_file()]
    card = spec.task_dir / "TASK_CARD.yaml"
    if not card.is_file():
        missing_files.append("TASK_CARD.yaml")
    if missing_files:
        _fail(rows, "required_files", ", ".join(missing_files))
    else:
        _ok(rows, "required_files", "")

    card_issues = _task_card_issues(card)
    if card_issues:
        _fail(rows, "task_card", "; ".join(card_issues))
    else:
        _ok(rows, "task_card", str(card.relative_to(ROOT)))

    missing_meta = [key for key in REQUIRED_METADATA if key not in spec.metadata]
    if "scientific_role" not in spec.metadata:
        missing_meta.append("scientific_role")
    if missing_meta:
        _fail(rows, "metadata", "missing " + ", ".join(sorted(set(missing_meta))))
    else:
        _ok(rows, "metadata", spec.metadata.get("scientific_role", ""))

    wave = None
    try:
        wave = load_frozen_wave(spec)
    except ValueError as exc:
        _fail(rows, "frontier_wave", str(exc))
    else:
        detail = "legacy single wave" if wave is None else "%s/%s" % (
            wave.task_family_id, wave.wave_id
        )
        _ok(rows, "frontier_wave", detail)

    role = str(spec.metadata.get("scientific_role") or "")
    task_md = spec.task_dir / "Task.md"
    prose = task_md.read_text(encoding="utf-8") if task_md.is_file() else ""
    if role == "discovery":
        if "contract_lint" in prose:
            _ok(rows, "discovery_contract_lint_documented", "")
        else:
            _fail(rows, "discovery_contract_lint_documented", "Task.md never names contract_lint")

    evaluator = spec.task_dir / "verification" / "evaluator.py"
    source = evaluator.read_text(encoding="utf-8") if evaluator.is_file() else ""
    numeric = offending_keys(source) if source else []
    if numeric:
        _fail(rows, "numeric_keys", repr(numeric[:3]))
    else:
        _ok(rows, "numeric_keys", "")

    initial_source = (spec.initial_program_path.read_text(encoding="utf-8")
                      if spec.initial_program_path.is_file() else "")
    keys = subscript_keys(initial_source)
    keys |= evaluator_problem_keys(source)
    constraints = spec.eval_dir / "constraints.txt"
    if constraints.is_file():
        prose += constraints.read_text(encoding="utf-8")
    undocumented = sorted(k for k in keys if k not in prose)
    undocumented_sub = sorted(k for k in submission_keys(source) if k not in prose)
    if undocumented or undocumented_sub:
        _fail(rows, "documented_keys",
              "inputs=%s submission=%s" % (undocumented, undocumented_sub))
    else:
        _ok(rows, "documented_keys", "%d baseline keys" % len(keys))

    if str(spec.metadata.get("score_mode")) == "uncapped":
        lower = prose.lower()
        if "clipped to" in lower and ("[0, 1]" in lower or "to one" in lower):
            _fail(rows, "uncapped_prompt", "Task.md still claims a clip to one")
        else:
            _ok(rows, "uncapped_prompt", "")

    structural_count = len(rows)
    baseline: dict = {}
    if skip_eval:
        _skip(rows, "baseline_eval")
        _skip(rows, "deterministic_baseline")
        if role == "discovery":
            _skip(rows, "discovery_axes")
            _skip(rows, "degenerate_candidates_score_zero")
        _skip(rows, "bad_candidates_score_zero")
        if wave is not None:
            _skip(rows, "frontier_degenerate_credit_zero")
    else:
        baseline = _evaluate(spec, spec.initial_program_path, timeout_s=timeout_s)
        score = float(baseline.get("combined_score", -1e18))
        valid = float(baseline.get("valid", 0.0))
        if baseline.get("infrastructure_failure"):
            _fail(rows, "baseline_eval",
                  str(baseline.get("error_message") or "infrastructure_failure"))
        elif valid < 1.0:
            _fail(rows, "baseline_eval", "valid=%s score=%s" % (valid, score))
        elif abs(score) > BASELINE_ZERO_TOLERANCE:
            _fail(rows, "baseline_eval", "baseline is not near zero: %s" % score)
        else:
            _ok(rows, "baseline_eval", "combined_score=%s" % score)

        repeat = _evaluate(spec, spec.initial_program_path, timeout_s=timeout_s)
        if baseline.get("infrastructure_failure") or repeat.get("infrastructure_failure"):
            _fail(rows, "deterministic_baseline", "infrastructure failure is not determinism evidence")
        elif repeat != baseline:
            _fail(rows, "deterministic_baseline",
                  "full metric payload changed between identical evaluations")
        else:
            _ok(rows, "deterministic_baseline", "")

        frontier_offenders = []
        if wave is not None:
            for label, metrics in (("baseline", baseline), ("repeat_baseline", repeat)):
                if metrics.get("infrastructure_failure") or metrics.get("frontier_records") != []:
                    frontier_offenders.append(label + ": expected empty frontier_records")

        if role == "discovery":
            has_mechanism = any(key in baseline for key in DISCOVERY_MECHANISM)
            has_fdr = any(key in baseline for key in DISCOVERY_AXES)
            has_refusal = any(key in baseline for key in DISCOVERY_REFUSAL)
            has_coverage = any(key in baseline for key in DISCOVERY_COVERAGE)
            if has_mechanism and has_fdr and has_refusal and has_coverage:
                _ok(rows, "discovery_axes",
                    "mechanism/fdr/refusal/coverage rates present")
            else:
                _fail(rows, "discovery_axes",
                      "mechanism=%s fdr=%s refusal=%s coverage=%s"
                      % (has_mechanism, has_fdr, has_refusal, has_coverage))

        # A degenerate candidate is not a broken one. The bad-candidate sweep below asks whether
        # a malformed submission is rejected; this asks whether a *well-formed* submission that
        # does no science scores nothing. For a discovery task the universal case is blanket
        # abstention: the whole three-axis normalisation rests on it being exactly zero, because a
        # candidate that refuses everything is perfect on false-discovery and on refusal and has
        # discovered nothing. FrontierMath makes the same demand of guessing, at under one per
        # cent. Until now this was pinned per task by hand-written tests, which meant a new task
        # could ship without it.
        if role == "discovery":
            degenerate = {
                "blanket_abstention":
                    "def {entry}(*args, **kwargs):\n    return {{'abstain': True}}\n",
                "blanket_abstention_with_confidence":
                    "def {entry}(*args, **kwargs):\n"
                    "    return {{'abstain': True, 'confidence': 1.0}}\n",
            }
            offenders = []
            for kind, template in degenerate.items():
                with tempfile.TemporaryDirectory(prefix="degenerate_") as tmp:
                    candidate = Path(tmp) / "candidate.py"
                    candidate.write_text(template.format(entry=spec.entrypoint), encoding="utf-8")
                    try:
                        metrics = evaluate_candidate(spec, candidate, timeout_s=timeout_s)
                    except Exception as exc:  # noqa: BLE001
                        offenders.append("%s:%s" % (kind, exc))
                        frontier_offenders.append("%s:evaluation failed" % kind)
                        continue
                    if metrics.get("infrastructure_failure"):
                        offenders.append("%s:infrastructure_failure" % kind)
                        frontier_offenders.append("%s:infrastructure_failure" % kind)
                        continue
                    degenerate_score = float(metrics.get("combined_score", INVALID_SCORE))
                    # Scoring zero is the requirement. Being rejected outright is acceptable too:
                    # a task whose contract has no abstain key simply cannot be gamed this way.
                    if float(metrics.get("valid", 0.0)) == 0.0:
                        continue
                    if wave is not None and metrics.get("frontier_records") != []:
                        frontier_offenders.append(kind + ": expected empty frontier_records")
                    if abs(degenerate_score) > BASELINE_ZERO_TOLERANCE:
                        offenders.append("%s scores %s, not zero" % (kind, degenerate_score))
            if offenders:
                _fail(rows, "degenerate_candidates_score_zero", "; ".join(offenders))
            else:
                _ok(rows, "degenerate_candidates_score_zero",
                    "blanket abstention earns nothing")

        if wave is not None:
            if frontier_offenders:
                _fail(rows, "frontier_degenerate_credit_zero", "; ".join(frontier_offenders))
            else:
                _ok(rows, "frontier_degenerate_credit_zero", "baseline and valid abstentions emit no records")

        crashes = []
        for kind, template in BAD_CANDIDATES.items():
            with tempfile.TemporaryDirectory(prefix="badcand_") as tmp:
                candidate = Path(tmp) / "candidate.py"
                candidate.write_text(template.format(entry=spec.entrypoint), encoding="utf-8")
                try:
                    metrics = evaluate_candidate(spec, candidate, timeout_s=timeout_s)
                except Exception as exc:  # noqa: BLE001
                    crashes.append("%s:%s" % (kind, exc))
                    continue
                if metrics.get("infrastructure_failure"):
                    crashes.append("%s:infrastructure_failure" % kind)
                elif float(metrics.get("valid", 0.0)) != 0.0:
                    crashes.append("%s:valid=%s" % (kind, metrics.get("valid")))
                else:
                    candidate_score = float(metrics.get("combined_score", INVALID_SCORE))
                    if candidate_score not in {0.0, float(INVALID_SCORE)}:
                        crashes.append("%s:invalid_score=%s" % (kind, candidate_score))
        if crashes:
            _fail(rows, "bad_candidates_score_zero", "; ".join(crashes))
        else:
            _ok(rows, "bad_candidates_score_zero", "raises/empty/wrong_type scored")

    probe = inspect_probe(spec, evaluate_candidate, timeout_s=timeout_s, skip_eval=skip_eval)
    rows.append({"check": "shortcut_probe", "ok": True if probe["passed"] else
                 False if probe["status"] == "failed" else None,
                 "status": probe["status"], "detail": probe.get("detail", "")})
    def phase(checks):
        if any(row["ok"] is False for row in checks):
            return "failed"
        if not checks or any(row["ok"] is not True for row in checks):
            return "incomplete"
        return "passed"
    phases = {"structural": phase(rows[:structural_count]),
              "runtime": phase(rows[structural_count:-1]),
              "shortcut_guard": phase(rows[-1:]),
              "difficulty": "unassessed"}
    execution_status = phase(rows)
    return {
        "schema_version": 2,
        "task": spec.task_id,
        "passed": execution_status == "passed",
        "status": execution_status,
        "phases": phases,
        "scientific_admission": "not_assessed",
        "note": "Passing declared probes does not establish model difficulty or iterative improvement.",
        "checks": rows,
        "shortcut_probe": probe,
        "baseline_combined_score": baseline.get("combined_score"),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", required=True)
    ap.add_argument("--output")
    ap.add_argument("--timeout", type=float, default=180.0)
    ap.add_argument(
        "--skip-eval", action="store_true",
        help="structural checks only; skip sandbox eval, determinism, and bad-candidate trials",
    )
    args = ap.parse_args()
    report = check_task(args.task, timeout_s=args.timeout, skip_eval=args.skip_eval)
    for row in report["checks"]:
        mark = "ok  " if row["ok"] is True else "FAIL" if row["ok"] is False else "SKIP"
        # A check that reports a structured detail should not take the whole gate down with a
        # TypeError before the verdict is printed; the JSON report keeps the structure either way.
        text = row["detail"] if isinstance(row["detail"], str) else json.dumps(
            row["detail"], ensure_ascii=False, sort_keys=True, default=str)
        detail = ("  " + text) if row["detail"] else ""
        print("%s  %-36s%s" % (mark, row["check"], detail))
    print()
    print(report["status"], report["task"], report["phases"])
    if args.output:
        Path(args.output).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return 0 if report["passed"] else 1 if report["status"] == "failed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
