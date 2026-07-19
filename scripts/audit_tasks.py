#!/usr/bin/env python3
"""Audit the task inventory against the certification policy."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from frontier_science.certification import certification_record, load_certification  # noqa: E402
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
        if rec["status"] == "certified":
            if not (spec.task_dir / "TASK_CARD.yaml").is_file():
                missing_files.append("TASK_CARD.yaml")
            if missing_files:
                issues.append("missing required files")
            if missing_metadata:
                issues.append("missing certification metadata")
            if not citation_ids:
                issues.append("no stable citation identifier")
            card_path = spec.task_dir / "TASK_CARD.yaml"
            if card_path.is_file():
                card = yaml.safe_load(card_path.read_text(encoding="utf-8")) or {}
                for key in ("scientific_question", "artifact", "oracle", "normalization",
                            "citations", "invariants", "known_shortcuts", "review"):
                    if not card.get(key):
                        issues.append("task card missing %s" % key)
        records.append({
            "task": spec.task_id, "status": rec["status"], "reason": rec["reason"],
            "missing_files": missing_files, "missing_metadata": missing_metadata,
            "citation_ids": citation_ids, "issues": issues,
        })
    orphaned = sorted(set(manifest["tasks"]) - ids)
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
        "orphaned_manifest_records": orphaned,
        "duplicate_oracle_groups": duplicates,
        "tasks": records,
        "passed": not orphaned and not any(r["issues"] for r in records),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = audit()
    text = json.dumps(report, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
