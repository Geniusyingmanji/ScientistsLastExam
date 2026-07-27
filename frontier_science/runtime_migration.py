"""Strict compatibility gate for the sealed-context runtime migration.

Historical calibration reports predate trusted confirmation contexts.  The
context support is intentionally additive: calls with ``trusted_context=None``
must keep using the historical oracle entry point and candidate sandbox.  This
module does not declare that compatibility from source names alone.  It binds
the exact old/current runtime blobs and a clean, replay-based migration audit.
"""

from __future__ import annotations

import hashlib
import json
import math
import subprocess
from pathlib import Path, PurePosixPath
from typing import Any, Sequence


REPO_ROOT = Path(__file__).resolve().parent.parent
BASE_RUNTIME_REVISION = "20c6b780828c1ec53ddafbbde8fbf4579ff7801a"
MIGRATION_REPORT = (
    "experiments/trusted_context_runtime_migration_audit_2026-07-26_v1.json"
)
MIGRATION_REPORT_SHA256 = (
    "fe21a9be7d3a64dadf4e4f0bbc68b9157eb529e9a47e6b97faa751ffd9ee9673"
)
RUNTIME_PATHS = (
    "frontier_science/evaluate.py",
    "frontier_science/secure_eval.py",
    "frontier_science/trusted_driver.py",
)
BASE_RUNTIME_SHA256 = {
    "frontier_science/evaluate.py": (
        "388a596a7e3b774116480657e0a2c9d423e03cecfd7704a65d78a47bddb8a39f"
    ),
    "frontier_science/secure_eval.py": (
        "af898b0102a826ab9fc8d36dd2455d2680d68db646f31996dbcf02e3dd43edaf"
    ),
    "frontier_science/trusted_driver.py": (
        "e6d630c0a0638138fb214a3a5b00d0f4cf718129edee6610f955ff0d3dda12b4"
    ),
}
AUDITED_RUNTIME_SHA256 = {
    "frontier_science/evaluate.py": (
        "ba30ec09573fd63ab9b3d02b940bc7718146f866363f4c7a44d39f0dc80dfe8d"
    ),
    "frontier_science/secure_eval.py": (
        "8f65b9459c22a508cdfdcbdedc940339d7b78c2adff10448d74c5cbfa41a98d7"
    ),
    "frontier_science/trusted_driver.py": (
        "79800395d619b11b751b512552a184bc19584e4a889c825bd5d6086fa77f1a83"
    ),
}


def compare_json_values(
    historical: Any,
    current: Any,
    *,
    numeric_tolerance: float,
) -> dict[str, Any]:
    """Compare JSON values without hiding structural or categorical changes.

    Booleans, strings, nulls, container shapes and keys must match exactly.
    Finite int/float leaves may differ only within ``numeric_tolerance``.  The
    returned paths make every accepted floating-point change auditable.
    """

    numeric_differences: list[dict[str, Any]] = []
    non_numeric_differences: list[dict[str, Any]] = []

    def walk(left: Any, right: Any, path: str) -> None:
        if isinstance(left, dict) and isinstance(right, dict):
            left_keys = set(left)
            right_keys = set(right)
            if left_keys != right_keys:
                non_numeric_differences.append({
                    "path": path or "/",
                    "kind": "mapping_keys",
                    "historical": sorted(str(key) for key in left_keys),
                    "current": sorted(str(key) for key in right_keys),
                })
            for key in sorted(left_keys & right_keys, key=str):
                walk(left[key], right[key], path + "/" + str(key))
            return
        if isinstance(left, list) and isinstance(right, list):
            if len(left) != len(right):
                non_numeric_differences.append({
                    "path": path or "/",
                    "kind": "list_length",
                    "historical": len(left),
                    "current": len(right),
                })
            for index, (old_value, new_value) in enumerate(zip(left, right)):
                walk(old_value, new_value, path + "/" + str(index))
            return
        numeric_left = (
            isinstance(left, (int, float)) and not isinstance(left, bool)
        )
        numeric_right = (
            isinstance(right, (int, float)) and not isinstance(right, bool)
        )
        if numeric_left and numeric_right:
            if not (math.isfinite(float(left)) and math.isfinite(float(right))):
                non_numeric_differences.append({
                    "path": path or "/",
                    "kind": "non_finite_numeric",
                    "historical": repr(left),
                    "current": repr(right),
                })
                return
            difference = abs(float(left) - float(right))
            if difference != 0.0:
                numeric_differences.append({
                    "path": path or "/",
                    "historical": float(left),
                    "current": float(right),
                    "absolute_difference": difference,
                })
            return
        if type(left) is not type(right) or left != right:
            non_numeric_differences.append({
                "path": path or "/",
                "kind": "value_or_type",
                "historical": left,
                "current": right,
            })

    walk(historical, current, "")
    maximum = max(
        (row["absolute_difference"] for row in numeric_differences),
        default=0.0,
    )
    return {
        "equivalent": bool(
            not non_numeric_differences and maximum <= numeric_tolerance
        ),
        "exactly_equal": historical == current,
        "numeric_tolerance": float(numeric_tolerance),
        "numeric_difference_count": len(numeric_differences),
        "non_numeric_difference_count": len(non_numeric_differences),
        "maximum_absolute_numeric_difference": maximum,
        "numeric_differences": numeric_differences,
        "non_numeric_differences": non_numeric_differences,
    }


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _is_ancestor(left: str, right: str, root: Path = REPO_ROOT) -> bool:
    return subprocess.run(
        ["git", "merge-base", "--is-ancestor", left, right],
        cwd=str(root), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        check=False,
    ).returncode == 0


def filter_runtime_source_changes(changes: Sequence[str]) -> list[str]:
    """Remove task-card metadata, while retaining every executable input.

    ``TASK_CARD.yaml`` documents a benchmark for reviewers but is not loaded by
    the candidate, task specification, evaluator, or trusted runtime.  Older
    analysis scripts scoped ``git diff`` to the whole task directory, so adding
    these cards incorrectly looked like a runtime migration.  Keep the
    exception deliberately exact: only ``benchmarks/<domain>/<task>/`` task
    cards are metadata.  A same-named file anywhere else remains runtime-visible.
    """

    retained: list[str] = []
    for value in changes:
        relative = str(value).strip()
        if not relative:
            continue
        parts = PurePosixPath(relative).parts
        is_task_card = bool(
            len(parts) == 4
            and parts[0] == "benchmarks"
            and parts[-1] == "TASK_CARD.yaml"
        )
        if not is_task_card:
            retained.append(relative)
    return retained


def runtime_source_changes(
    left: str,
    right: str,
    scope: Sequence[str],
    *,
    root: Path = REPO_ROOT,
) -> list[str]:
    """Return runtime-relevant paths changed between two revisions."""

    output = subprocess.check_output(
        ["git", "diff", "--name-only", left, right, "--", *scope],
        cwd=str(root),
        text=True,
        stderr=subprocess.DEVNULL,
    )
    return filter_runtime_source_changes(output.splitlines())


def runtime_migration_status(
    input_revision: str,
    current_revision: str,
    runtime_changes: Sequence[str],
    *,
    additional_allowed_changes: Sequence[str] = (),
    additional_checks: dict[str, bool] | None = None,
    root: Path = REPO_ROOT,
) -> dict[str, Any]:
    """Return a fail-closed, hash-bound compatibility decision.

    ``additional_allowed_changes`` is for a separately audited task migration
    (for example a confirmation-only evaluator entry point).  Callers must also
    supply explicit ``additional_checks``; merely naming another path cannot
    make it equivalent.
    """

    root = Path(root).resolve()
    report_path = root / MIGRATION_REPORT
    expected_changes = sorted(set(RUNTIME_PATHS) | set(additional_allowed_changes))
    observed_changes = sorted(set(str(value) for value in runtime_changes))
    status: dict[str, Any] = {
        "required": bool(observed_changes),
        "report": MIGRATION_REPORT,
        "expected_report_sha256": MIGRATION_REPORT_SHA256,
        "report_sha256": _sha256(report_path) if report_path.is_file() else None,
        "base_runtime_revision": BASE_RUNTIME_REVISION,
        "audited_runtime_revision": None,
        "input_revision": input_revision,
        "current_revision": current_revision,
        "runtime_source_changes": observed_changes,
        "expected_runtime_source_changes": expected_changes,
        "current_runtime_sha256": {
            relative: _sha256(root / relative)
            for relative in RUNTIME_PATHS if (root / relative).is_file()
        },
        "additional_allowed_changes": sorted(set(additional_allowed_changes)),
        "additional_checks": dict(additional_checks or {}),
        "accepted": False,
    }
    if not observed_changes:
        status["accepted"] = True
        status["checks"] = {"no_migration_required": True}
        return status
    if not report_path.is_file():
        status["failure_reason"] = "migration_report_missing"
        return status
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        status["failure_reason"] = "migration_report_invalid_json"
        return status

    provenance = report.get("source_provenance") or {}
    audited_revision = str(provenance.get("git_revision") or "")
    status["audited_runtime_revision"] = audited_revision or None
    source = report.get("source_contract") or {}
    replay = report.get("retained_artifact_replay") or {}
    semantics = report.get("legacy_path_semantics") or {}
    checks = {
        "report_hash_matches": status["report_sha256"] == MIGRATION_REPORT_SHA256,
        "report_passed_clean": bool(
            report.get("schema_version") == 1
            and report.get("execution_passed") is True
            and report.get("passed") is True
            and report.get("trusted_evidence") is True
            and report.get("trust_decision") == "trusted_clean_revision"
            and audited_revision not in {"", "unknown"}
            and provenance.get("source_tree_dirty") is False
            and provenance.get("source_changes") == []
        ),
        "input_predates_or_equals_base": bool(
            input_revision
            and _is_ancestor(input_revision, BASE_RUNTIME_REVISION, root)
        ),
        "audited_revision_is_ancestor": _is_ancestor(
            audited_revision, current_revision, root,
        ),
        "runtime_change_scope_matches": observed_changes == expected_changes,
        "source_contract_matches": bool(
            source.get("base_revision") == BASE_RUNTIME_REVISION
            and source.get("audited_revision") == audited_revision
            and source.get("runtime_paths") == list(RUNTIME_PATHS)
            and source.get("base_runtime_sha256") == BASE_RUNTIME_SHA256
            and source.get("audited_runtime_sha256") == AUDITED_RUNTIME_SHA256
            and source.get("passed") is True
        ),
        "current_runtime_hashes_match": (
            status["current_runtime_sha256"] == AUDITED_RUNTIME_SHA256
        ),
        "legacy_path_semantics_passed": bool(
            semantics.get("passed") is True
            and semantics.get("trusted_context_none_uses_legacy_oracle") is True
            and semantics.get("trusted_context_none_adds_no_context_argument") is True
            and semantics.get("candidate_sandbox_contract_unchanged") is True
        ),
        "retained_replay_passed": bool(
            replay.get("passed") is True
            and replay.get("artifact_count", 0) > 0
            and replay.get("non_numeric_difference_count") == 0
            and replay.get("failure_taxonomy_change_count") == 0
            and float(replay.get("maximum_absolute_numeric_difference", 1.0))
            <= float(report.get("numeric_tolerance", 0.0))
        ),
        "additional_checks_passed": bool(
            not additional_allowed_changes
            or (
                additional_checks
                and all(value is True for value in additional_checks.values())
            )
        ),
    }
    status["checks"] = checks
    status["accepted"] = all(checks.values())
    if not status["accepted"]:
        status["failure_reason"] = "migration_gate_failed"
    return status
