#!/usr/bin/env python3
"""Audit the task inventory against the certification policy."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from sle.certification import certification_record, load_certification  # noqa: E402
from sle.frontier import load_frozen_wave, validate_family_waves  # noqa: E402
from sle.provenance import finalize_report_trust, source_provenance  # noqa: E402
from sle.registry import list_tasks  # noqa: E402

REQUIRED_FILES = (
    "Task.md", "solution.py", "verification/evaluator.py", "frontier_eval/metadata.yaml",
    "frontier_eval/initial_program.txt", "frontier_eval/candidate_destination.txt",
    "frontier_eval/entrypoint.txt", "frontier_eval/constraints.txt",
)
REQUIRED_METADATA = (
    "domain", "task", "difficulty", "oracle_type", "score_mode", "gpu_required",
    "eval_time_seconds", "science_metric", "reference_baseline", "reference_sota", "citation",
)
TASK_CARD_REQUIRED_STATUSES = {"certified", "candidate"}
TASK_CARD_REQUIRED_KEYS = (
    "scientific_question", "artifact", "oracle", "normalization",
    "citations", "invariants", "known_shortcuts", "review",
    "provenance", "novelty_risk", "lineage", "construction_audit", "long_horizon",
)
PROVENANCE_CLASSES = {
    "known_answer", "procedural", "public_data_replay", "prospective",
}
NOVELTY_RISK_LEVELS = {"low", "medium", "high", "unknown"}
LINEAGE_STATUSES = {"complete", "incomplete_legacy", "unknown"}
METADATA_DIFFICULTIES = {
    "unmeasured", "hard", "flagship",
}
METADATA_TIERS = {"candidate", "T2", "T3"}
SCORE_MODES = {"clipped", "uncapped"}
# `run_eval.py` hands `EVAL_TIMEOUT_S` to `sle eval`; nothing on the evaluation path reads
# `eval_time_seconds`, so the two can disagree forever. They are reconciled here instead:
# the enforced timeout must cover the declared cost by at least the generator's own threefold
# margin, and must not exceed it by more than an order of magnitude beyond the widest legitimate
# margin in the inventory (75x, OccupancyDetectionDesign at 4 s under a 300 s wrapper). The
# ceiling is deliberately loose - it catches a declaration wrong by orders of magnitude without
# failing a merely conservative one. Tasks whose two values are already inconsistent when this
# check lands are named in `schemas/eval_timeout_migration.json` rather than silently waived.
EVAL_TIMEOUT_MIN = 3.0
EVAL_TIMEOUT_MAX = 100.0
# `review.domain` is the external-sign-off slot, and any nonempty string satisfied it: `'x'`
# passed. It is now an enumerated status. The 88 inherited cards wrote free-text variants of
# one of those values (`pending_external`, `pending_external_photovoltaics`), so a value that
# *starts* with a pending prefix is read as pending - never as sign-off. That keeps the inventory
# green without rewriting 88 task packages, and an unrecognised string now fails rather than
# counting as reviewed.
DOMAIN_REVIEW_PENDING_PREFIX = "pending"
DOMAIN_REVIEW_COMPLETE = "complete"
# Recorded, not waived: see the `policy` key in the file.
EVAL_TIMEOUT_MIGRATION = ROOT / "schemas" / "eval_timeout_migration.json"


def _nonempty_string(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _module_literal(path: Path, name: str):
    """The value a module binds to ``name`` at top level, without importing it.

    The timeout that actually stops an evaluation is a hand-committed constant in each task's
    wrapper, so the audit has to read it out of the source. `ast` rather than a regex because
    the wrappers carry comments about timeouts, and a substring scan matches those.
    """
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        return None
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(target, ast.Name) and target.id == name
                   for target in node.targets):
            continue
        try:
            return ast.literal_eval(node.value)
        except (ValueError, SyntaxError):
            return None
    return None


def _migration_inventory() -> dict:
    """The recorded tasks whose declared cost and enforced timeout already disagree."""
    try:
        document = json.loads(EVAL_TIMEOUT_MIGRATION.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    tasks = document.get("tasks")
    return tasks if isinstance(tasks, dict) else {}


def _timeout_issues(metadata: dict, run_eval: Path | None, task_id: str) -> list[str]:
    issues = []
    if "eval_time_seconds" not in metadata:
        # An absent key is `REQUIRED_METADATA`'s issue, not a second one for the same cause.
        return issues
    declared = metadata["eval_time_seconds"]
    if isinstance(declared, bool) or not isinstance(declared, (int, float)) or declared <= 0:
        return ["metadata eval_time_seconds is not a positive number"]
    if run_eval is None or not run_eval.is_file():
        return issues
    enforced = _module_literal(run_eval, "EVAL_TIMEOUT_S")
    if isinstance(enforced, bool) or not isinstance(enforced, (int, float)):
        return ["run_eval.py does not bind a literal EVAL_TIMEOUT_S"]
    entry = _migration_inventory().get(task_id)
    if entry is not None:
        # Pending means the disagreement is recorded, not that it was accepted. The entry pins
        # the pair it was written against: if either number moves, the entry is stale and the
        # ratio is checked again, so the inventory cannot outlive the numbers it excuses.
        if (entry.get("declared_eval_time_seconds") == declared
                and entry.get("enforced_timeout_s") == enforced):
            return issues
        issues.append("eval timeout migration entry is stale")
    ratio = enforced / declared
    if ratio < EVAL_TIMEOUT_MIN:
        issues.append(
            "run_eval.py timeout %g does not cover the declared %g s evaluation by %gx"
            % (enforced, declared, EVAL_TIMEOUT_MIN))
    elif ratio > EVAL_TIMEOUT_MAX:
        issues.append(
            "run_eval.py timeout %g exceeds the declared %g s evaluation by %gx"
            % (enforced, declared, EVAL_TIMEOUT_MAX))
    return issues


def _metadata_issues(metadata: dict, run_eval: Path | None = None,
                     task_id: str = "") -> list[str]:
    issues = []
    if metadata.get("difficulty") not in METADATA_DIFFICULTIES:
        issues.append("metadata difficulty is invalid")
    tier = metadata.get("tier")
    if tier is not None and tier not in METADATA_TIERS:
        issues.append("metadata tier is invalid")
    if metadata.get("score_mode") not in SCORE_MODES:
        issues.append("metadata score_mode is invalid")
    issues.extend(_timeout_issues(metadata, run_eval, task_id))
    return issues


def domain_review_state(review: dict) -> str:
    """Classify ``review.domain`` as ``pending``, ``complete`` or ``unknown``.

    Shared by the inventory audit (which fails closed on an unrecognised value) and the maturity
    audit (which counts sign-offs), so the two cannot disagree about whether a card is reviewed.
    ``complete`` additionally requires a reviewer and a date: a bare status is the uncheckable
    assertion the free-text field used to be, just spelled differently.
    """
    value = review.get("domain")
    status = value.strip() if isinstance(value, str) else ""
    if not status:
        return "unknown"
    if status.split("_", 1)[0] == DOMAIN_REVIEW_PENDING_PREFIX:
        return "pending"
    if status == DOMAIN_REVIEW_COMPLETE and all(
        _nonempty_string(review.get(key)) for key in ("reviewed_by", "reviewed_at")
    ):
        return "complete"
    return "unknown"


def _domain_review_issues(review: dict) -> list[str]:
    """`pending` must be distinguishable from `done by someone`, and `done` must be evidenced."""
    value = review.get("domain")
    if not isinstance(value, str) or not value.strip():
        return []
    if value.strip() == DOMAIN_REVIEW_COMPLETE:
        # `reviewed_by`/`reviewed_at` are new keys, so the 88 inherited cards - all pending -
        # keep validating.
        return ["task card review domain is complete without %s" % key
                for key in ("reviewed_by", "reviewed_at")
                if not _nonempty_string(review.get(key))]
    if domain_review_state(review) == "pending":
        return []
    return ["task card review domain is not a %s status or %s"
            % (DOMAIN_REVIEW_PENDING_PREFIX, DOMAIN_REVIEW_COMPLETE)]


def _task_card_issues(path: Path) -> list[str]:
    """Return fail-closed schema issues without aborting the inventory audit."""
    if not path.is_file():
        return ["missing task card"]
    try:
        card = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        return ["task card is not valid YAML: %s" % type(exc).__name__]
    if not isinstance(card, dict):
        return ["task card root is not a mapping"]

    issues = []
    if card.get("schema_version") != 2:
        issues.append("task card schema_version is not 2")
    for key in TASK_CARD_REQUIRED_KEYS:
        if not card.get(key):
            issues.append("task card missing %s" % key)

    for key in ("scientific_question", "artifact", "known_shortcuts"):
        if key in card and not _nonempty_string(card.get(key)):
            issues.append("task card %s is not a nonempty string" % key)

    oracle = card.get("oracle")
    if isinstance(oracle, dict):
        if oracle.get("deterministic") is not True:
            issues.append("task card oracle is not explicitly deterministic")
        if not _nonempty_string(oracle.get("feasibility")):
            issues.append("task card oracle lacks feasibility semantics")
        if not any(_nonempty_string(oracle.get(key)) for key in ("model", "nominal", "exact")):
            issues.append("task card oracle lacks model semantics")
    elif oracle is not None:
        issues.append("task card oracle is not a mapping")

    normalization = card.get("normalization")
    if isinstance(normalization, dict):
        for key in ("baseline", "reference", "score"):
            if not _nonempty_string(normalization.get(key)):
                issues.append("task card normalization lacks %s" % key)
    elif normalization is not None:
        issues.append("task card normalization is not a mapping")

    citations = card.get("citations")
    if isinstance(citations, list):
        for index, citation in enumerate(citations):
            if not isinstance(citation, dict):
                issues.append("task card citation %d is not a mapping" % index)
                continue
            identifier = citation.get("id")
            if not _nonempty_string(identifier) or ":" not in identifier:
                issues.append("task card citation %d lacks a stable identifier" % index)
            if not _nonempty_string(citation.get("title")):
                issues.append("task card citation %d lacks a title" % index)
    elif citations is not None:
        issues.append("task card citations is not a list")

    invariants = card.get("invariants")
    if isinstance(invariants, list):
        if any(not _nonempty_string(value) for value in invariants):
            issues.append("task card invariants contain a non-string or empty value")
    elif invariants is not None:
        issues.append("task card invariants is not a list")

    review = card.get("review")
    if isinstance(review, dict):
        for key in ("domain", "evaluator_security"):
            if not _nonempty_string(review.get(key)):
                issues.append("task card review lacks %s" % key)
        issues.extend(_domain_review_issues(review))
    elif review is not None:
        issues.append("task card review is not a mapping")

    provenance = card.get("provenance")
    if isinstance(provenance, dict):
        if provenance.get("class") not in PROVENANCE_CLASSES:
            issues.append("task card provenance class is invalid")
        if not _nonempty_string(provenance.get("target_source")):
            issues.append("task card provenance lacks target_source")
        if not isinstance(provenance.get("task_contract_public_before_evaluation"), bool):
            issues.append("task card provenance lacks public-before-evaluation boolean")
        if not _nonempty_string(provenance.get("fresh_confirmation_status")):
            issues.append("task card provenance lacks fresh_confirmation_status")
    elif provenance is not None:
        issues.append("task card provenance is not a mapping")

    novelty_risk = card.get("novelty_risk")
    if isinstance(novelty_risk, dict):
        if novelty_risk.get("level") not in NOVELTY_RISK_LEVELS:
            issues.append("task card novelty_risk level is invalid")
        if not _nonempty_string(novelty_risk.get("rationale")):
            issues.append("task card novelty_risk lacks rationale")
    elif novelty_risk is not None:
        issues.append("task card novelty_risk is not a mapping")

    lineage = card.get("lineage")
    if isinstance(lineage, dict):
        if lineage.get("status") not in LINEAGE_STATUSES:
            issues.append("task card lineage status is invalid")
        for key in ("builder_model_ids", "builder_scaffolds", "calibrator_model_ids"):
            values = lineage.get(key)
            if not isinstance(values, list) or any(not _nonempty_string(value) for value in values):
                issues.append("task card lineage %s is not a string list" % key)
        runs = lineage.get("calibration_runs")
        if isinstance(runs, list):
            for run in runs:
                if not _nonempty_string(run):
                    issues.append("task card calibration run is not a nonempty string")
                    continue
                relative = Path(run)
                if relative.is_absolute() or ".." in relative.parts or not run.startswith("experiments/"):
                    issues.append("task card calibration run is not a safe experiment path")
                elif not (ROOT / relative).is_file():
                    issues.append("task card calibration run does not exist")
        else:
            issues.append("task card lineage calibration_runs is not a list")
        if lineage.get("calibration_evidence_status") not in {
            "current_or_migration_replayed", "historical_only", "missing",
        }:
            issues.append("task card calibration_evidence_status is invalid")
        for key in ("edits_triggered_by_model", "shortcut_discoverer"):
            if not _nonempty_string(lineage.get(key)):
                issues.append("task card lineage lacks %s" % key)
        if not isinstance(lineage.get("frozen_before_eval"), bool):
            issues.append("task card lineage frozen_before_eval is not boolean")
        if "freeze_timestamp" not in lineage:
            issues.append("task card lineage lacks freeze_timestamp")
        elif lineage.get("frozen_before_eval") is True and not _nonempty_string(
            lineage.get("freeze_timestamp")
        ):
            issues.append("task card frozen lineage lacks freeze_timestamp value")
    elif lineage is not None:
        issues.append("task card lineage is not a mapping")

    construction = card.get("construction_audit")
    if isinstance(construction, dict):
        for key in (
            "status", "author_domain", "reviewer_domain",
            "oracle_disagreement_status", "independent_recomputation_status",
        ):
            if not _nonempty_string(construction.get(key)):
                issues.append("task card construction_audit lacks %s" % key)
        for key in ("expert_hours", "red_team_rounds"):
            value = construction.get(key)
            if value is not None and (
                isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0
            ):
                issues.append("task card construction_audit %s is invalid" % key)
    elif construction is not None:
        issues.append("task card construction_audit is not a mapping")

    long_horizon = card.get("long_horizon")
    if isinstance(long_horizon, dict):
        if not _nonempty_string(long_horizon.get("status")):
            issues.append("task card long_horizon lacks status")
        for key in ("measurement_health_passed", "material_headroom_after_2h"):
            if not isinstance(long_horizon.get(key), bool):
                issues.append("task card long_horizon %s is not boolean" % key)
        long_evidence = long_horizon.get("evidence")
        if not isinstance(long_evidence, list) or any(
            not _nonempty_string(value) for value in long_evidence
        ):
            issues.append("task card long_horizon evidence is not a string list")
        elif (
            long_horizon.get("measurement_health_passed") is True
            or long_horizon.get("material_headroom_after_2h") is True
        ) and not long_evidence:
            issues.append("task card long_horizon passed gate lacks evidence")
    elif long_horizon is not None:
        issues.append("task card long_horizon is not a mapping")
    return issues


def _normalized_oracle(path: Path) -> str:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    if (tree.body and isinstance(tree.body[0], ast.Expr)
            and isinstance(tree.body[0].value, ast.Constant)
            and isinstance(tree.body[0].value.value, str)):
        tree.body.pop(0)
    entrypoint_names = {
        node.args.args[0].arg for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "evaluate" and node.args.args
    }
    class Normalize(ast.NodeTransformer):
        def visit_arg(self, node):
            if node.arg in entrypoint_names:
                node.arg = "candidate"
            return node

        def visit_Name(self, node):
            if node.id in entrypoint_names:
                node.id = "candidate"
            return node
    tree = Normalize().visit(tree)
    return ast.dump(tree, annotate_fields=False, include_attributes=False)


def audit() -> dict:
    manifest = load_certification()
    specs = list_tasks(None)
    ids = {s.task_id for s in specs}
    records = []
    for spec in specs:
        rec = certification_record(spec.task_id)
        missing_files = [p for p in REQUIRED_FILES if not (spec.task_dir / p).is_file()]
        missing_metadata = [k for k in REQUIRED_METADATA if k not in spec.metadata]
        citation_ids = rec.get("citation_ids", [])
        issues = _metadata_issues(
            spec.metadata, spec.task_dir / "frontier_eval" / "run_eval.py", spec.task_id)
        try:
            wave = load_frozen_wave(spec)
        except ValueError as exc:
            wave = None
            issues.append("invalid frontier wave: %s" % exc)
        if rec["status"] in TASK_CARD_REQUIRED_STATUSES:
            card_path = spec.task_dir / "TASK_CARD.yaml"
            if not card_path.is_file():
                missing_files.append("TASK_CARD.yaml")
            if missing_files:
                issues.append("missing required files")
            if missing_metadata:
                issues.append("missing certification metadata")
            if not citation_ids:
                issues.append("no stable citation identifier")
            elif any(not isinstance(value, str) or ":" not in value for value in citation_ids):
                issues.append("unstable citation identifier")
            issues.extend(_task_card_issues(card_path))
        records.append({
            "task": spec.task_id, "status": rec["status"], "reason": rec["reason"],
            "missing_files": missing_files, "missing_metadata": missing_metadata,
            "citation_ids": citation_ids, "issues": issues,
            "task_family_id": wave.task_family_id if wave else spec.task_id,
            "wave_id": wave.wave_id if wave else None,
            "wave_manifest_sha256": wave.manifest_sha256 if wave else None,
        })
    orphaned = sorted(set(manifest["tasks"]) - ids)
    missing_manifest = sorted(ids - set(manifest["tasks"]))
    duplicate_groups = {}
    for spec in specs:
        digest = hashlib.sha256(_normalized_oracle(spec.task_dir / "verification/evaluator.py").encode()).hexdigest()
        duplicate_groups.setdefault(digest, []).append(spec.task_id)
    duplicates = [v for v in duplicate_groups.values() if len(v) > 1]
    family_issues = validate_family_waves(specs)
    return {
        "schema_version": 1,
        "trust_status": "TRUSTED_CERTIFICATION_AUDIT",
        "inventory_count": len(specs),
        "status_counts": {s: sum(r["status"] == s for r in records)
                          for s in ("certified", "candidate", "quarantined")},
        "missing_manifest_records": missing_manifest,
        "orphaned_manifest_records": orphaned,
        "duplicate_oracle_groups": duplicates,
        "frontier_family_issues": family_issues,
        "task_card_required_count": sum(
            record["status"] in TASK_CARD_REQUIRED_STATUSES for record in records
        ),
        "task_card_passed_count": sum(
            record["status"] in TASK_CARD_REQUIRED_STATUSES
            and not any("task card" in issue for issue in record["issues"])
            for record in records
        ),
        "tasks": records,
        "passed": (
            not missing_manifest
            and not orphaned
            and not family_issues
            and not any(r["issues"] for r in records)
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = audit()
    execution_passed = bool(report.pop("passed"))
    report.update({
        "created_at": datetime.now(timezone.utc).isoformat(),
        "environment": {"python": sys.version, "platform": platform.platform()},
        "source_provenance": source_provenance(ROOT),
    })
    finalize_report_trust(report, execution_passed)
    text = json.dumps(report, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0 if execution_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
