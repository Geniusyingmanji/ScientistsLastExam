#!/usr/bin/env python3
"""Audit compatibility of trusted-context support with historical runs.

The audit binds the exact three shared runtime files, proves that a call with
``trusted_context=None`` still selects ``evaluate`` with one candidate argument,
and replays retained artifacts from the affected calibration analyzers.  It
fails on every structural/categorical change and permits only bounded numeric
roundoff from the later single-thread BLAS environment.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import importlib.util
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from frontier_science.evaluate import evaluate_candidate  # noqa: E402
from frontier_science.provenance import (  # noqa: E402
    finalize_report_trust,
    source_provenance,
)
from frontier_science.registry import find_task  # noqa: E402
from frontier_science.runtime_migration import (  # noqa: E402
    AUDITED_RUNTIME_SHA256,
    BASE_RUNTIME_REVISION,
    BASE_RUNTIME_SHA256,
    RUNTIME_PATHS,
    compare_json_values,
)


NUMERIC_TOLERANCE = 5.0e-10
ANALYZERS = (
    "scripts/analyze_alloy_hardness_calibrations.py",
    "scripts/analyze_calorimeter_v2_calibrations.py",
    "scripts/analyze_demographic_sfs_v2_calibrations.py",
    "scripts/analyze_diffraction_grating_calibrations.py",
    "scripts/analyze_electrolyte_conductivity_design_calibrations.py",
    "scripts/analyze_force_field_hypothesis_calibrations.py",
    "scripts/analyze_protein_stability_design_calibrations.py",
)
# One baseline and one non-baseline source per affected task exercise both a
# valid legacy path and the task's observed proposal/failure behavior without
# redundantly evaluating duplicate selected/terminal files from every condition.
REPLAY_CASES = (
    ("scripts/analyze_alloy_hardness_calibrations.py", "budget_one", "selected_best"),
    ("scripts/analyze_alloy_hardness_calibrations.py", "normal_budget_three", "selected_best"),
    ("scripts/analyze_calorimeter_v2_calibrations.py", "budget_one", "selected_best"),
    ("scripts/analyze_calorimeter_v2_calibrations.py", "budget_one", "terminal"),
    ("scripts/analyze_demographic_sfs_v2_calibrations.py", "budget_one", "selected_best"),
    ("scripts/analyze_demographic_sfs_v2_calibrations.py", "normal_budget_three", "selected_best"),
    ("scripts/analyze_diffraction_grating_calibrations.py", "budget_one", "selected_best"),
    ("scripts/analyze_diffraction_grating_calibrations.py", "budget_one", "terminal"),
    ("scripts/analyze_electrolyte_conductivity_design_calibrations.py", "budget_one", "selected_best"),
    ("scripts/analyze_electrolyte_conductivity_design_calibrations.py", "normal_budget_three", "selected_best"),
    ("scripts/analyze_force_field_hypothesis_calibrations.py", "budget_one", "selected_best"),
    ("scripts/analyze_force_field_hypothesis_calibrations.py", "budget_one", "terminal"),
    ("scripts/analyze_protein_stability_design_calibrations.py", "budget_one", "selected_best"),
    ("scripts/analyze_protein_stability_design_calibrations.py", "normal_budget_three", "selected_best"),
)
FAILURE_TAXONOMY_KEYS = (
    "valid", "candidate_failure_kind", "infrastructure_failure", "timeout",
    "error_message",
)


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _git_show(revision: str, relative: str) -> bytes:
    return subprocess.check_output(
        ["git", "show", revision + ":" + relative], cwd=str(ROOT),
    )


def _load_script(relative: str):
    path = ROOT / relative
    name = "runtime_migration_" + path.stem
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError("cannot load %s" % relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def audit_source_contract(audited_revision: str) -> dict[str, Any]:
    changes = subprocess.check_output(
        [
            "git", "diff", "--name-only", BASE_RUNTIME_REVISION,
            audited_revision, "--", *RUNTIME_PATHS,
        ],
        cwd=str(ROOT), text=True,
    ).splitlines()
    base_hashes = {
        relative: _sha256_bytes(_git_show(BASE_RUNTIME_REVISION, relative))
        for relative in RUNTIME_PATHS
    }
    current_hashes = {
        relative: _sha256(ROOT / relative) for relative in RUNTIME_PATHS
    }
    return {
        "base_revision": BASE_RUNTIME_REVISION,
        "audited_revision": audited_revision,
        "runtime_paths": list(RUNTIME_PATHS),
        "runtime_source_changes": changes,
        "base_runtime_sha256": base_hashes,
        "audited_runtime_sha256": current_hashes,
        "passed": bool(
            changes == list(RUNTIME_PATHS)
            and base_hashes == BASE_RUNTIME_SHA256
            and current_hashes == AUDITED_RUNTIME_SHA256
        ),
    }


def _function(tree: ast.Module, name: str) -> ast.FunctionDef:
    matches = [
        node for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == name
    ]
    if len(matches) != 1 or not isinstance(matches[0], ast.FunctionDef):
        raise ValueError("expected one function %s" % name)
    return matches[0]


def audit_legacy_path_semantics() -> dict[str, Any]:
    secure_path = ROOT / "frontier_science/secure_eval.py"
    evaluate_path = ROOT / "frontier_science/evaluate.py"
    secure_text = secure_path.read_text(encoding="utf-8")
    evaluate_text = evaluate_path.read_text(encoding="utf-8")
    secure_tree = ast.parse(secure_text)
    evaluate_tree = ast.parse(evaluate_text)
    secure_function = _function(secure_tree, "trusted_evaluate")
    outer_function = _function(evaluate_tree, "evaluate_candidate")
    secure_source = ast.get_source_segment(secure_text, secure_function) or ""
    outer_source = ast.get_source_segment(evaluate_text, outer_function) or ""
    compact_secure = "".join(secure_source.split())
    legacy_oracle = (
        "with_trusted_context=trusted_context is not None" in secure_source
        and "iftrusted_contextisnotNoneelseoracle(proxy)" in compact_secure
    )
    context_optional = (
        "trusted_context:dict[str,Any]|None=None" in compact_secure
    )
    no_context_mount = (
        "if context_payload is not None:" in outer_source
        and "--trusted-context" in outer_source
    )
    candidate_sandbox_hash_unchanged = bool(
        _sha256_bytes(_git_show(BASE_RUNTIME_REVISION, "frontier_science/candidate_worker.py"))
        == _sha256(ROOT / "frontier_science/candidate_worker.py")
        and _sha256_bytes(_git_show(BASE_RUNTIME_REVISION, "frontier_science/rpc_codec.py"))
        == _sha256(ROOT / "frontier_science/rpc_codec.py")
    )
    passed = bool(
        legacy_oracle and context_optional and no_context_mount
        and candidate_sandbox_hash_unchanged
    )
    return {
        "trusted_context_none_uses_legacy_oracle": legacy_oracle,
        "trusted_context_none_adds_no_context_argument": context_optional,
        "trusted_context_file_is_conditional": no_context_mount,
        "candidate_sandbox_contract_unchanged": candidate_sandbox_hash_unchanged,
        "passed": passed,
    }


def _raw_expected(module: Any, record: dict[str, Any]) -> dict[str, dict[str, Any]]:
    workdir = (ROOT / record["best_program"]).parent
    raw_events = module.load_trajectory(workdir / "trajectory.jsonl")
    return {
        str(event["candidate_sha256"]): dict(event.get("metrics") or {})
        for event in raw_events
    }


def _failure_taxonomy(metrics: dict[str, Any]) -> dict[str, Any]:
    return {key: metrics.get(key) for key in FAILURE_TAXONOMY_KEYS}


def audit_retained_artifacts() -> dict[str, Any]:
    records = []
    unique: dict[tuple[str, str], dict[str, Any]] = {}
    modules: dict[str, Any] = {}
    loaded_records: dict[tuple[str, str], dict[str, Any]] = {}
    for analyzer, label, artifact in REPLAY_CASES:
        if analyzer not in modules:
            modules[analyzer] = _load_script(analyzer)
        module = modules[analyzer]
        relative = module.REPORTS[label]
        record_key = (analyzer, label)
        if record_key not in loaded_records:
            if "oracle" in module._load_model.__code__.co_varnames:
                oracle = module._load_module(
                    ROOT / (
                        "benchmarks/Physics/CalorimeterDesign/"
                        "verification/evaluator.py"
                    ),
                    "runtime_migration_calorimeter_oracle",
                )
                record = module._load_model(label, relative, oracle)
            elif "replay_retained_sources" in module._load_model.__code__.co_varnames:
                record = module._load_model(
                    label, relative, replay_retained_sources=False,
                )
            else:
                record = module._load_model(label, relative)
            loaded_records[record_key] = record
        record = loaded_records[record_key]
        expected = _raw_expected(module, record)
        task_id = str(module.TASK)
        spec = find_task(task_id, include_uncertified=True)
        key = "best_program" if artifact == "selected_best" else "terminal_program"
        path = ROOT / record[key]
        source_hash = _sha256(path)
        cache_key = (task_id, source_hash)
        if cache_key not in unique:
            historical = expected[source_hash]
            current = evaluate_candidate(spec, path, timeout_s=180)
            comparison = compare_json_values(
                historical, current,
                numeric_tolerance=NUMERIC_TOLERANCE,
            )
            taxonomy_changed = (
                _failure_taxonomy(historical)
                != _failure_taxonomy(current)
            )
            unique[cache_key] = {
                "task": task_id,
                "source_sha256": source_hash,
                "historical_metrics_sha256": _sha256_bytes(json.dumps(
                    historical, sort_keys=True, separators=(",", ":"),
                    allow_nan=False,
                ).encode("utf-8")),
                "current_metrics_sha256": _sha256_bytes(json.dumps(
                    current, sort_keys=True, separators=(",", ":"),
                    allow_nan=False,
                ).encode("utf-8")),
                "failure_taxonomy_changed": taxonomy_changed,
                "comparison": comparison,
            }
        records.append({
            "analyzer": analyzer,
            "condition": label,
            "artifact": artifact,
            "path": str(path.relative_to(ROOT)),
            **unique[cache_key],
        })

    numeric_count = sum(
        row["comparison"]["numeric_difference_count"] for row in unique.values()
    )
    non_numeric_count = sum(
        row["comparison"]["non_numeric_difference_count"] for row in unique.values()
    )
    maximum = max(
        (row["comparison"]["maximum_absolute_numeric_difference"]
         for row in unique.values()),
        default=0.0,
    )
    taxonomy_changes = sum(
        bool(row["failure_taxonomy_changed"]) for row in unique.values()
    )
    result = {
        "analyzer_count": len(ANALYZERS),
        "artifact_instance_count": len(records),
        "artifact_count": len(unique),
        "numeric_difference_count": numeric_count,
        "non_numeric_difference_count": non_numeric_count,
        "maximum_absolute_numeric_difference": maximum,
        "failure_taxonomy_change_count": taxonomy_changes,
        "artifact_instances": records,
    }
    result["passed"] = bool(
        result["analyzer_count"] == len(ANALYZERS)
        and result["artifact_instance_count"] == len(REPLAY_CASES)
        and result["artifact_count"] > 0
        and non_numeric_count == 0
        and taxonomy_changes == 0
        and maximum <= NUMERIC_TOLERANCE
        and all(row["comparison"]["equivalent"] for row in unique.values())
    )
    return result


def audit() -> dict[str, Any]:
    provenance = source_provenance(ROOT)
    revision = str(provenance.get("git_revision"))
    source = audit_source_contract(revision)
    semantics = audit_legacy_path_semantics()
    replay = audit_retained_artifacts()
    execution_passed = bool(
        source["passed"] and semantics["passed"] and replay["passed"]
    )
    report = {
        "schema_version": 1,
        "trust_status": "TRUSTED_RUNTIME_MIGRATION_AUDIT",
        "evidence_scope": (
            "TRUSTED_CONTEXT_ADDITIVE_RUNTIME_MIGRATION_LEGACY_NONE_PATH_"
            "RETAINED_ARTIFACT_REPLAY_NUMERIC_TOLERANCE_NOT_FUTURE_RUNTIME_"
            "OR_UNRETAINED_SOURCE_EQUIVALENCE"
        ),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_provenance": provenance,
        "environment": {"python": sys.version, "platform": platform.platform()},
        "numeric_tolerance": NUMERIC_TOLERANCE,
        "source_contract": source,
        "legacy_path_semantics": semantics,
        "retained_artifact_replay": replay,
        "limitations": [
            "Only retained selected-best and terminal artifacts are replayed; unretained intermediate proposal source cannot be re-executed.",
            "The tolerance accepts bounded floating-point roundoff only; structure, strings, booleans, keys, lengths and failure taxonomy must remain exact.",
            "This audit covers the exact hash-bound runtime migration and does not authorize later runtime or task-evaluator edits.",
        ],
    }
    finalize_report_trust(report, execution_passed)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = audit()
    rendered = json.dumps(report, indent=2, allow_nan=False) + "\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered, encoding="utf-8")
    print(json.dumps({
        "execution_passed": report["execution_passed"],
        "trusted_evidence": report["trusted_evidence"],
        "artifact_count": report["retained_artifact_replay"]["artifact_count"],
        "maximum_absolute_numeric_difference": report[
            "retained_artifact_replay"
        ]["maximum_absolute_numeric_difference"],
    }, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
