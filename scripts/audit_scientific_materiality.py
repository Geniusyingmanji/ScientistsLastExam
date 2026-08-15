#!/usr/bin/env python3
"""Audit domain-grounded materiality contracts for the frozen seven tasks.

The audit answers a narrow prerequisite question: does each calibrated task
landscape contain one *same-candidate* witness that clears preregistered raw
scientific thresholds on development, held-out/confirmation, and robustness
axes?  It does not test an agent, post-2h headroom, external validity, or
autonomous discovery.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Optional

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from sle.provenance import finalize_report_trust, source_provenance  # noqa: E402
from sle.registry import find_task  # noqa: E402
from scripts.run_measurement_health_preflight import (  # noqa: E402
    _contract_compatibility,
    load_inert_evaluators,
)


SCHEMA_VERSION = 1
DEFAULT_CONTRACT = (
    ROOT / ".research/scientific_materiality_contracts_2026-07-27_v1.json"
)
ALLOWED_AXES = {"development", "heldout", "robustness", "independent_confirmation"}
ALLOWED_KINDS = {"paired_scalar", "paired_records", "values_bound"}
FORBIDDEN_PRIMARY_TOKENS = {
    "combined_score", "raw_score", "normalized_exact_quality",
    "normalized_score", "score",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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


def _descends(pointer: Any, root: Any) -> bool:
    return bool(
        isinstance(pointer, str)
        and isinstance(root, str)
        and (pointer == root or pointer.startswith(root.rstrip("/") + "/"))
    )


def _flatten(value: Any) -> list[Any]:
    if isinstance(value, list):
        result = []
        for item in value:
            result.extend(_flatten(item))
        return result
    return [value]


def _signed_change(
    baseline: float, witness: float, direction: str,
) -> tuple[float, Optional[float]]:
    if direction == "increase":
        absolute = witness - baseline
    elif direction == "decrease":
        absolute = baseline - witness
    else:
        raise ValueError("invalid improvement direction %r" % direction)
    relative = absolute / abs(baseline) if baseline != 0.0 else None
    return absolute, relative


def _change_passes(
    absolute: float,
    relative: Optional[float],
    criterion: dict[str, Any],
) -> bool:
    absolute_threshold = criterion.get("minimum_absolute_change")
    relative_threshold = criterion.get("minimum_relative_change")
    if absolute_threshold is None and relative_threshold is None:
        return False
    passed = True
    if absolute_threshold is not None:
        threshold = _finite(absolute_threshold)
        passed = passed and threshold is not None and absolute >= threshold
    if relative_threshold is not None:
        threshold = _finite(relative_threshold)
        passed = (
            passed and threshold is not None and relative is not None
            and relative >= threshold
        )
    return bool(passed)


def _paired_scalar(document: dict[str, Any], criterion: dict[str, Any]) -> dict[str, Any]:
    try:
        raw_baseline = _json_pointer(document, criterion["baseline_pointer"])
        raw_witness = _json_pointer(document, criterion["witness_pointer"])
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        return {"passed": False, "reason": "scalar pointer unavailable: %s" % exc}
    baseline = _finite(raw_baseline)
    witness = _finite(raw_witness)
    if baseline is None or witness is None:
        return {"passed": False, "reason": "scalar materiality value is non-finite"}
    try:
        absolute, relative = _signed_change(
            baseline, witness, criterion.get("direction")
        )
    except ValueError as exc:
        return {"passed": False, "reason": str(exc)}
    passed = _change_passes(absolute, relative, criterion)
    return {
        "passed": passed,
        "baseline": baseline,
        "witness": witness,
        "direction": criterion.get("direction"),
        "signed_absolute_change": absolute,
        "signed_relative_change": relative,
        "minimum_absolute_change": criterion.get("minimum_absolute_change"),
        "minimum_relative_change": criterion.get("minimum_relative_change"),
        "unit": criterion.get("unit"),
        "reason": None if passed else "raw scientific change did not clear the threshold",
    }


def _record_map(value: Any, key: Any) -> tuple[dict[str, dict[str, Any]], Optional[str]]:
    if not isinstance(value, list) or not value:
        return {}, "paired record source is not a non-empty list"
    if not isinstance(key, str) or not key:
        return {}, "paired record key is missing"
    result = {}
    for row in value:
        if not isinstance(row, dict) or not isinstance(row.get(key), str):
            return {}, "paired record lacks a string identity"
        identity = row[key]
        if identity in result:
            return {}, "paired record identities are not unique"
        result[identity] = row
    return result, None


def _paired_records(document: dict[str, Any], criterion: dict[str, Any]) -> dict[str, Any]:
    try:
        baseline_value = _json_pointer(document, criterion["baseline_pointer"])
        witness_value = _json_pointer(document, criterion["witness_pointer"])
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        return {"passed": False, "reason": "record pointer unavailable: %s" % exc}
    baseline, error = _record_map(baseline_value, criterion.get("record_key"))
    if error:
        return {"passed": False, "reason": error}
    witness, error = _record_map(witness_value, criterion.get("record_key"))
    if error:
        return {"passed": False, "reason": error}
    if set(baseline) != set(witness):
        return {"passed": False, "reason": "baseline and witness record identities differ"}

    split_field = criterion.get("split_field")
    required_splits = set(criterion.get("required_splits") or [])
    observed_splits = set()
    value_pointer = criterion.get("value_pointer")
    records = []
    passed = True
    for identity in sorted(baseline):
        left, right = baseline[identity], witness[identity]
        if split_field:
            if left.get(split_field) != right.get(split_field):
                return {"passed": False, "reason": "paired record split labels differ"}
            observed_splits.add(left.get(split_field))
        try:
            left_values = _flatten(_json_pointer(left, value_pointer))
            right_values = _flatten(_json_pointer(right, value_pointer))
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            return {"passed": False, "reason": "record value unavailable: %s" % exc}
        if not left_values or len(left_values) != len(right_values):
            return {"passed": False, "reason": "paired record value shapes differ"}
        comparisons = []
        for raw_left, raw_right in zip(left_values, right_values):
            left_number, right_number = _finite(raw_left), _finite(raw_right)
            if left_number is None or right_number is None:
                return {"passed": False, "reason": "record materiality value is non-finite"}
            try:
                absolute, relative = _signed_change(
                    left_number, right_number, criterion.get("direction")
                )
            except ValueError as exc:
                return {"passed": False, "reason": str(exc)}
            comparison_passed = _change_passes(absolute, relative, criterion)
            comparisons.append({
                "baseline": left_number,
                "witness": right_number,
                "signed_absolute_change": absolute,
                "signed_relative_change": relative,
                "passed": comparison_passed,
            })
            passed = passed and comparison_passed
        records.append({
            "identity": identity,
            "split": left.get(split_field) if split_field else None,
            "comparisons": comparisons,
            "passed": all(row["passed"] for row in comparisons),
        })
    split_coverage = observed_splits >= required_splits
    passed = passed and split_coverage
    absolute_changes = [
        value["signed_absolute_change"]
        for row in records for value in row["comparisons"]
    ]
    relative_changes = [
        value["signed_relative_change"]
        for row in records for value in row["comparisons"]
        if value["signed_relative_change"] is not None
    ]
    return {
        "passed": bool(passed),
        "direction": criterion.get("direction"),
        "record_count": len(records),
        "value_count": len(absolute_changes),
        "required_splits": sorted(required_splits),
        "observed_splits": sorted(value for value in observed_splits if value is not None),
        "split_coverage_passed": split_coverage,
        "minimum_signed_absolute_change": min(absolute_changes),
        "minimum_signed_relative_change": (
            min(relative_changes) if relative_changes else None
        ),
        "minimum_absolute_change": criterion.get("minimum_absolute_change"),
        "minimum_relative_change": criterion.get("minimum_relative_change"),
        "unit": criterion.get("unit"),
        "records": records,
        "reason": None if passed else "one or more raw record changes or splits failed",
    }


def _bound_comparison(value: Any, operator: Any, threshold: Any) -> bool:
    if operator == "eq":
        return value == threshold
    left, right = _finite(value), _finite(threshold)
    if left is None or right is None:
        return False
    if operator == "gte":
        return left >= right
    if operator == "lte":
        return left <= right
    return False


def _values_bound(document: dict[str, Any], criterion: dict[str, Any]) -> dict[str, Any]:
    try:
        source = _json_pointer(document, criterion["source_pointer"])
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        return {"passed": False, "reason": "bound source unavailable: %s" % exc}
    value_pointer = criterion.get("value_pointer")
    if value_pointer is None:
        values = _flatten(source)
    else:
        if not isinstance(source, list) or not source:
            return {"passed": False, "reason": "bound record source is not a non-empty list"}
        values = []
        for row in source:
            try:
                values.extend(_flatten(_json_pointer(row, value_pointer)))
            except (KeyError, IndexError, TypeError, ValueError) as exc:
                return {"passed": False, "reason": "bound record value unavailable: %s" % exc}
    if not values:
        return {"passed": False, "reason": "bound criterion has no values"}
    operator = criterion.get("operator")
    threshold = criterion.get("threshold")
    outcomes = [_bound_comparison(value, operator, threshold) for value in values]
    passed = all(outcomes)
    return {
        "passed": passed,
        "operator": operator,
        "threshold": threshold,
        "value_count": len(values),
        "values": values,
        "outcomes": outcomes,
        "reason": None if passed else "one or more witness bounds failed",
    }


def _criterion_schema_issues(
    criterion: Any,
    baseline_root: Any,
    witness_root: Any,
) -> list[str]:
    if not isinstance(criterion, dict):
        return ["criterion is not an object"]
    issues = []
    if not isinstance(criterion.get("id"), str) or not criterion["id"]:
        issues.append("criterion id is missing")
    kind = criterion.get("kind")
    if kind not in ALLOWED_KINDS:
        issues.append("criterion kind is invalid")
    axes = criterion.get("axes")
    if not isinstance(axes, list) or not axes or not set(axes) <= ALLOWED_AXES:
        issues.append("criterion axes are invalid")
    if kind in {"paired_scalar", "paired_records"}:
        baseline_pointer = criterion.get("baseline_pointer")
        witness_pointer = criterion.get("witness_pointer")
        if not _descends(baseline_pointer, baseline_root):
            issues.append("criterion baseline is outside the declared baseline witness")
        if not _descends(witness_pointer, witness_root):
            issues.append("criterion value is outside the declared material witness")
        primary = criterion.get("value_pointer", witness_pointer)
        token = str(primary).rstrip("/").rsplit("/", 1)[-1]
        if token in FORBIDDEN_PRIMARY_TOKENS or token.startswith("normalized_"):
            issues.append("normalized or combined score cannot be a primary materiality value")
        if criterion.get("direction") not in {"increase", "decrease"}:
            issues.append("criterion direction is invalid")
        if (
            _finite(criterion.get("minimum_absolute_change")) is None
            and _finite(criterion.get("minimum_relative_change")) is None
        ):
            issues.append("criterion materiality threshold is missing")
        if not isinstance(criterion.get("unit"), str) or not criterion["unit"]:
            issues.append("criterion physical unit is missing")
    if kind == "paired_records":
        if not isinstance(criterion.get("value_pointer"), str):
            issues.append("paired-record value pointer is missing")
        if not isinstance(criterion.get("record_key"), str):
            issues.append("paired-record identity key is missing")
        required_splits = criterion.get("required_splits")
        if not isinstance(required_splits, list) or not required_splits:
            issues.append("paired-record split coverage is missing")
    if kind == "values_bound":
        if not _descends(criterion.get("source_pointer"), witness_root):
            issues.append("bound criterion is outside the declared material witness")
        if criterion.get("operator") not in {"eq", "gte", "lte"}:
            issues.append("bound criterion operator is invalid")
        if "threshold" not in criterion:
            issues.append("bound criterion threshold is missing")
    return issues


def _task_card_citation(task_dir: Path, citation: Any) -> tuple[bool, dict[str, Any]]:
    path = task_dir / "TASK_CARD.yaml"
    try:
        card = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        return False, {"path": _recorded_path(path), "reason": str(exc)}
    citations = card.get("citations") if isinstance(card, dict) else None
    expected_doi = citation.get("doi") if isinstance(citation, dict) else None
    expected_title = citation.get("title") if isinstance(citation, dict) else None
    expected_id = "doi:%s" % expected_doi if isinstance(expected_doi, str) else None
    matches = [
        row for row in citations or []
        if isinstance(row, dict) and row.get("id", "").lower() == str(expected_id).lower()
    ]
    verified_title = citation.get("verified_title") if isinstance(citation, dict) else None
    passed = bool(
        len(matches) == 1
        and matches[0].get("title") == expected_title
        and verified_title == expected_title
        and isinstance(citation.get("issued_year"), int)
        and citation.get("metadata_source") == "doi.org CSL JSON"
        and citation.get("retrieved_on") == "2026-07-27"
    )
    return passed, {
        "path": _recorded_path(path),
        "doi": expected_doi,
        "declared_title": expected_title,
        "verified_title": verified_title,
        "task_card_match_count": len(matches),
        "task_card_title": matches[0].get("title") if len(matches) == 1 else None,
        "issued_year": citation.get("issued_year") if isinstance(citation, dict) else None,
        "metadata_source": citation.get("metadata_source") if isinstance(citation, dict) else None,
        "retrieved_on": citation.get("retrieved_on") if isinstance(citation, dict) else None,
        "reason": None if passed else "citation metadata or TASK_CARD binding differs",
    }


def _evidence(config: Any) -> tuple[Optional[dict[str, Any]], dict[str, Any]]:
    binding = config if isinstance(config, dict) else {}
    raw_path, expected_hash = binding.get("path"), binding.get("sha256")
    if not isinstance(raw_path, str) or not isinstance(expected_hash, str):
        return None, {"reason": "evidence binding is incomplete"}
    path = (ROOT / raw_path).resolve()
    if not path.is_file():
        return None, {
            "path": _recorded_path(path), "expected_sha256": expected_hash,
            "actual_sha256": None, "reason": "evidence file is missing",
        }
    actual_hash = _sha256(path)
    try:
        document = _load_object(path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return None, {
            "path": _recorded_path(path), "expected_sha256": expected_hash,
            "actual_sha256": actual_hash, "reason": "evidence is unreadable: %s" % exc,
        }
    passed = bool(
        actual_hash == expected_hash
        and document.get("trusted_evidence") is True
        and document.get("execution_passed") is True
    )
    return (document if passed else None), {
        "path": _recorded_path(path),
        "expected_sha256": expected_hash,
        "actual_sha256": actual_hash,
        "hash_matches": actual_hash == expected_hash,
        "trusted_evidence": document.get("trusted_evidence") is True,
        "execution_passed": document.get("execution_passed") is True,
        "source_revision": (document.get("source_provenance") or {}).get("git_revision"),
        "reason": None if passed else "evidence hash, trust, or execution binding failed",
    }


def _audit_task(row: dict[str, Any]) -> dict[str, Any]:
    task_id = row.get("task")
    issues = []
    if not isinstance(task_id, str):
        return {"task": task_id, "materiality_contract_passed": False, "issues": ["task id is missing"]}
    task_spec = find_task(task_id, include_uncertified=True)
    for key in (
        "scientific_quantity", "improvement_direction", "applicability",
    ):
        if not isinstance(row.get(key), str) or not row[key]:
            issues.append("%s is missing" % key)
    units = row.get("units")
    if not isinstance(units, list) or not units or not all(
        isinstance(value, str) and value for value in units
    ):
        issues.append("scientific units are missing")
    if row.get("threshold_basis") != "benchmark_preregistered_operational_threshold_not_field_consensus":
        issues.append("threshold basis is not explicitly benchmark-operational")
    required_axes = row.get("required_axes")
    if not isinstance(required_axes, list) or not set(required_axes) <= ALLOWED_AXES:
        issues.append("required axes are invalid")
        required_axes = []
    baseline_root = row.get("baseline_pointer")
    witness_root = row.get("material_witness_pointer")
    if not isinstance(baseline_root, str) or not baseline_root.startswith("/"):
        issues.append("baseline witness pointer is invalid")
    if not isinstance(witness_root, str) or not witness_root.startswith("/"):
        issues.append("material witness pointer is invalid")
    if baseline_root == witness_root:
        issues.append("baseline and material witness pointers are identical")

    criteria = row.get("criteria")
    if not isinstance(criteria, list) or not criteria:
        issues.append("materiality criteria are missing")
        criteria = []
    criterion_ids = [
        criterion.get("id") for criterion in criteria if isinstance(criterion, dict)
    ]
    if len(criterion_ids) != len(set(criterion_ids)):
        issues.append("criterion ids are not unique")
    covered_axes = set()
    paired_count = 0
    for criterion in criteria:
        criterion_issues = _criterion_schema_issues(
            criterion, baseline_root, witness_root
        )
        issues.extend(
            "%s: %s" % (
                criterion.get("id", "unknown") if isinstance(criterion, dict) else "unknown",
                issue,
            )
            for issue in criterion_issues
        )
        if isinstance(criterion, dict):
            covered_axes.update(criterion.get("axes") or [])
            paired_count += criterion.get("kind") in {"paired_scalar", "paired_records"}
    if paired_count == 0:
        issues.append("no raw paired materiality criterion is declared")
    if not set(required_axes) <= covered_axes:
        issues.append("criteria do not cover every required scientific axis")

    citation_passed, citation_audit = _task_card_citation(
        task_spec.task_dir, row.get("citation")
    )
    if not citation_passed:
        issues.append("citation binding failed")
    document, evidence_audit = _evidence(row.get("evidence"))
    compatibility = None
    criterion_rows = []
    if document is None:
        issues.append("calibration evidence binding failed")
    else:
        # Same exemption the preflight applies, read from the same spec: an evaluator edit that
        # was *measured* not to move this task's frozen artifact does not unbind evidence taken
        # before it. Without this the audit refuses what the preflight accepts, and the two
        # disagree about the same task.
        compatibility = _contract_compatibility(
            evidence_audit.get("source_revision"), task_spec,
            load_inert_evaluators().get(task_id),
        )
        if not compatibility["runtime_files_unchanged"]:
            issues.append("calibration evidence is not bound to the current task runtime")
        try:
            baseline = _json_pointer(document, baseline_root)
            witness = _json_pointer(document, witness_root)
            if not isinstance(baseline, dict) or not isinstance(witness, dict):
                issues.append("baseline or material witness is not an object")
            if baseline is witness or baseline == witness:
                issues.append("baseline and material witness are not distinct")
        except (KeyError, IndexError, TypeError, ValueError):
            issues.append("baseline or material witness pointer is unavailable")
        if not issues:
            evaluators = {
                "paired_scalar": _paired_scalar,
                "paired_records": _paired_records,
                "values_bound": _values_bound,
            }
            for criterion in criteria:
                result = evaluators[criterion["kind"]](document, criterion)
                criterion_rows.append({
                    "id": criterion["id"],
                    "kind": criterion["kind"],
                    "axes": criterion["axes"],
                    **result,
                })

    criteria_passed = bool(criterion_rows) and all(
        criterion["passed"] for criterion in criterion_rows
    )
    passed = not issues and criteria_passed
    return {
        "task": task_id,
        "scientific_quantity": row.get("scientific_quantity"),
        "units": units,
        "threshold_basis": row.get("threshold_basis"),
        "required_axes": required_axes,
        "covered_axes": sorted(covered_axes),
        "same_witness_enforced": True,
        "baseline_pointer": baseline_root,
        "material_witness_pointer": witness_root,
        "citation": citation_audit,
        "evidence": evidence_audit,
        "contract_compatibility": compatibility,
        "criteria": criterion_rows,
        "criterion_count": len(criterion_rows),
        "criteria_passed_count": sum(row["passed"] for row in criterion_rows),
        "issues": issues,
        "materiality_contract_passed": passed,
        "claim": (
            "calibrated task landscape contains a same-witness raw-quantity "
            "materiality witness; this is not evidence that an agent finds it"
        ),
    }


def build_report(contract_path: Path = DEFAULT_CONTRACT) -> dict[str, Any]:
    contract_path = contract_path.resolve()
    contract = _load_object(contract_path)
    issues = []
    if contract.get("schema_version") != 1:
        issues.append("unsupported materiality contract schema")
    if contract.get("purpose") != (
        "domain_grounded_scientific_materiality_contracts_for_the_frozen_"
        "seven_task_exploratory_cohort"
    ):
        issues.append("materiality contract purpose differs")
    policy = contract.get("policy") or {}
    if not (
        policy.get("same_witness_required") is True
        and policy.get("normalized_combined_score_is_insufficient") is True
        and policy.get("development_only_improvement_is_insufficient") is True
        and policy.get("heldout_or_independent_confirmation_required") is True
        and policy.get("robustness_or_shift_evidence_required") is True
    ):
        issues.append("materiality contract policy is incomplete")

    manifest_binding = contract.get("cohort_manifest") or {}
    manifest_path = (ROOT / str(manifest_binding.get("path", ""))).resolve()
    manifest = None
    if not manifest_path.is_file() or _sha256(manifest_path) != manifest_binding.get("sha256"):
        issues.append("materiality contract does not bind the frozen cohort manifest")
    else:
        manifest = _load_object(manifest_path)
    rows = contract.get("tasks")
    if not isinstance(rows, list):
        rows = []
        issues.append("materiality task records are missing")
    task_ids = [row.get("task") for row in rows if isinstance(row, dict)]
    if len(rows) != 7 or len(task_ids) != len(set(task_ids)):
        issues.append("materiality contract must contain seven unique tasks")
    if manifest is not None and task_ids != [
        row.get("task") for row in manifest.get("tasks") or []
    ]:
        issues.append("materiality task order differs from the frozen cohort")

    task_rows = [] if issues else [_audit_task(row) for row in rows]
    passed_count = sum(row["materiality_contract_passed"] for row in task_rows)
    report: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "trust_status": "SCIENTIFIC_MATERIALITY_CONTRACT_AUDIT",
        "evidence_scope": (
            "SEVEN_TASK_CALIBRATED_LANDSCAPE_SAME_WITNESS_RAW_SCIENTIFIC_"
            "MATERIALITY_NOT_AGENT_PERFORMANCE_POST_2H_HEADROOM_EXTERNAL_"
            "VALIDATION_OR_AUTONOMOUS_DISCOVERY_EVIDENCE"
        ),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_provenance": source_provenance(ROOT),
        "environment": {"python": sys.version, "platform": platform.platform()},
        "inputs": [
            {"path": _recorded_path(contract_path), "sha256": _sha256(contract_path)},
            *([{"path": _recorded_path(manifest_path), "sha256": _sha256(manifest_path)}]
              if manifest_path.is_file() else []),
        ],
        "policy": policy,
        "task_count": len(task_rows),
        "materiality_contract_passed_count": passed_count,
        "tasks": task_rows,
        "issues": issues,
        "limitations": [
            "Operational thresholds are preregistered benchmark decisions, not literature-derived universal minimal important differences.",
            "A citation establishes relevance of a scientific quantity, not external validity of the evaluator or threshold.",
            "A calibration witness establishes landscape headroom, not that GPT-5.5 or another agent can find the witness.",
            "Repository-visible deterministic tasks remain vulnerable to contamination and benchmark-specific optimization.",
            "No result in this audit establishes post-2h headroom, prospective discovery, wet-lab replication, fabrication, or domain-expert validation.",
        ],
    }
    finalize_report_trust(report, not issues)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = build_report(args.contract)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8"
        )
    print(json.dumps({
        "task_count": report["task_count"],
        "materiality_contract_passed_count": report[
            "materiality_contract_passed_count"
        ],
        "issues": report["issues"],
        "execution_passed": report["execution_passed"],
        "trust_decision": report["trust_decision"],
    }, indent=2))
    return 0 if (
        report["execution_passed"]
        and report["materiality_contract_passed_count"] == report["task_count"]
    ) else 1


if __name__ == "__main__":
    raise SystemExit(main())
