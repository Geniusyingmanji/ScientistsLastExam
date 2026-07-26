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

from frontier_science.certification import certification_record, load_certification  # noqa: E402
from frontier_science.provenance import finalize_report_trust, source_provenance  # noqa: E402
from frontier_science.registry import list_tasks  # noqa: E402

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
)


def _nonempty_string(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


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
    if card.get("schema_version") != 1:
        issues.append("task card schema_version is not 1")
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
    elif review is not None:
        issues.append("task card review is not a mapping")
    return issues


def _normalized_oracle(path: Path) -> str:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    if tree.body and isinstance(tree.body[0], ast.Expr) and isinstance(tree.body[0].value, ast.Str):
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
        issues = []
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
        })
    orphaned = sorted(set(manifest["tasks"]) - ids)
    missing_manifest = sorted(ids - set(manifest["tasks"]))
    duplicate_groups = {}
    for spec in specs:
        digest = hashlib.sha256(_normalized_oracle(spec.task_dir / "verification/evaluator.py").encode()).hexdigest()
        duplicate_groups.setdefault(digest, []).append(spec.task_id)
    duplicates = [v for v in duplicate_groups.values() if len(v) > 1]
    return {
        "schema_version": 1,
        "trust_status": "TRUSTED_CERTIFICATION_AUDIT",
        "inventory_count": len(specs),
        "status_counts": {s: sum(r["status"] == s for r in records)
                          for s in ("certified", "candidate", "quarantined")},
        "missing_manifest_records": missing_manifest,
        "orphaned_manifest_records": orphaned,
        "duplicate_oracle_groups": duplicates,
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
