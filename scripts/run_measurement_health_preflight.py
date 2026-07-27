#!/usr/bin/env python3
"""Run the frozen seven-task measurement-health preflight.

This is deliberately a *measurement* audit rather than another declaration of
task quality.  It re-evaluates one fixed retained artifact, binds historical
baseline/reference and shortcut evidence by hash, and keeps numerical score
resolution separate from scientific materiality.  Missing evidence fails
closed and is reported as ``missing`` rather than silently treated as a fail or
as a zero-noise pass.
"""

from __future__ import annotations

import argparse
import ast
import copy
import hashlib
import json
import math
import platform
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Optional

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from frontier_science.algorithms.common import (  # noqa: E402
    task_contract_sha256,
    task_package_sha256,
)
from frontier_science.evaluate import evaluate_candidate  # noqa: E402
from frontier_science.provenance import finalize_report_trust, source_provenance  # noqa: E402
from frontier_science.spec import load_task_spec  # noqa: E402


SCHEMA_VERSION = 1
DEFAULT_MANIFEST = ROOT / ".research/exploratory_2h_cohort_manifest_2026-07-27_v1.json"
LEGACY_SPEC = ROOT / ".research/measurement_health_preflight_spec_2026-07-27_v1.json"
DEFAULT_SPEC = ROOT / ".research/measurement_health_preflight_spec_2026-07-27_v2.json"
STATUS_VALUES = {"pass", "fail", "missing"}

Evaluator = Callable[[Any, Path, float], Dict[str, Any]]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _task_runtime_paths(task_spec: Any) -> list[Path]:
    roots = [
        task_spec.task_dir / "Task.md",
        task_spec.initial_program_path,
        task_spec.task_dir / "verification",
        task_spec.eval_dir,
    ]
    paths = set()
    for root in roots:
        candidates = root.rglob("*") if root.is_dir() else [root]
        for path in candidates:
            if (
                path.is_file()
                and "__pycache__" not in path.parts
                and path.suffix not in {".pyc", ".pyo"}
            ):
                paths.add(path.resolve())
    return sorted(paths)


def _recorded_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path.resolve())


def _load_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("%s must contain a JSON object" % path)
    return value


def _deep_merge(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    """Return a recursive object merge without mutating either input."""

    result = copy.deepcopy(base)
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def _resolve_preflight_spec(
    path: Path,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[str]]:
    """Resolve an immutable v1 spec or a hash-bound v2 overlay.

    The overlay format lets a later gate add shared protocol evidence without
    copying hundreds of task-specific evidence bindings.  Both the overlay and
    its base are retained as report inputs, and a missing or changed base fails
    closed before any evaluator call.
    """

    document = _load_object(path)
    inputs = [{"path": _recorded_path(path), "sha256": _sha256(path)}]
    if document.get("schema_version") == 1:
        return document, inputs, []
    if document.get("schema_version") != 2:
        return {}, inputs, ["unsupported measurement-health spec schema"]

    binding = document.get("base_spec") or {}
    raw_base_path = binding.get("path")
    expected_hash = binding.get("sha256")
    if not isinstance(raw_base_path, str) or not isinstance(expected_hash, str):
        return {}, inputs, ["v2 preflight base-spec binding is incomplete"]
    base_path = (ROOT / raw_base_path).resolve()
    if not base_path.is_file():
        return {}, inputs, ["v2 preflight base spec is missing"]
    actual_hash = _sha256(base_path)
    inputs.append({"path": _recorded_path(base_path), "sha256": actual_hash})
    if actual_hash != expected_hash:
        return {}, inputs, ["v2 preflight base-spec hash differs"]
    base = _load_object(base_path)
    if base.get("schema_version") != 1:
        return {}, inputs, ["v2 preflight base spec is not schema v1"]

    top_level = document.get("top_level_overrides") or {}
    shared_task = document.get("shared_task_overrides") or {}
    task_overrides = document.get("task_overrides") or []
    if not isinstance(top_level, dict) or not isinstance(shared_task, dict):
        return {}, inputs, ["v2 preflight shared overrides are invalid"]
    if not isinstance(task_overrides, list):
        return {}, inputs, ["v2 preflight task overrides are invalid"]

    resolved = _deep_merge(base, top_level)
    resolved["schema_version"] = 2
    tasks = []
    for row in resolved.get("tasks") or []:
        if not isinstance(row, dict):
            return {}, inputs, ["v2 preflight base task record is invalid"]
        tasks.append(_deep_merge(row, shared_task))
    override_by_task = {}
    for override in task_overrides:
        if not isinstance(override, dict) or not isinstance(override.get("task"), str):
            return {}, inputs, ["v2 preflight task override lacks a task id"]
        task_id = override["task"]
        if task_id in override_by_task:
            return {}, inputs, ["v2 preflight task overrides contain duplicates"]
        override_by_task[task_id] = override
    known = {row.get("task") for row in tasks}
    if set(override_by_task) - known:
        return {}, inputs, ["v2 preflight task override is outside the frozen cohort"]
    resolved["tasks"] = [
        _deep_merge(row, override_by_task.get(row["task"], {})) for row in tasks
    ]
    return resolved, inputs, []


def _json_pointer(value: Any, pointer: str) -> Any:
    if pointer == "":
        return value
    if not isinstance(pointer, str) or not pointer.startswith("/"):
        raise ValueError("invalid JSON pointer %r" % pointer)
    current = value
    for raw in pointer[1:].split("/"):
        token = raw.replace("~1", "/").replace("~0", "~")
        if isinstance(current, list):
            current = current[int(token)]
        elif isinstance(current, dict):
            current = current[token]
        else:
            raise KeyError(pointer)
    return current


def _finite(value: Any) -> Optional[float]:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def _check(status: str, **fields: Any) -> dict[str, Any]:
    if status not in STATUS_VALUES:
        raise ValueError("unknown preflight status %r" % status)
    return {"status": status, "passed": status == "pass", **fields}


def _bound_document(binding: dict[str, Any]) -> tuple[Optional[dict[str, Any]], dict[str, Any]]:
    raw_path = binding.get("path")
    expected_hash = binding.get("sha256")
    if not isinstance(raw_path, str) or not raw_path or not isinstance(expected_hash, str):
        return None, {
            "path": raw_path,
            "expected_sha256": expected_hash,
            "actual_sha256": None,
            "hash_matches": False,
            "trusted_evidence": False,
            "reason": "invalid evidence binding",
        }
    path = (ROOT / raw_path).resolve()
    if not path.is_file():
        return None, {
            "path": _recorded_path(path),
            "expected_sha256": expected_hash,
            "actual_sha256": None,
            "hash_matches": False,
            "trusted_evidence": False,
            "reason": "bound evidence file is missing",
        }
    actual_hash = _sha256(path)
    try:
        document = _load_object(path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return None, {
            "path": _recorded_path(path),
            "expected_sha256": expected_hash,
            "actual_sha256": actual_hash,
            "hash_matches": actual_hash == expected_hash,
            "trusted_evidence": False,
            "reason": "bound evidence is unreadable: %s" % exc,
        }
    trusted = document.get("trusted_evidence") is True
    return document, {
        "path": _recorded_path(path),
        "expected_sha256": expected_hash,
        "actual_sha256": actual_hash,
        "hash_matches": actual_hash == expected_hash,
        "trusted_evidence": trusted,
        "source_revision": (document.get("source_provenance") or {}).get("git_revision"),
        "reason": None,
    }


def _extract_bound_values(
    binding: dict[str, Any], pointers: Iterable[str],
) -> tuple[list[Any], dict[str, Any]]:
    document, audit = _bound_document(binding)
    if document is None or not audit["hash_matches"] or not audit["trusted_evidence"]:
        return [], audit
    values = []
    missing = []
    for pointer in pointers:
        try:
            values.append(_json_pointer(document, pointer))
        except (KeyError, IndexError, TypeError, ValueError):
            missing.append(pointer)
    audit["pointers"] = list(pointers)
    audit["missing_pointers"] = missing
    return ([] if missing else values), audit


def _comparison(value: Any, operator: str, expected: Any) -> bool:
    if operator == "eq":
        return value == expected
    if operator == "gt":
        left, right = _finite(value), _finite(expected)
        return left is not None and right is not None and left > right
    if operator == "gte":
        left, right = _finite(value), _finite(expected)
        return left is not None and right is not None and left >= right
    raise ValueError("unsupported comparison operator %r" % operator)


def _contract_compatibility(
    source_revision: Any, task_spec: Any,
) -> dict[str, Any]:
    paths = _task_runtime_paths(task_spec)
    changed = []
    missing = []
    if not isinstance(source_revision, str) or not source_revision:
        return {
            "source_revision": source_revision,
            "runtime_files_unchanged": False,
            "changed_paths": [],
            "missing_at_source_revision": [],
            "reason": "evidence source revision is missing",
        }
    current_relatives = {
        path.relative_to(ROOT).as_posix(): path for path in paths
    }
    task_relative = task_spec.task_dir.relative_to(ROOT).as_posix()
    try:
        historical_names = subprocess.check_output(
            ["git", "ls-tree", "-r", "--name-only", source_revision, "--", task_relative],
            cwd=str(ROOT), text=True, stderr=subprocess.DEVNULL,
        ).splitlines()
    except (OSError, subprocess.CalledProcessError):
        historical_names = []
    historical_runtime = {
        name for name in historical_names
        if (
            name == "%s/Task.md" % task_relative
            or name == task_spec.initial_program_path.relative_to(ROOT).as_posix()
            or name.startswith("%s/verification/" % task_relative)
            or name.startswith("%s/frontier_eval/" % task_relative)
        )
        and "__pycache__" not in Path(name).parts
        and Path(name).suffix not in {".pyc", ".pyo"}
    }
    extra_at_source = sorted(historical_runtime - set(current_relatives))
    added_since_source = sorted(set(current_relatives) - historical_runtime)
    for relative, path in current_relatives.items():
        try:
            historical = subprocess.check_output(
                ["git", "show", "%s:%s" % (source_revision, relative)],
                cwd=str(ROOT), stderr=subprocess.DEVNULL,
            )
        except (OSError, subprocess.CalledProcessError):
            missing.append(relative)
            continue
        if historical != path.read_bytes():
            changed.append(relative)
    passed = not changed and not missing and not extra_at_source and not added_since_source
    return {
        "source_revision": source_revision,
        "runtime_files_unchanged": passed,
        "changed_paths": changed,
        "missing_at_source_revision": missing,
        "extra_at_source_revision": extra_at_source,
        "added_since_source_revision": added_since_source,
        "compared_file_count": len(paths),
        "reason": None if passed else "task runtime differs from the calibration evidence revision",
    }


def _baseline_reference_check(
    config: dict[str, Any], task_spec: Any,
) -> dict[str, Any]:
    binding = config.get("evidence") or {}
    pointers = [
        config.get("baseline_score_pointer"),
        config.get("baseline_valid_pointer"),
        config.get("reference_score_pointer"),
        config.get("reference_valid_pointer"),
    ]
    if any(not isinstance(pointer, str) for pointer in pointers):
        return _check("missing", reason="baseline/reference pointers are incomplete")
    values, audit = _extract_bound_values(binding, pointers)
    if not values:
        return _check("missing", evidence=audit, reason="bound baseline/reference evidence unavailable")
    compatibility = _contract_compatibility(audit.get("source_revision"), task_spec)
    if not compatibility["runtime_files_unchanged"]:
        return _check(
            "missing", evidence=audit, contract_compatibility=compatibility,
            reason="baseline/reference evidence is not bound to the current task runtime",
        )
    baseline_score = _finite(values[0])
    baseline_valid = _finite(values[1])
    reference_score = _finite(values[2])
    reference_valid = _finite(values[3])
    minimum_gap = _finite(config.get("minimum_score_gap"))
    if None in {baseline_score, baseline_valid, reference_score, reference_valid, minimum_gap}:
        return _check("missing", evidence=audit, reason="baseline/reference values are non-finite or threshold missing")
    gap = reference_score - baseline_score
    passed = baseline_valid == 1.0 and reference_valid == 1.0 and gap >= minimum_gap
    return _check(
        "pass" if passed else "fail",
        baseline_score=baseline_score,
        reference_score=reference_score,
        score_gap=gap,
        minimum_score_gap=minimum_gap,
        baseline_valid=baseline_valid,
        reference_valid=reference_valid,
        evidence=audit,
        contract_compatibility=compatibility,
        reason=None if passed else "valid baseline/reference separation is too small",
    )


def _shortcut_check(config: dict[str, Any], task_spec: Any) -> dict[str, Any]:
    binding = config.get("evidence") or {}
    predicates = config.get("predicates")
    if not isinstance(predicates, list) or not predicates:
        return _check("missing", reason="no shortcut-resistance predicates declared")
    pointers = [row.get("pointer") for row in predicates]
    if any(not isinstance(pointer, str) for pointer in pointers):
        return _check("missing", reason="shortcut-resistance pointer is incomplete")
    values, audit = _extract_bound_values(binding, pointers)
    if not values:
        return _check("missing", evidence=audit, reason="bound shortcut-resistance evidence unavailable")
    compatibility = _contract_compatibility(audit.get("source_revision"), task_spec)
    if not compatibility["runtime_files_unchanged"]:
        return _check(
            "missing", evidence=audit, contract_compatibility=compatibility,
            reason="shortcut-resistance evidence is not bound to the current task runtime",
        )
    rows = []
    passed = True
    for predicate, value in zip(predicates, values):
        operator = str(predicate.get("operator", "eq"))
        expected = predicate.get("value", True)
        matched = _comparison(value, operator, expected)
        rows.append({
            "pointer": predicate["pointer"],
            "operator": operator,
            "expected": expected,
            "observed": value,
            "passed": matched,
        })
        passed = passed and matched
    return _check(
        "pass" if passed else "fail",
        predicates=rows,
        evidence=audit,
        contract_compatibility=compatibility,
        reason=None if passed else "one or more shortcut-resistance predicates failed",
    )


def _source_shortcut_check(
    artifact_path: Path,
    expected_sha256: Any,
    config: dict[str, Any],
    *,
    display_path: Optional[str] = None,
) -> dict[str, Any]:
    if not artifact_path.is_file() or _sha256(artifact_path) != expected_sha256:
        return _check("missing", reason="shortcut scan artifact binding failed")
    source = artifact_path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source)
        syntax_error = None
    except SyntaxError as exc:
        tree = None
        syntax_error = "%s:%s" % (exc.lineno, exc.msg)
    forbidden_modules = set(config.get("forbidden_modules") or [
        "builtins", "ctypes", "http", "importlib", "inspect", "os", "pathlib",
        "requests", "shutil", "socket", "subprocess", "urllib",
    ])
    forbidden_calls = set(config.get("forbidden_calls") or [
        "__import__", "breakpoint", "compile", "eval", "exec", "input", "open",
    ])
    import_hits = []
    call_hits = []
    if tree is not None:
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root = alias.name.split(".")[0]
                    if root in forbidden_modules:
                        import_hits.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                root = (node.module or "").split(".")[0]
                if root in forbidden_modules:
                    import_hits.append(node.module or "")
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.func.id in forbidden_calls:
                    call_hits.append(node.func.id)
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if node.func.attr in {"read_bytes", "read_text"}:
                    call_hits.append(node.func.attr)
    lowered = source.lower()
    literal_hits = [
        token for token in config.get("forbidden_literals") or []
        if isinstance(token, str) and token.lower() in lowered
    ]
    passed = tree is not None and not import_hits and not call_hits and not literal_hits
    return _check(
        "pass" if passed else "fail",
        path=display_path or _recorded_path(artifact_path),
        source_sha256=expected_sha256,
        source_utf8_bytes=len(source.encode("utf-8")),
        syntax_valid=tree is not None,
        syntax_error=syntax_error,
        forbidden_import_hits=sorted(set(import_hits)),
        forbidden_call_hits=sorted(set(call_hits)),
        forbidden_literal_hits=sorted(set(literal_hits)),
        runtime_network_and_filesystem_isolation_checked_separately=True,
        scope=(
            "narrow retained-source scan plus secure black-box execution; not an exhaustive "
            "contamination, memorization, or benchmark-overfitting audit"
        ),
        reason=None if passed else "retained artifact failed the narrow shortcut source scan",
    )


def _materialize_portable_artifact(
    config: dict[str, Any],
    task_id: str,
    expected_sha256: Any,
    frozen_runtime_contract_sha256: Any,
    directory: Path,
) -> tuple[Optional[Path], dict[str, Any]]:
    portable = config.get("portable_artifact") or {}
    binding = portable.get("evidence") or {}
    pointer = portable.get("artifact_pointer")
    if not isinstance(pointer, str):
        return None, {"reason": "portable artifact pointer is missing"}
    document, audit = _bound_document(binding)
    # Portable artifact packs are immutable inputs rather than derived experiment
    # results and therefore use their explicit purpose/claim binding, not the
    # generic trusted_evidence flag.
    if document is None or not audit["hash_matches"]:
        return None, {**audit, "reason": "portable artifact pack is unavailable"}
    if not (
        document.get("purpose")
        == "portable_fixed_artifacts_for_frozen_seven_task_measurement_health_preflight"
        and isinstance(document.get("claim_limit"), str)
    ):
        return None, {**audit, "reason": "portable artifact pack purpose is invalid"}
    try:
        row = _json_pointer(document, pointer)
    except (KeyError, IndexError, TypeError, ValueError):
        return None, {**audit, "reason": "portable artifact row is missing"}
    if not isinstance(row, dict):
        return None, {**audit, "reason": "portable artifact row is not an object"}
    source = row.get("source")
    origin = row.get("origin") or {}
    if not (
        row.get("task") == task_id
        and isinstance(source, str)
        and row.get("candidate_sha256") == expected_sha256
        and origin.get("task_contract_sha256") == frozen_runtime_contract_sha256
    ):
        return None, {**audit, "reason": "portable artifact identity or contract differs"}
    payload = source.encode("utf-8")
    if (
        hashlib.sha256(payload).hexdigest() != expected_sha256
        or len(payload) != row.get("candidate_utf8_bytes")
    ):
        return None, {**audit, "reason": "portable artifact content binding differs"}
    target = directory / (task_id.replace("/", "__") + ".py")
    target.write_bytes(payload)
    return target, {
        **audit,
        "artifact_pointer": pointer,
        "task": task_id,
        "candidate_sha256": expected_sha256,
        "candidate_utf8_bytes": len(payload),
        "origin": origin,
        "reason": None,
    }


def _bound_boolean_check(config: dict[str, Any], label: str) -> dict[str, Any]:
    binding = config.get("evidence") or {}
    pointer = config.get("pointer")
    if not isinstance(pointer, str):
        return _check("missing", reason="%s evidence pointer is missing" % label)
    values, audit = _extract_bound_values(binding, [pointer])
    if not values:
        return _check("missing", evidence=audit, reason="bound %s evidence unavailable" % label)
    expected = config.get("expected", True)
    passed = values[0] == expected
    return _check(
        "pass" if passed else "fail", evidence=audit,
        observed=values[0], expected=expected,
        reason=None if passed else "%s evidence did not meet its declared criterion" % label,
    )


def _revision_paths_compatibility(
    source_revision: Any, relative_paths: Iterable[str],
) -> dict[str, Any]:
    paths = sorted(set(relative_paths))
    changed = []
    missing = []
    if not isinstance(source_revision, str) or not source_revision:
        return {
            "source_revision": source_revision,
            "runtime_files_unchanged": False,
            "paths": paths,
            "changed_paths": [],
            "missing_at_source_revision": [],
            "reason": "evidence source revision is missing",
        }
    for relative in paths:
        current = ROOT / relative
        if not current.is_file():
            missing.append(relative)
            continue
        try:
            historical = subprocess.check_output(
                ["git", "show", "%s:%s" % (source_revision, relative)],
                cwd=str(ROOT), stderr=subprocess.DEVNULL,
            )
        except (OSError, subprocess.CalledProcessError):
            missing.append(relative)
            continue
        if historical != current.read_bytes():
            changed.append(relative)
    passed = not changed and not missing
    return {
        "source_revision": source_revision,
        "runtime_files_unchanged": passed,
        "paths": paths,
        "changed_paths": changed,
        "missing_at_source_revision": missing,
        "reason": None if passed else "recovery runtime differs from the fault-audit revision",
    }


def _task_card(task_spec: Any) -> tuple[Optional[dict[str, Any]], Optional[str]]:
    path = task_spec.task_dir / "TASK_CARD.yaml"
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        return None, "task card is unreadable: %s" % exc
    if not isinstance(value, dict):
        return None, "task card is not an object"
    return value, None


def _recovery_check(config: dict[str, Any], task_spec: Any) -> dict[str, Any]:
    """Bind protocol fault evidence to deterministic local task execution.

    This deliberately establishes logical exactly-once outcomes and oracle-budget
    accounting only.  It never upgrades that result to physical exactly-once lab
    execution.
    """

    predicates = config.get("predicates") or []
    pointers = [row.get("pointer") for row in predicates]
    if not predicates or any(not isinstance(pointer, str) for pointer in pointers):
        return _check("missing", reason="recovery evidence predicates are incomplete")
    values, audit = _extract_bound_values(config.get("evidence") or {}, pointers)
    if not values:
        return _check("missing", evidence=audit, reason="bound recovery evidence unavailable")
    rows = []
    predicates_passed = True
    for predicate, value in zip(predicates, values):
        operator = str(predicate.get("operator", "eq"))
        expected = predicate.get("value", True)
        matched = _comparison(value, operator, expected)
        rows.append({
            "pointer": predicate["pointer"], "operator": operator,
            "expected": expected, "observed": value, "passed": matched,
        })
        predicates_passed = predicates_passed and matched

    compatibility = _revision_paths_compatibility(
        audit.get("source_revision"), config.get("runtime_paths") or []
    )
    card, card_error = _task_card(task_spec)
    deterministic = (
        ((card or {}).get("oracle") or {}).get("deterministic") is True
    )
    expected_scope = (
        "PROCESS_CRASH_DURABLE_RECEIPT_LOGICAL_EXACTLY_ONCE_OUTCOME_AND_"
        "ORACLE_BUDGET_FOR_DETERMINISTIC_LOCAL_EVALUATORS_NOT_PHYSICAL_"
        "EXACTLY_ONCE_LIVE_LAB_EXECUTION"
    )
    document, _ = _bound_document(config.get("evidence") or {})
    scope_matches = bool(document and document.get("evidence_scope") == expected_scope)
    passed = bool(
        predicates_passed
        and compatibility["runtime_files_unchanged"]
        and deterministic
        and scope_matches
    )
    reasons = []
    if not predicates_passed:
        reasons.append("one or more recovery fault predicates failed")
    if not compatibility["runtime_files_unchanged"]:
        reasons.append("recovery runtime differs from the fault-audit revision")
    if not deterministic:
        reasons.append(card_error or "task oracle is not declared deterministic")
    if not scope_matches:
        reasons.append("recovery evidence scope is missing or broader than allowed")
    return _check(
        "pass" if passed else "fail",
        predicates=rows,
        evidence=audit,
        runtime_compatibility=compatibility,
        task_card_path=_recorded_path(task_spec.task_dir / "TASK_CARD.yaml"),
        oracle_deterministic=deterministic,
        evidence_scope_matches=scope_matches,
        claim=(
            "logical exactly-once outcome and oracle-budget accounting for a "
            "deterministic local evaluator; not physical exactly-once execution"
        ),
        reason=None if passed else "; ".join(reasons),
    )


def _trajectory_resolution_check(
    config: dict[str, Any], noise_span: Optional[float], task_spec: Any,
) -> dict[str, Any]:
    binding = config.get("evidence") or {}
    pointer = config.get("trajectory_pointer")
    if not isinstance(pointer, str):
        return _check("missing", reason="trajectory pointer is missing")
    values, audit = _extract_bound_values(binding, [pointer])
    if not values or not isinstance(values[0], list):
        return _check("missing", evidence=audit, reason="bound trajectory evidence unavailable")
    compatibility = _contract_compatibility(audit.get("source_revision"), task_spec)
    if not compatibility["runtime_files_unchanged"]:
        return _check(
            "missing", evidence=audit, contract_compatibility=compatibility,
            reason="trajectory evidence is not bound to the current task runtime",
        )
    scores = sorted({
        number for row in values[0]
        if isinstance(row, dict) and row.get("valid") in {True, 1, 1.0}
        for number in [_finite(
            row.get("score") if row.get("score") is not None
            else row.get("combined_score")
        )]
        if number is not None
    })
    nonzero_gaps = [
        right - left for left, right in zip(scores, scores[1:]) if right > left
    ]
    if not nonzero_gaps:
        return _check(
            "fail", evidence=audit, distinct_scores=scores,
            contract_compatibility=compatibility,
            reason="no non-zero score difference was observed in the bound trajectory",
        )
    minimum_gap = min(nonzero_gaps)
    multiplier = _finite(config.get("minimum_noise_multiplier"))
    absolute_floor = _finite(config.get("absolute_resolution_floor"))
    if multiplier is None or absolute_floor is None or noise_span is None:
        return _check("missing", evidence=audit, reason="resolution policy or measured noise is missing")
    required = max(absolute_floor, multiplier * noise_span)
    passed = minimum_gap > required
    return _check(
        "pass" if passed else "fail",
        distinct_scores=scores,
        minimum_nonzero_score_gap=minimum_gap,
        measured_fixed_artifact_noise_span=noise_span,
        minimum_noise_multiplier=multiplier,
        absolute_resolution_floor=absolute_floor,
        required_score_gap=required,
        evidence=audit,
        contract_compatibility=compatibility,
        reason=None if passed else "observed score gap does not clear the measured numerical resolution",
    )


def _scientific_materiality_check(config: Any) -> dict[str, Any]:
    if not isinstance(config, dict):
        return _check(
            "missing",
            reason=(
                "no domain-grounded scientific materiality threshold is declared; "
                "numerical score resolution cannot substitute for materiality"
            ),
        )
    binding = config.get("evidence") or {}
    pointer = config.get("declaration_pointer")
    if not isinstance(pointer, str):
        return _check("missing", reason="scientific materiality declaration pointer is missing")
    values, audit = _extract_bound_values(binding, [pointer])
    if not values:
        return _check("missing", evidence=audit, reason="bound scientific materiality declaration unavailable")
    expected = config.get("expected", True)
    passed = values[0] == expected
    return _check(
        "pass" if passed else "fail", evidence=audit,
        declared_value=values[0], expected=expected,
        reason=None if passed else "scientific materiality declaration did not pass",
    )


def _protocol_check(config: dict[str, Any]) -> dict[str, Any]:
    binding = config.get("evidence") or {}
    predicates = config.get("predicates") or []
    pointers = [row.get("pointer") for row in predicates]
    if not predicates or any(not isinstance(pointer, str) for pointer in pointers):
        return _check("missing", reason="protocol evidence predicates are incomplete")
    values, audit = _extract_bound_values(binding, pointers)
    if not values:
        return _check("missing", evidence=audit, reason="bound protocol evidence unavailable")
    rows = []
    passed = True
    for predicate, value in zip(predicates, values):
        operator = str(predicate.get("operator", "eq"))
        expected = predicate.get("value", True)
        matched = _comparison(value, operator, expected)
        rows.append({
            "pointer": predicate["pointer"], "operator": operator,
            "expected": expected, "observed": value, "passed": matched,
        })
        passed = passed and matched
    return _check(
        "pass" if passed else "fail", predicates=rows, evidence=audit,
        reason=None if passed else "protocol evidence predicate failed",
    )


def _evaluate_repeated(
    task_spec: Any,
    artifact_path: Path,
    repetitions: int,
    timeout_s: float,
    evaluator: Evaluator,
) -> dict[str, Any]:
    if repetitions < 2:
        return _check("missing", reason="fixed-artifact noise requires at least two repetitions")
    results = []
    for _ in range(repetitions):
        try:
            result = evaluator(task_spec, artifact_path, timeout_s)
        except Exception as exc:  # noqa: BLE001
            result = {
                "combined_score": 0.0, "valid": 0.0,
                "infrastructure_failure": 1.0,
                "error_message": "preflight evaluator raised: %s" % exc,
            }
        results.append(result)
    scores = [_finite(row.get("combined_score")) for row in results]
    valid = [_finite(row.get("valid")) for row in results]
    infrastructure_failures = sum(bool(row.get("infrastructure_failure")) for row in results)
    finite_scores = [value for value in scores if value is not None]
    all_valid = len(valid) == repetitions and all(value == 1.0 for value in valid)
    noise_span = max(finite_scores) - min(finite_scores) if len(finite_scores) == repetitions else None
    tolerance = 1e-12
    numeric_fields = sorted(set.intersection(*(
        {
            key for key, value in row.items()
            if _finite(value) is not None
        }
        for row in results
    ))) if results else []
    numeric_spans = {
        key: max(float(row[key]) for row in results) - min(float(row[key]) for row in results)
        for key in numeric_fields
    }
    maximum_numeric_span = max(numeric_spans.values(), default=0.0)
    canonical_payload_hashes = [
        hashlib.sha256(json.dumps(
            row, sort_keys=True, separators=(",", ":"), allow_nan=False,
        ).encode("utf-8")).hexdigest()
        for row in results
    ]
    exact_payload_match = len(set(canonical_payload_hashes)) == 1
    passed = (
        infrastructure_failures == 0
        and all_valid
        and noise_span is not None
        and noise_span <= tolerance
        and maximum_numeric_span <= tolerance
        and exact_payload_match
    )
    return _check(
        "pass" if passed else "fail",
        repetitions=repetitions,
        scores=scores,
        valid=valid,
        noise_span=noise_span,
        numeric_field_spans=numeric_spans,
        maximum_numeric_field_span=maximum_numeric_span,
        canonical_payload_sha256=canonical_payload_hashes,
        exact_payload_match=exact_payload_match,
        maximum_allowed_noise_span=tolerance,
        infrastructure_failure_count=infrastructure_failures,
        results=results,
        reason=None if passed else "fixed artifact was invalid, unstable, or suffered infrastructure failure",
    )


def _task_preflight(
    manifest_row: dict[str, Any],
    config: dict[str, Any],
    evaluator: Evaluator,
) -> dict[str, Any]:
    task_id = manifest_row["task"]
    task_dir = ROOT / "benchmarks" / task_id
    task_spec = load_task_spec(task_dir)
    current_contract = task_contract_sha256(task_spec)
    current_package = task_package_sha256(task_spec)
    expected_artifact_hash = config.get("fixed_artifact_sha256")
    contract_binding_passed = current_contract == manifest_row.get("runtime_contract_sha256")
    package_binding_passed = current_package == config.get("task_package_sha256")

    repetitions = int(config.get("fixed_artifact_repetitions", 3))
    timeout_s = float(config.get("evaluation_timeout_seconds", 300.0))
    with tempfile.TemporaryDirectory(prefix="fs_measurement_health_preflight_") as temporary:
        artifact_path, portable_audit = _materialize_portable_artifact(
            config,
            task_id,
            expected_artifact_hash,
            manifest_row.get("runtime_contract_sha256"),
            Path(temporary),
        )
        actual_artifact_hash = (
            _sha256(artifact_path) if artifact_path is not None and artifact_path.is_file()
            else None
        )
        artifact_binding_passed = (
            isinstance(expected_artifact_hash, str)
            and actual_artifact_hash == expected_artifact_hash
            and portable_audit.get("reason") is None
        )
        if artifact_binding_passed and contract_binding_passed and package_binding_passed:
            noise = _evaluate_repeated(
                task_spec, artifact_path, repetitions, timeout_s, evaluator
            )
        else:
            noise = _check(
                "missing",
                repetitions=repetitions,
                reason="portable artifact or frozen runtime contract binding failed",
            )
        noise_span = (
            _finite(noise.get("noise_span")) if noise["status"] == "pass" else None
        )
        portable_display = "%s#%s" % (
            portable_audit.get("path", "portable-artifact-pack"),
            portable_audit.get("artifact_pointer", "missing"),
        )
        shortcut = (
            _shortcut_check(config["shortcut_resistance"], task_spec)
            if (config.get("shortcut_resistance") or {}).get("mode") == "bound_evidence"
            else _source_shortcut_check(
                artifact_path or Path(temporary) / "missing.py",
                expected_artifact_hash,
                config.get("shortcut_resistance") or {},
                display_path=portable_display,
            )
        )
        checks = {
            "frozen_runtime_contract": _check(
                "pass" if contract_binding_passed else "fail",
                expected_sha256=manifest_row.get("runtime_contract_sha256"),
                actual_sha256=current_contract,
            ),
            "frozen_task_package": _check(
                "pass" if package_binding_passed else "fail",
                expected_sha256=config.get("task_package_sha256"),
                actual_sha256=current_package,
                scope="all task source/data files excluding generated Python caches",
            ),
            "fixed_artifact_binding": _check(
                "pass" if artifact_binding_passed else "fail",
                path=portable_display,
                expected_sha256=expected_artifact_hash,
                actual_sha256=actual_artifact_hash,
                portable_artifact=portable_audit,
            ),
            "fixed_artifact_noise": noise,
            "baseline_reference_separation": _baseline_reference_check(
                config.get("baseline_reference") or {}, task_spec
            ),
            "evaluator_numerical_resolution": _trajectory_resolution_check(
                config.get("numerical_resolution") or {}, noise_span, task_spec
            ),
            "scientific_materiality": _scientific_materiality_check(
                config.get("scientific_materiality")
            ),
            "shortcut_resistance": shortcut,
            "content_addressed_atomic_capture": _protocol_check(
                config.get("content_addressed_atomic_capture") or {}
            ),
            "exactly_once_recovery": _recovery_check(
                config.get("exactly_once_recovery") or {}, task_spec
            ),
        }
    gate_passed = all(row["status"] == "pass" for row in checks.values())
    return {
        "task": task_id,
        "checks": checks,
        "status_counts": {
            status: sum(row["status"] == status for row in checks.values())
            for status in ("pass", "fail", "missing")
        },
        "preflight_passed": gate_passed,
        "long_horizon_run_permitted": gate_passed,
        "not_permitted_reasons": [
            name for name, row in checks.items() if row["status"] != "pass"
        ],
    }


def build_report(
    manifest_path: Path = DEFAULT_MANIFEST,
    spec_path: Path = DEFAULT_SPEC,
    *,
    evaluator: Evaluator = evaluate_candidate,
) -> dict[str, Any]:
    manifest_path = manifest_path.resolve()
    spec_path = spec_path.resolve()
    manifest = _load_object(manifest_path)
    evidence_spec, spec_inputs, issues = _resolve_preflight_spec(spec_path)

    expected_manifest_hash = evidence_spec.get("cohort_manifest_sha256")
    if _sha256(manifest_path) != expected_manifest_hash:
        issues.append("preflight spec does not bind the current cohort manifest")
    manifest_tasks = [row.get("task") for row in manifest.get("tasks") or []]
    configs = evidence_spec.get("tasks") or []
    config_tasks = [row.get("task") for row in configs]
    if manifest_tasks != config_tasks:
        issues.append("preflight task order differs from the frozen cohort")
    if len(manifest_tasks) != 7:
        issues.append("preflight requires exactly seven frozen exploratory tasks")
    duplicate_tasks = len(config_tasks) != len(set(config_tasks))
    if duplicate_tasks:
        issues.append("preflight spec contains duplicate task records")

    config_by_task = {row.get("task"): row for row in configs if isinstance(row, dict)}
    task_rows = []
    if not issues:
        for manifest_row in manifest["tasks"]:
            task_rows.append(_task_preflight(
                manifest_row, config_by_task[manifest_row["task"]], evaluator
            ))

    passed_count = sum(row["preflight_passed"] for row in task_rows)
    status_counts = {
        status: sum(row["status_counts"][status] for row in task_rows)
        for status in ("pass", "fail", "missing")
    }
    report: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "trust_status": "MEASUREMENT_HEALTH_PREFLIGHT",
        "evidence_scope": (
            "SEVEN_TASK_FIXED_ARTIFACT_NOISE_BASELINE_REFERENCE_NUMERICAL_"
            "RESOLUTION_SHORTCUT_AND_PROTOCOL_PREFLIGHT_NOT_POST_2H_HEADROOM_"
            "CONFIRMATORY_EXTERNAL_VALIDATION_OR_AUTONOMOUS_DISCOVERY_EVIDENCE"
        ),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_provenance": source_provenance(ROOT),
        "environment": {"python": sys.version, "platform": platform.platform()},
        "inputs": [
            {"path": _recorded_path(manifest_path), "sha256": _sha256(manifest_path)},
            *spec_inputs,
        ],
        "policy": {
            "fail_closed": True,
            "status_values": ["pass", "fail", "missing"],
            "fixed_artifact_repetitions": 3,
            "fixed_artifact_maximum_noise_span": 1e-12,
            "numerical_resolution_is_not_scientific_materiality": True,
            "scientific_materiality_requires_domain_grounded_bound_evidence": True,
            "post_2h_headroom_is_not_tested_by_preflight": True,
        },
        "task_count": len(task_rows),
        "preflight_passed_count": passed_count,
        "long_horizon_run_permitted_count": passed_count,
        "check_status_counts": status_counts,
        "tasks": task_rows,
        "issues": issues,
        "limitations": [
            "A deterministic evaluator and resolvable score do not prove that a score change is scientifically meaningful.",
            "Historical calibration witnesses establish baseline/reference separation only under their bound contracts.",
            "Source scans are narrow shortcut checks, not evidence against every form of benchmark overfitting or contamination.",
            "This preflight cannot demonstrate material improvement after two hours; that requires completed sentinel trajectories.",
            "Recovery evidence establishes logical exactly-once outcomes only for deterministic local evaluators, not physical exactly-once live-lab execution.",
            "No task passing this audit becomes confirmatory, externally validated, or autonomous-discovery evidence.",
        ],
    }
    finalize_report_trust(report, not issues)
    return report


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Seven-task measurement-health preflight",
        "",
        "This report separates evaluator mechanics from scientific materiality and fails closed",
        "on missing evidence. It does not establish post-2h headroom or confirmatory readiness.",
        "",
        "Preflight passes: **%d / %d**. Long-horizon runs permitted: **%d**." % (
            report["preflight_passed_count"], report["task_count"],
            report["long_horizon_run_permitted_count"],
        ),
        "",
        "| Task | pass | fail | missing | permitted | blockers |",
        "|---|---:|---:|---:|:---:|---|",
    ]
    for row in report["tasks"]:
        counts = row["status_counts"]
        lines.append("| %s | %d | %d | %d | %s | %s |" % (
            row["task"], counts["pass"], counts["fail"], counts["missing"],
            "yes" if row["long_horizon_run_permitted"] else "no",
            ", ".join(row["not_permitted_reasons"]) or "--",
        ))
    lines.extend([
        "",
        "Numerical evaluator resolution is reported separately from domain-grounded scientific",
        "materiality. Missing materiality declarations and missing crash-recovery evidence remain",
        "explicit blockers even when fixed-artifact replay is deterministic.",
        "",
    ])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--spec", type=Path, default=DEFAULT_SPEC)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--markdown-output", type=Path)
    args = parser.parse_args()
    report = build_report(args.manifest, args.spec)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    if args.markdown_output:
        args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
        args.markdown_output.write_text(render_markdown(report), encoding="utf-8")
    print(json.dumps({
        "task_count": report["task_count"],
        "preflight_passed_count": report["preflight_passed_count"],
        "long_horizon_run_permitted_count": report["long_horizon_run_permitted_count"],
        "check_status_counts": report["check_status_counts"],
        "issues": report["issues"],
        "execution_passed": report["execution_passed"],
        "trusted_evidence": report["trusted_evidence"],
    }, indent=2))
    return 0 if report["execution_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
