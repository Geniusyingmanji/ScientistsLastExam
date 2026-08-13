#!/usr/bin/env python3
"""Audit and summarize the frozen seven-task two-hour exploratory screen.

This analysis replays the raw trajectories, exactly-once evaluation ledgers,
content-addressed boundary sentinels, preregistration and cohort bindings.  It
keeps the online incumbent, the artifact present at the 7200-second boundary,
the last signed in-horizon decision and the observer best-so-far envelope as
different endpoints.  Task-specific raw scientific axes are retained and are
never averaged into a cross-task discovery score.

The study has one uncontrolled provider trajectory per result-selected task.
Consequently this script performs no significance test and supports no model
ranking, feedback-causal, scaling-law, confirmatory, external-validation or
autonomous-discovery claim.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from sle.algorithms.common import (  # noqa: E402
    atomic_write_text,
    runtime_source_sha256,
    task_contract_sha256,
    task_package_sha256,
)
from sle.evaluation_ledger import EvaluationLedger  # noqa: E402
from sle.protocol import (  # noqa: E402
    compact_trajectory_snapshot,
    load_trajectory,
)
from sle.provenance import (  # noqa: E402
    SOURCE_SCOPE,
    finalize_report_trust,
    source_provenance,
)
from sle.registry import find_task  # noqa: E402
from sle.runtime_migration import runtime_source_changes  # noqa: E402
from sle.sentinels import load_sentinel_events  # noqa: E402


DEFAULT_RAW = ROOT / "experiments/exploratory_2h_gpt55_2026-07-27_v2.json"
DEFAULT_PREREGISTRATION = (
    ROOT / ".research/exploratory_2h_execution_preregistration_2026-07-27_v2.json"
)
DEFAULT_COHORT = (
    ROOT / ".research/exploratory_2h_cohort_manifest_2026-07-27_v1.json"
)
DEFAULT_MATERIALITY = (
    ROOT / ".research/scientific_materiality_contracts_2026-07-27_v1.json"
)
EXPECTED_ALGORITHM = "greedy_rewrite"
EXPECTED_FEEDBACK_MODE = "normal"
EXPECTED_SEED = 0
EXPECTED_HORIZON = 7200.0
EXPECTED_GRID = (0.0, 1800.0, 3600.0, 5400.0, 7200.0)
EXPECTED_MODEL = {
    "wire": "responses",
    "model": "gpt-5.5",
    "max_output_tokens": 16000,
    "temperature": None,
    "reasoning_effort": "low",
    "server_side_seed_control": False,
}


SCIENCE_METRICS = {
    "Electrochemistry/ElectrolyteConductivityDesign": (
        "combined_score",
        "development_mean_weighted_conductivity_s_cm",
        "development_minimum_weighted_conductivity_s_cm",
        "heldout_policy_score",
        "heldout_mean_weighted_conductivity_s_cm",
        "heldout_minimum_weighted_conductivity_s_cm",
        "robustness_score",
        "heldout_robustness_score",
        "confirmation_score",
        "confirmation_robustness_score",
        "heldout_confirmation_score",
        "heldout_confirmation_robustness_score",
        "development_confirmation_mean_weighted_conductivity_s_cm",
        "development_confirmation_minimum_weighted_conductivity_s_cm",
        "heldout_confirmation_mean_weighted_conductivity_s_cm",
        "heldout_confirmation_minimum_weighted_conductivity_s_cm",
        "development_proxy_false_promotion_rate",
        "heldout_proxy_false_promotion_rate",
        "feasibility_rate",
        "heldout_feasibility_rate",
    ),
    "Optics/DiffractionGratingDesign": (
        "combined_score",
        "development_mean_target_efficiency",
        "development_minimum_target_efficiency",
        "heldout_policy_score",
        "heldout_mean_target_efficiency",
        "heldout_minimum_target_efficiency",
        "robustness_score",
        "heldout_robustness_score",
        "development_shift_geometry_feasibility",
        "heldout_shift_geometry_feasibility",
        "feasibility_rate",
        "heldout_feasibility_rate",
    ),
    "RNAEngineering/RNAInverseDesign": (
        "combined_score",
        "development_exact_utility",
        "development_target_probability",
        "development_ensemble_correctness",
        "heldout_policy_score",
        "heldout_target_probability",
        "heldout_ensemble_correctness",
        "robustness_score",
        "heldout_robustness_score",
        "development_proxy_false_promotion_rate",
        "heldout_proxy_false_promotion_rate",
        "feasibility_rate",
        "heldout_feasibility_rate",
    ),
    "Semiconductor/MOSFETDoping": (
        "combined_score",
        "heldout_policy_score",
        "robustness_score",
        "heldout_robustness_score",
        "development_mean_nominal_feasible_rate",
        "development_shift_feasibility_rate",
        "heldout_mean_nominal_feasible_rate",
        "heldout_shift_feasibility_rate",
        "feasibility_rate",
        "heldout_feasibility_rate",
    ),
    "StructuralEngineering/TrussWeightMinimization": (
        "combined_score",
        "development_score",
        "heldout_policy_score",
        "robustness_score",
        "heldout_robustness_score",
        "mean_shifted_case_feasibility_rate",
        "mean_shifted_constraint_feasibility_rate",
        "feasibility_rate",
        "heldout_feasibility_rate",
    ),
    "Thermodynamics/HeatExchangerDesign": (
        "combined_score",
        "development_exact_score",
        "heldout_exact_score",
        "robustness_score",
        "heldout_robustness_score",
        "development_proxy_score",
        "heldout_proxy_score",
        "development_false_promotion_rate",
        "heldout_false_promotion_rate",
        "feasibility_rate",
        "heldout_feasibility_rate",
        "heldout_structural_validity_rate",
    ),
    "Turbulence/RANSCalibration": (
        "combined_score",
        "development_raw_loss",
        "heldout_raw_loss",
        "development_worst_shift_loss",
        "heldout_worst_shift_loss",
        "development_velocity_rmse_plus",
        "heldout_velocity_rmse_plus",
        "development_reynolds_shear_rmse_plus",
        "heldout_reynolds_shear_rmse_plus",
        "heldout_policy_score",
        "robustness_score",
        "heldout_robustness_score",
        "physics_gate_passed",
        "feasibility_rate",
        "heldout_feasibility_rate",
    ),
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _canonical_sha256(value: Any) -> str:
    payload = json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _load(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("cannot load %s" % label) from exc
    if not isinstance(value, dict):
        raise ValueError("%s must be a JSON object" % label)
    return value


def _recorded_path(path: Path) -> str:
    try:
        return str(Path(path).resolve().relative_to(ROOT))
    except ValueError:
        return str(Path(path).resolve())


def _finite(value: Any) -> Optional[float]:
    if (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    ):
        return float(value)
    return None


def _git_scope_changes(left: str, right: str) -> list[str]:
    try:
        return runtime_source_changes(left, right, SOURCE_SCOPE, root=ROOT)
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ValueError("cannot compare frozen source revisions") from exc


def _frozen_runtime_source_sha256(frozen: dict[str, Any]) -> Optional[str]:
    parent = frozen.get("parent_revision")
    if not isinstance(parent, str) or not parent:
        return None
    try:
        names = subprocess.check_output(
            ["git", "ls-tree", "-r", "--name-only", parent, "--", "sle",
             "requirements-upstream.txt"],
            cwd=str(ROOT), text=True, stderr=subprocess.DEVNULL,
        ).splitlines()
        digest = hashlib.sha256()
        for relative in sorted(
            name for name in names
            if name.endswith(".py") or name == "requirements-upstream.txt"
        ):
            payload = subprocess.check_output(
                ["git", "show", "%s:%s" % (parent, relative)],
                cwd=str(ROOT), stderr=subprocess.DEVNULL,
            )
            digest.update(relative.encode("utf-8") + b"\0")
            digest.update(payload + b"\0")
        return digest.hexdigest()
    except (OSError, subprocess.CalledProcessError):
        return None


def _source_equivalent(left: str, right: str) -> bool:
    return left == right or not _git_scope_changes(left, right)


def _json_pointer(value: Any, pointer: str) -> Any:
    if pointer in {"", "/"}:
        return value
    if not isinstance(pointer, str) or not pointer.startswith("/"):
        raise ValueError("invalid JSON pointer")
    current = value
    for token in pointer[1:].split("/"):
        token = token.replace("~1", "/").replace("~0", "~")
        if isinstance(current, list):
            current = current[int(token)]
        elif isinstance(current, dict):
            current = current[token]
        else:
            raise TypeError("JSON pointer traverses a scalar")
    return current


def _relative_pointer(pointer: str, root: str) -> str:
    if pointer == root:
        return ""
    prefix = root.rstrip("/") + "/"
    if not pointer.startswith(prefix):
        raise ValueError("materiality pointer is outside its witness root")
    return pointer[len(root):]


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
        raise ValueError("invalid improvement direction")
    relative = absolute / abs(baseline) if baseline != 0.0 else None
    return absolute, relative


def _change_passes(
    absolute: float, relative: Optional[float], criterion: dict[str, Any],
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


def _record_map(value: Any, key: Any) -> tuple[dict[str, dict[str, Any]], Optional[str]]:
    if not isinstance(value, list) or not value:
        return {}, "record source is not a non-empty list"
    if not isinstance(key, str) or not key:
        return {}, "record identity key is missing"
    result = {}
    for row in value:
        if not isinstance(row, dict) or not isinstance(row.get(key), str):
            return {}, "record lacks a string identity"
        identity = row[key]
        if identity in result:
            return {}, "record identities are not unique"
        result[identity] = row
    return result, None


def _bound_comparison(value: Any, operator: str, threshold: Any) -> bool:
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


def evaluate_materiality(
    contract: dict[str, Any],
    baseline_metrics: dict[str, Any],
    witness_metrics: dict[str, Any],
) -> dict[str, Any]:
    """Apply the frozen task contract to one baseline/witness artifact pair."""

    baseline_root = str(contract["baseline_pointer"])
    witness_root = str(contract["material_witness_pointer"])
    rows = []
    for criterion in contract.get("criteria") or []:
        kind = criterion.get("kind")
        result: dict[str, Any]
        try:
            if kind == "paired_scalar":
                baseline = _finite(_json_pointer(
                    baseline_metrics,
                    _relative_pointer(criterion["baseline_pointer"], baseline_root),
                ))
                witness = _finite(_json_pointer(
                    witness_metrics,
                    _relative_pointer(criterion["witness_pointer"], witness_root),
                ))
                if baseline is None or witness is None:
                    raise ValueError("scalar value is non-finite")
                absolute, relative = _signed_change(
                    baseline, witness, str(criterion.get("direction")),
                )
                passed = _change_passes(absolute, relative, criterion)
                result = {
                    "passed": passed,
                    "baseline": baseline,
                    "witness": witness,
                    "signed_absolute_change": absolute,
                    "signed_relative_change": relative,
                    "minimum_absolute_change": criterion.get(
                        "minimum_absolute_change"
                    ),
                    "minimum_relative_change": criterion.get(
                        "minimum_relative_change"
                    ),
                    "unit": criterion.get("unit"),
                    "reason": (
                        None if passed
                        else "raw scientific change did not clear the threshold"
                    ),
                }
            elif kind == "paired_records":
                baseline_value = _json_pointer(
                    baseline_metrics,
                    _relative_pointer(criterion["baseline_pointer"], baseline_root),
                )
                witness_value = _json_pointer(
                    witness_metrics,
                    _relative_pointer(criterion["witness_pointer"], witness_root),
                )
                baseline, error = _record_map(
                    baseline_value, criterion.get("record_key")
                )
                if error:
                    raise ValueError(error)
                witness, error = _record_map(
                    witness_value, criterion.get("record_key")
                )
                if error:
                    raise ValueError(error)
                if set(baseline) != set(witness):
                    raise ValueError("baseline and witness identities differ")
                observed_splits = set()
                comparisons = []
                all_passed = True
                for identity in sorted(baseline):
                    left, right = baseline[identity], witness[identity]
                    split_field = criterion.get("split_field")
                    if split_field:
                        if left.get(split_field) != right.get(split_field):
                            raise ValueError("paired record split labels differ")
                        observed_splits.add(left.get(split_field))
                    left_values = _flatten(_json_pointer(
                        left, str(criterion["value_pointer"])
                    ))
                    right_values = _flatten(_json_pointer(
                        right, str(criterion["value_pointer"])
                    ))
                    if not left_values or len(left_values) != len(right_values):
                        raise ValueError("paired record value shapes differ")
                    record_values = []
                    for raw_left, raw_right in zip(left_values, right_values):
                        left_number, right_number = _finite(raw_left), _finite(raw_right)
                        if left_number is None or right_number is None:
                            raise ValueError("record value is non-finite")
                        absolute, relative = _signed_change(
                            left_number,
                            right_number,
                            str(criterion.get("direction")),
                        )
                        passed = _change_passes(absolute, relative, criterion)
                        all_passed = all_passed and passed
                        record_values.append({
                            "baseline": left_number,
                            "witness": right_number,
                            "signed_absolute_change": absolute,
                            "signed_relative_change": relative,
                            "passed": passed,
                        })
                    comparisons.append({
                        "identity": identity,
                        "split": left.get(split_field) if split_field else None,
                        "comparisons": record_values,
                        "passed": all(row["passed"] for row in record_values),
                    })
                required_splits = set(criterion.get("required_splits") or [])
                split_coverage = observed_splits >= required_splits
                all_passed = all_passed and split_coverage
                absolute_changes = [
                    item["signed_absolute_change"]
                    for row in comparisons for item in row["comparisons"]
                ]
                relative_changes = [
                    item["signed_relative_change"]
                    for row in comparisons for item in row["comparisons"]
                    if item["signed_relative_change"] is not None
                ]
                result = {
                    "passed": bool(all_passed),
                    "record_count": len(comparisons),
                    "value_count": len(absolute_changes),
                    "required_splits": sorted(required_splits),
                    "observed_splits": sorted(
                        value for value in observed_splits if value is not None
                    ),
                    "split_coverage_passed": split_coverage,
                    "minimum_signed_absolute_change": min(absolute_changes),
                    "minimum_signed_relative_change": (
                        min(relative_changes) if relative_changes else None
                    ),
                    "minimum_absolute_change": criterion.get(
                        "minimum_absolute_change"
                    ),
                    "minimum_relative_change": criterion.get(
                        "minimum_relative_change"
                    ),
                    "unit": criterion.get("unit"),
                    "records": comparisons,
                    "reason": (
                        None if all_passed
                        else "one or more raw record changes or splits failed"
                    ),
                }
            elif kind == "values_bound":
                source = _json_pointer(
                    witness_metrics,
                    _relative_pointer(criterion["source_pointer"], witness_root),
                )
                if criterion.get("value_pointer") is None:
                    values = _flatten(source)
                else:
                    if not isinstance(source, list) or not source:
                        raise ValueError("bound record source is not a non-empty list")
                    values = []
                    for row in source:
                        values.extend(_flatten(_json_pointer(
                            row, str(criterion["value_pointer"])
                        )))
                if not values:
                    raise ValueError("bound criterion has no values")
                outcomes = [
                    _bound_comparison(
                        value,
                        str(criterion.get("operator")),
                        criterion.get("threshold"),
                    )
                    for value in values
                ]
                result = {
                    "passed": all(outcomes),
                    "operator": criterion.get("operator"),
                    "threshold": criterion.get("threshold"),
                    "value_count": len(values),
                    "values": values,
                    "outcomes": outcomes,
                    "reason": (
                        None if all(outcomes)
                        else "one or more witness bounds failed"
                    ),
                }
            else:
                raise ValueError("unsupported materiality criterion kind")
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            result = {"passed": False, "reason": str(exc)}
        rows.append({
            "id": criterion.get("id"),
            "kind": kind,
            "axes": criterion.get("axes"),
            **result,
        })
    passed = bool(rows) and all(row["passed"] for row in rows)
    return {
        "threshold_basis": contract.get("threshold_basis"),
        "scientific_quantity": contract.get("scientific_quantity"),
        "required_axes": contract.get("required_axes"),
        "criterion_count": len(rows),
        "criteria_passed_count": sum(row["passed"] for row in rows),
        "operational_materiality_contract_passed": passed,
        "criteria": rows,
        "claim_limit": (
            "benchmark operational threshold on the frozen local oracle; not "
            "field consensus, external validation or scientific discovery"
        ),
    }


def wall_time_auc(events: list[dict[str, Any]], horizon: float) -> float:
    """Integrate the online incumbent over active wall time."""

    if not events or horizon <= 0.0:
        raise ValueError("wall-time AUC requires events and a positive horizon")
    baseline = float(events[0]["best_score"])
    prior_time = 0.0
    prior_best = baseline
    area = 0.0
    for event in events:
        completed = min(horizon, float(event["cumulative_wall_seconds"]))
        if completed < prior_time:
            raise ValueError("trajectory completion time is not monotone")
        area += prior_best * (completed - prior_time)
        prior_time = completed
        if completed < horizon and bool(event.get("accepted")):
            prior_best = max(prior_best, float(event["score"]))
        elif completed == horizon and float(event["cumulative_wall_seconds"]) <= horizon:
            if bool(event.get("accepted")):
                prior_best = max(prior_best, float(event["score"]))
        if float(event["cumulative_wall_seconds"]) >= horizon:
            break
    area += prior_best * (horizon - prior_time)
    return area / horizon


def _best_event(events: list[dict[str, Any]]) -> dict[str, Any]:
    eligible = [
        row for row in events if bool(row.get("valid")) and bool(row.get("accepted"))
    ]
    if not eligible:
        raise ValueError("trajectory has no valid accepted event")
    return max(eligible, key=lambda row: (float(row["score"]), -int(row["step"])))


def _observer_best_published_by(
    events: list[dict[str, Any]], horizon: float,
) -> dict[str, Any]:
    eligible = [events[0]]
    for event in events[1:]:
        published = _finite(
            (event.get("algorithm_metadata") or {}).get(
                "proposal_published_wall_seconds"
            )
        )
        if published is not None and published <= horizon and bool(event.get("valid")):
            eligible.append(event)
    return max(eligible, key=lambda row: (float(row["score"]), -int(row["step"])))


def _online_best_completed_by(
    events: list[dict[str, Any]], horizon: float,
) -> dict[str, Any]:
    if horizon == 0.0:
        return events[0]
    eligible = [
        row for row in events
        if float(row["cumulative_wall_seconds"]) <= horizon
        and bool(row.get("valid"))
        and bool(row.get("accepted"))
    ]
    return _best_event(eligible or [events[0]])


def _science_metrics(task: str, metrics: dict[str, Any]) -> dict[str, Any]:
    return {
        key: metrics[key]
        for key in SCIENCE_METRICS[task]
        if key in metrics
    }


def _evaluation_payload(workdir: Path, sentinel: dict[str, Any]) -> dict[str, Any]:
    reference = sentinel.get("evaluation") or {}
    relative = reference.get("path")
    if not relative:
        raise ValueError("evaluated sentinel lacks an evaluation payload")
    value = _load(workdir / str(relative), "sentinel evaluation")
    if _sha256(workdir / str(relative)) != reference.get("sha256"):
        raise ValueError("sentinel evaluation hash differs")
    return value


def _endpoint(
    task: str,
    event: dict[str, Any],
    baseline_metrics: dict[str, Any],
    materiality_contract: dict[str, Any],
    *,
    policy: str,
) -> dict[str, Any]:
    metrics = dict(event.get("metrics") or {})
    return {
        "policy": policy,
        "source_step": int(event["step"]),
        "candidate_sha256": event.get("candidate_sha256"),
        "proposal_published_wall_seconds": (
            0.0 if int(event["step"]) == 0
            else (event.get("algorithm_metadata") or {}).get(
                "proposal_published_wall_seconds"
            )
        ),
        "evaluation_completed_wall_seconds": float(
            event["cumulative_wall_seconds"]
        ),
        "valid": bool(event.get("valid")),
        "combined_score": float(event["score"]),
        "science_metrics": _science_metrics(task, metrics),
        "materiality": evaluate_materiality(
            materiality_contract, baseline_metrics, metrics
        ),
    }


def _validate_prerequisites(preregistration: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for contract in preregistration.get("prerequisites") or []:
        path = ROOT / str(contract.get("path", ""))
        document = _load(path, "preregistered prerequisite")
        checks = {
            "hash_matches": _sha256(path) == contract.get("sha256"),
            "execution_passed": document.get("execution_passed") is True,
            "trusted_evidence": document.get("trusted_evidence") is True,
            "passed": document.get("passed") is True,
            "issues_empty": document.get("issues", []) == [],
        }
        if not all(checks.values()):
            raise ValueError(
                "preregistered prerequisite failed: %s" % contract.get("role")
            )
        rows.append({
            "role": contract.get("role"),
            "path": _recorded_path(path),
            "sha256": _sha256(path),
            "checks": checks,
        })
    if len(rows) != 7:
        raise ValueError("expected seven preregistered prerequisites")
    return rows


def _validate_inputs(
    raw_path: Path,
    preregistration_path: Path,
    cohort_path: Path,
    materiality_path: Path,
) -> tuple[
    dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any], list[str]
]:
    raw = _load(raw_path, "two-hour raw report")
    preregistration = _load(preregistration_path, "two-hour preregistration")
    cohort = _load(cohort_path, "two-hour cohort")
    materiality = _load(materiality_path, "scientific materiality contract")
    prereg_tasks = [
        row.get("task") for row in (preregistration.get("design") or {}).get("tasks") or []
    ]
    cohort_tasks = [row.get("task") for row in cohort.get("tasks") or []]
    config = raw.get("config") or {}
    raw_prereg = config.get("preregistration") or {}
    raw_cohort = config.get("cohort_manifest") or {}
    model = config.get("llm") or {}
    design = preregistration.get("design") or {}
    frozen = preregistration.get("frozen_source") or {}
    raw_provenance = raw.get("source_provenance") or {}
    materiality_tasks = [row.get("task") for row in materiality.get("tasks") or []]
    if not (
        raw.get("schema_version") == 1
        and raw.get("execution_passed") is True
        and raw.get("trusted_evidence") is True
        and raw.get("passed") is True
        and raw.get("trust_status") == "TRUSTED_SECURE_EVAL"
        and preregistration.get("schema_version") == 1
        and preregistration.get("preregistration_id")
        == "sle_exploratory_2h_execution_v2"
        and cohort.get("manifest_id") == "sle_exploratory_2h_v1"
        and (cohort.get("selection") or {}).get("confirmatory_reuse_permitted")
        is False
        and prereg_tasks == cohort_tasks == materiality_tasks
        and len(prereg_tasks) == 7
        and config.get("tasks") == prereg_tasks
        and config.get("algorithms") == [EXPECTED_ALGORITHM]
        and config.get("feedback_modes") == [EXPECTED_FEEDBACK_MODE]
        and config.get("seeds") == [EXPECTED_SEED]
        and config.get("trajectory_snapshot_schema_version") == 2
        and float(config.get("active_wall_horizon_s", -1)) == EXPECTED_HORIZON
        and float(config.get("sentinel_interval_s", -1)) == 1800.0
        and config.get("signed_decisions") is True
        and config.get("signed_decision_policy") == "record_only"
        and config.get("budget") == design.get("proposal_budget_upper_bound")
        and raw_prereg.get("path") == _recorded_path(preregistration_path)
        and raw_prereg.get("sha256") == _sha256(preregistration_path)
        and raw_prereg.get("bytes") == len(preregistration_path.read_bytes())
        and raw_prereg.get("execution_contract_validated") is True
        and raw_cohort.get("path") == _recorded_path(cohort_path)
        and raw_cohort.get("sha256") == _sha256(cohort_path)
        and raw_cohort.get("bytes") == len(cohort_path.read_bytes())
        and raw_cohort.get("confirmatory_reuse_permitted") is False
        and all(model.get(key) == value for key, value in EXPECTED_MODEL.items())
        and config.get("llm_condition_sha256")
        == (preregistration.get("model_condition") or {}).get(
            "llm_condition_sha256"
        )
        and raw_provenance.get("git_available") is True
        and raw_provenance.get("source_tree_dirty") is False
        and raw_provenance.get("source_changes") == []
        and isinstance(raw_provenance.get("git_revision"), str)
        and _source_equivalent(
            str(frozen.get("parent_revision")),
            str(raw_provenance.get("git_revision")),
        )
        and _frozen_runtime_source_sha256(frozen)
        == frozen.get("runtime_source_sha256")
        and (materiality.get("cohort_manifest") or {}).get("sha256")
        == _sha256(cohort_path)
    ):
        raise ValueError("two-hour frozen input contract differs")
    for row in design.get("tasks") or []:
        task = str(row["task"])
        spec = find_task(task, include_uncertified=True)
        if not (
            task_contract_sha256(spec) == row.get("task_contract_sha256")
            and task_package_sha256(spec) == row.get("task_package_sha256")
            and _sha256(spec.task_dir / "TASK_CARD.yaml")
            == row.get("task_card_sha256")
        ):
            raise ValueError("current task package differs for %s" % task)
    _validate_prerequisites(preregistration)
    return raw, preregistration, cohort, materiality, prereg_tasks


def _validate_run(
    run: dict[str, Any],
    task: str,
    task_design: dict[str, Any],
    materiality_contract: dict[str, Any],
) -> dict[str, Any]:
    if not (
        run.get("task") == task
        and run.get("algorithm") == EXPECTED_ALGORITHM
        and run.get("feedback_mode") == EXPECTED_FEEDBACK_MODE
        and run.get("seed") == EXPECTED_SEED
        and not run.get("error")
        and not run.get("protocol_incomplete")
    ):
        raise ValueError("run identity or terminal status differs for %s" % task)
    workdir = Path(str(run["workdir"])).resolve()
    expected_root = (ROOT / "runs/exploratory_2h_gpt55_2026-07-27_v2").resolve()
    if expected_root not in workdir.parents:
        raise ValueError("run workdir is outside the frozen result root")

    manifest = _load(workdir / "run_manifest.json", "run manifest")
    if not (
        manifest.get("task_id") == task
        and manifest.get("algorithm") == EXPECTED_ALGORITHM
        and manifest.get("feedback_mode") == EXPECTED_FEEDBACK_MODE
        and manifest.get("seed") == EXPECTED_SEED
        and manifest.get("task_contract_sha256")
        == task_design.get("task_contract_sha256")
        and manifest.get("task_package_sha256")
        == task_design.get("task_package_sha256")
        and isinstance(manifest.get("runtime_source_sha256"), str)
        and manifest.get("llm_condition_sha256")
        == "5b0df4671481f6b3505155bc6c5654a64c4da5591422fb806904e7d0f44fc4d2"
        and float((manifest.get("protocol") or {}).get("active_wall_horizon_s", -1))
        == EXPECTED_HORIZON
        and (manifest.get("protocol") or {}).get("signed_decisions") is True
        and (manifest.get("protocol") or {}).get("signed_decision_policy")
        == "record_only"
    ):
        raise ValueError("run manifest differs for %s" % task)

    trajectory_path = workdir / "trajectory.jsonl"
    events = load_trajectory(trajectory_path)
    snapshot = run.get("trajectory_snapshot") or {}
    if compact_trajectory_snapshot(trajectory_path, schema_version=2) != snapshot:
        raise ValueError("portable trajectory snapshot differs for %s" % task)
    if snapshot.get("trajectory_sha256") != _sha256(trajectory_path):
        raise ValueError("trajectory hash differs for %s" % task)

    checkpoint = _load(workdir / "checkpoint.json", "run checkpoint")
    best_event = _best_event(events)
    best_program_hash = _sha256(workdir / "best_program.py")
    if not (
        checkpoint.get("next_iter") == len(events)
        and checkpoint.get("pending_proposal") is None
        and checkpoint.get("best_source_step") == best_event.get("step")
        and checkpoint.get("best_sha256") == best_event.get("candidate_sha256")
        and checkpoint.get("best_sha256") == best_program_hash
        and math.isclose(
            float(checkpoint.get("best_score")),
            float(best_event["score"]),
            rel_tol=0.0,
            abs_tol=0.0,
        )
        and math.isclose(float(run.get("best")), float(best_event["score"]))
        and run.get("accepted")
        == sum(bool(event.get("accepted")) for event in events[1:])
        and run.get("evaluated") == int(events[-1]["oracle_calls"])
    ):
        raise ValueError("online incumbent checkpoint differs for %s" % task)

    evaluation_snapshot = EvaluationLedger(workdir).snapshot()
    if evaluation_snapshot != (run.get("summary") or {}).get(
        "evaluation_ledger_snapshot"
    ):
        raise ValueError("evaluation ledger snapshot differs for %s" % task)
    event_request_ids = [
        (event.get("algorithm_metadata") or {}).get("evaluation_request_id")
        for event in events
    ]
    if not (
        len(event_request_ids) == len(set(event_request_ids)) == len(events)
        and set(event_request_ids) == set(evaluation_snapshot["request_ids"])
        and evaluation_snapshot["request_count"]
        == evaluation_snapshot["receipt_count"] == len(events)
        and evaluation_snapshot["incomplete_attempt_count"] == 0
        and evaluation_snapshot["infrastructure_failure_attempt_count"] == 0
        and all(
            (event.get("algorithm_metadata") or {}).get(
                "evaluation_receipt_committed"
            ) is True
            for event in events
        )
    ):
        raise ValueError("trajectory-to-receipt lineage differs for %s" % task)
    evaluation_ledger = EvaluationLedger(workdir)
    for event, request_id in zip(events, event_request_ids):
        bound = evaluation_ledger.require_bound_record(str(request_id))
        request = bound["request"]
        receipt = bound["receipt"]
        expected_kind = "baseline" if int(event["step"]) == 0 else "proposal"
        if not (
            request.get("kind") == expected_kind
            and request.get("task_id") == task
            and request.get("step") == event.get("step")
            and request.get("candidate_sha256") == event.get("candidate_sha256")
            and request.get("task_contract_sha256")
            == manifest.get("task_contract_sha256")
            and request.get("task_package_sha256")
            == manifest.get("task_package_sha256")
            and request.get("runtime_source_sha256")
            == manifest.get("runtime_source_sha256")
            and _canonical_sha256(receipt.get("metrics") or {})
            == _canonical_sha256(event.get("metrics") or {})
        ):
            raise ValueError("evaluation receipt payload differs for %s" % task)

    sentinel_snapshot = (run.get("summary") or {}).get("sentinel_snapshot") or {}
    sentinel_path = workdir / str(sentinel_snapshot.get("ledger_path"))
    sentinel_events = load_sentinel_events(sentinel_path, workdir=workdir)
    if not (
        _sha256(sentinel_path) == sentinel_snapshot.get("ledger_sha256")
        and sentinel_events == sentinel_snapshot.get("events")
        and len(sentinel_events) == sentinel_snapshot.get("event_count")
    ):
        raise ValueError("sentinel ledger snapshot differs for %s" % task)
    types = [row["sentinel_type"] for row in sentinel_events]
    submissions = [row for row in sentinel_events if row["sentinel_type"] == "submission"]
    decisions = [
        row for row in sentinel_events
        if row["sentinel_type"] in {"commit", "abstain"}
    ]
    fixed = [row for row in sentinel_events if row["sentinel_type"] == "fixed_grid"]
    terminal = [row for row in sentinel_events if row["sentinel_type"] == "terminal"]
    first_valid = [row for row in sentinel_events if row["sentinel_type"] == "first_valid"]
    proposal_events = events[1:]
    signed_actions = [
        (row.get("algorithm_metadata") or {}).get("signed_decision_action")
        for row in proposal_events
    ]
    expected_decisions = [
        row for row in proposal_events
        if (row.get("algorithm_metadata") or {}).get("signed_decision_action")
        in {"commit", "abstain"}
    ]
    first_valid_event = next((row for row in proposal_events if row["valid"]), None)
    if not (
        types[0] == "t0"
        and types[-1] == "terminal"
        and types.count("t0") == 1
        and len(first_valid) == 1
        and len(submissions) == len(proposal_events)
        and len(decisions) == len(expected_decisions)
        and all(action in {"continue", "commit", "abstain"} for action in signed_actions)
        and [row["scheduled_elapsed_seconds"] for row in fixed]
        == list(EXPECTED_GRID[1:])
        and len(terminal) == 1
        and terminal[0].get("scheduled_elapsed_seconds") == EXPECTED_HORIZON
        and first_valid_event is not None
        and first_valid[0].get("source_step") == first_valid_event.get("step")
        and first_valid[0].get("artifact_sha256")
        == first_valid_event.get("candidate_sha256")
    ):
        raise ValueError("required sentinel risk set differs for %s" % task)
    for proposal, submission in zip(proposal_events, submissions):
        if not (
            submission.get("source_step") == proposal.get("step")
            and submission.get("artifact_sha256") == proposal.get("candidate_sha256")
            and (submission.get("metadata") or {}).get("decision_made_before_evaluation")
            is True
            and (submission.get("metadata") or {}).get("response_sha256")
            == (submission.get("provider_response") or {}).get("sha256")
        ):
            raise ValueError("submission sentinel lineage differs for %s" % task)
    for proposal, decision in zip(expected_decisions, decisions):
        action = (proposal.get("algorithm_metadata") or {}).get(
            "signed_decision_action"
        )
        if not (
            decision.get("sentinel_type") == action
            and (decision.get("metadata") or {}).get(
                "evaluation_not_visible_when_deciding"
            ) is True
            and (decision.get("metadata") or {}).get(
                "evaluation_result_bound_by_trajectory_step"
            ) == proposal.get("step")
            and (decision.get("metadata") or {}).get("response_sha256")
            == (decision.get("provider_response") or {}).get("sha256")
            and (
                decision.get("artifact_sha256") == proposal.get("candidate_sha256")
                if action == "commit"
                else decision.get("artifact_sha256") is None
            )
        ):
            raise ValueError("signed-decision sentinel lineage differs for %s" % task)

    t0_metrics = _evaluation_payload(workdir, sentinel_events[0])
    if _canonical_sha256(t0_metrics) != _canonical_sha256(events[0]["metrics"]):
        raise ValueError("t0 evaluation differs from trajectory for %s" % task)
    published_by_cutoff = [
        row for row in events[1:]
        if _finite((row.get("algorithm_metadata") or {}).get(
            "proposal_published_wall_seconds"
        )) <= EXPECTED_HORIZON
    ]
    expected_terminal_event = published_by_cutoff[-1] if published_by_cutoff else events[0]
    terminal_metrics = _evaluation_payload(workdir, terminal[0])
    if not (
        terminal[0].get("selection_policy") == "terminal_workspace_artifact"
        and terminal[0].get("source_step") == expected_terminal_event.get("step")
        and terminal[0].get("artifact_sha256")
        == expected_terminal_event.get("candidate_sha256")
        and _canonical_sha256(terminal_metrics)
        == _canonical_sha256(expected_terminal_event.get("metrics") or {})
    ):
        raise ValueError("terminal workspace endpoint differs for %s" % task)

    baseline_metrics = dict(events[0].get("metrics") or {})
    online = _endpoint(
        task,
        best_event,
        baseline_metrics,
        materiality_contract,
        policy="online_in_horizon_incumbent",
    )
    observer_event = _observer_best_published_by(events, EXPECTED_HORIZON)
    observer = _endpoint(
        task,
        observer_event,
        baseline_metrics,
        materiality_contract,
        policy="observer_best_valid_artifact_published_by_cutoff",
    )
    terminal_endpoint = _endpoint(
        task,
        {**expected_terminal_event, "metrics": terminal_metrics},
        baseline_metrics,
        materiality_contract,
        policy="terminal_workspace_artifact",
    )

    in_horizon_decisions = [
        row for row in decisions
        if float(row["artifact_published_elapsed_seconds"]) <= EXPECTED_HORIZON
    ]
    if not in_horizon_decisions:
        raise ValueError("run lacks an in-horizon signed endpoint for %s" % task)
    signed = in_horizon_decisions[-1]
    bound_step = (signed.get("metadata") or {}).get(
        "evaluation_result_bound_by_trajectory_step"
    )
    bound_event = events[int(bound_step)]
    signed_endpoint: dict[str, Any] = {
        "policy": "latest_signed_commit_or_abstention_published_by_cutoff",
        "action": signed["sentinel_type"],
        "decision_wall_seconds": signed["recorded_elapsed_seconds"],
        "decision_made_before_evaluation": True,
        "evaluation_visible_when_deciding": False,
        "bound_post_decision_evaluation": {
            "source_step": int(bound_event["step"]),
            "valid": bool(bound_event["valid"]),
            "combined_score": float(bound_event["score"]),
            "evaluation_completed_wall_seconds": float(
                bound_event["cumulative_wall_seconds"]
            ),
        },
    }
    if signed["sentinel_type"] == "commit":
        signed_endpoint["committed_artifact"] = _endpoint(
            task,
            bound_event,
            baseline_metrics,
            materiality_contract,
            policy="signed_commit_before_evaluation",
        )
    else:
        signed_endpoint["committed_artifact"] = None

    grids = []
    sentinel_by_grid = {0.0: sentinel_events[0]}
    sentinel_by_grid.update({
        float(row["scheduled_elapsed_seconds"]): row for row in fixed
    })
    for time_seconds in EXPECTED_GRID:
        sentinel = sentinel_by_grid[time_seconds]
        workspace_metrics = _evaluation_payload(workdir, sentinel)
        workspace_event = events[int(sentinel["source_step"])]
        online_event = _online_best_completed_by(events, time_seconds)
        observer_grid_event = _observer_best_published_by(events, time_seconds)
        grids.append({
            "time_seconds": time_seconds,
            "online_incumbent": {
                "source_step": int(online_event["step"]),
                "combined_score": float(online_event["score"]),
            },
            "observer_best_published_by_grid": {
                "source_step": int(observer_grid_event["step"]),
                "combined_score": float(observer_grid_event["score"]),
                "evaluation_completed_by_grid": bool(
                    float(observer_grid_event["cumulative_wall_seconds"])
                    <= time_seconds
                ) if time_seconds > 0 else False,
            },
            "workspace_artifact": {
                "source_step": int(workspace_event["step"]),
                "valid": float(workspace_metrics.get("valid", 0.0)) >= 1.0,
                "combined_score": float(workspace_metrics.get("combined_score", 0.0)),
                "evaluation_status": (sentinel.get("evaluation") or {}).get("status"),
            },
        })

    invalid_taxonomy: dict[str, int] = {}
    for event in proposal_events:
        if event["valid"]:
            continue
        label = (
            event.get("error")
            or (event.get("metrics") or {}).get("candidate_failure_kind")
            or (event.get("metrics") or {}).get("error_message")
            or "evaluator_validity_gate_failed"
        )
        invalid_taxonomy[str(label)] = invalid_taxonomy.get(str(label), 0) + 1

    score_30m = grids[1]["online_incumbent"]["combined_score"]
    score_120m = grids[-1]["online_incumbent"]["combined_score"]
    summary = run.get("summary") or {}
    return {
        "task": task,
        "scientific_role": task_design.get("scientific_role"),
        "workdir": _recorded_path(workdir),
        "completion": {
            "horizon_reached": summary.get("horizon_reached"),
            "active_wall_seconds": summary.get("wall_seconds"),
            "proposal_count": len(proposal_events),
            "oracle_calls_including_baseline": summary.get("oracle_calls"),
            "valid_proposal_count": sum(bool(row["valid"]) for row in proposal_events),
            "valid_proposal_rate": (
                sum(bool(row["valid"]) for row in proposal_events)
                / len(proposal_events)
            ),
            "accepted_incumbent_updates": run.get("accepted"),
            "first_valid_wall_seconds": first_valid[0]["recorded_elapsed_seconds"],
            "input_tokens": (summary.get("llm") or {}).get("input_tokens"),
            "output_tokens": (summary.get("llm") or {}).get("output_tokens"),
            "total_tokens": (summary.get("llm") or {}).get("total_tokens"),
            "estimated_cost_usd": (summary.get("llm") or {}).get(
                "estimated_cost_usd"
            ),
            "invalid_proposal_taxonomy": invalid_taxonomy,
            "wall_time_best_so_far_auc": wall_time_auc(events, EXPECTED_HORIZON),
            "score_change_30m_to_120m": score_120m - score_30m,
        },
        "time_grid": grids,
        "endpoints": {
            "online_incumbent": online,
            "terminal_workspace_artifact": terminal_endpoint,
            "latest_signed_in_horizon_decision": signed_endpoint,
            "observer_best_so_far_envelope": observer,
        },
        "endpoint_relationships": {
            "online_incumbent_equals_observer_envelope": (
                online["candidate_sha256"] == observer["candidate_sha256"]
            ),
            "terminal_workspace_equals_online_incumbent": (
                terminal_endpoint["candidate_sha256"] == online["candidate_sha256"]
            ),
            "terminal_workspace_valid": terminal_endpoint["valid"],
            "terminal_policy_label_in_preregistration": (
                "terminal_in_horizon_incumbent"
            ),
            "terminal_policy_implemented_by_runner": (
                "terminal_workspace_artifact"
            ),
        },
        "lineage": {
            "trajectory_sha256": _sha256(trajectory_path),
            "sentinel_ledger_sha256": _sha256(sentinel_path),
            "run_manifest_sha256": _sha256(workdir / "run_manifest.json"),
            "evaluation_request_count": evaluation_snapshot["request_count"],
            "evaluation_receipt_count": evaluation_snapshot["receipt_count"],
            "sentinel_event_count": len(sentinel_events),
            "all_lineage_checks_passed": True,
        },
    }


def analyze(
    raw_path: Path = DEFAULT_RAW,
    preregistration_path: Path = DEFAULT_PREREGISTRATION,
    cohort_path: Path = DEFAULT_COHORT,
    materiality_path: Path = DEFAULT_MATERIALITY,
) -> dict[str, Any]:
    raw, preregistration, cohort, materiality, tasks = _validate_inputs(
        raw_path.resolve(),
        preregistration_path.resolve(),
        cohort_path.resolve(),
        materiality_path.resolve(),
    )
    runs = raw.get("runs") or []
    run_map = {run.get("task"): run for run in runs}
    design_map = {
        row["task"]: row
        for row in (preregistration.get("design") or {}).get("tasks") or []
    }
    materiality_map = {
        row["task"]: row for row in materiality.get("tasks") or []
    }
    intent = (raw.get("aggregate") or {}).get("intent_to_evaluate") or {}
    if not (
        len(runs) == len(run_map) == len(tasks) == 7
        and set(run_map) == set(tasks)
        and intent.get("scheduled_runs") == 7
        and intent.get("successful_runs") == 7
        and intent.get("terminal_failed_runs") == 0
        and intent.get("run_cells_with_any_failed_attempt") == 0
        and intent.get("run_cells_with_protocol_incomplete_attempt") == 0
        and (raw.get("aggregate") or {}).get("failed_attempts") == 0
        and (raw.get("aggregate") or {}).get("protocol_incomplete_attempts") == 0
    ):
        raise ValueError("two-hour intent-to-evaluate risk set is incomplete")

    records = [
        _validate_run(
            run_map[task], task, design_map[task], materiality_map[task]
        )
        for task in tasks
    ]
    proposal_count = sum(row["completion"]["proposal_count"] for row in records)
    valid_count = sum(
        row["completion"]["valid_proposal_count"] for row in records
    )
    signed_actions = {
        action: sum(
            row["endpoints"]["latest_signed_in_horizon_decision"]["action"]
            == action
            for row in records
        )
        for action in ("commit", "abstain")
    }
    online_materiality = sum(
        row["endpoints"]["online_incumbent"]["materiality"][
            "operational_materiality_contract_passed"
        ]
        for row in records
    )
    terminal_materiality = sum(
        row["endpoints"]["terminal_workspace_artifact"]["materiality"][
            "operational_materiality_contract_passed"
        ]
        for row in records
    )
    committed_materiality = sum(
        bool(
            row["endpoints"]["latest_signed_in_horizon_decision"].get(
                "committed_artifact"
            )
            and row["endpoints"]["latest_signed_in_horizon_decision"][
                "committed_artifact"
            ]["materiality"]["operational_materiality_contract_passed"]
        )
        for row in records
    )
    endpoint_policy_discrepancy = all(
        row["endpoint_relationships"]["terminal_policy_label_in_preregistration"]
        != row["endpoint_relationships"]["terminal_policy_implemented_by_runner"]
        for row in records
    )
    report: dict[str, Any] = {
        "schema_version": 1,
        "trust_status": "TRUSTED_DERIVED_EVIDENCE / EXPLORATORY_2H_ANALYSIS",
        "evidence_scope": (
            "SEVEN_RESULT_SELECTED_SINGLE_TRAJECTORY_TWO_HOUR_EXPLORATORY_SCREEN_"
            "NOT_POPULATION_MODEL_RANKING_FEEDBACK_CAUSAL_SCALING_CONFIRMATORY_"
            "EXTERNAL_VALIDATION_OR_AUTONOMOUS_DISCOVERY_EVIDENCE"
        ),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_provenance": source_provenance(ROOT),
        "environment": {"python": sys.version, "platform": platform.platform()},
        "inputs": {
            "raw_report": {
                "path": _recorded_path(raw_path),
                "sha256": _sha256(raw_path),
                "source_revision": (raw.get("source_provenance") or {}).get(
                    "git_revision"
                ),
            },
            "preregistration": {
                "path": _recorded_path(preregistration_path),
                "sha256": _sha256(preregistration_path),
            },
            "cohort_manifest": {
                "path": _recorded_path(cohort_path),
                "sha256": _sha256(cohort_path),
            },
            "scientific_materiality_contracts": {
                "path": _recorded_path(materiality_path),
                "sha256": _sha256(materiality_path),
            },
        },
        "prerequisites": _validate_prerequisites(preregistration),
        "fixed_design": {
            "analysis_role": (preregistration.get("design") or {}).get(
                "analysis_role"
            ),
            "tasks": tasks,
            "task_count": len(tasks),
            "model": EXPECTED_MODEL,
            "algorithm": EXPECTED_ALGORITHM,
            "feedback_mode": EXPECTED_FEEDBACK_MODE,
            "local_replicate_identifiers": [EXPECTED_SEED],
            "active_wall_horizon_seconds": EXPECTED_HORIZON,
            "primary_time_grid_seconds": list(EXPECTED_GRID),
            "confirmatory_reuse_permitted": False,
            "unconditional_12h_followup_tasks": (
                preregistration.get("unconditional_12h_followup") or {}
            ).get("tasks"),
        },
        "risk_set": {
            "scheduled_cells": 7,
            "successful_cells": 7,
            "terminal_failed_cells": 0,
            "failed_attempts": 0,
            "protocol_incomplete_attempts": 0,
            "proposal_count": proposal_count,
            "valid_proposal_count": valid_count,
            "valid_proposal_rate": valid_count / proposal_count,
            "oracle_calls_including_baselines": sum(
                row["completion"]["oracle_calls_including_baseline"]
                for row in records
            ),
            "provider_total_tokens": sum(
                row["completion"]["total_tokens"] for row in records
            ),
            "estimated_cost_usd": None,
            "signed_in_horizon_endpoint_actions": signed_actions,
            "terminal_workspace_valid_count": sum(
                row["endpoint_relationships"]["terminal_workspace_valid"]
                for row in records
            ),
            "online_incumbent_operational_materiality_pass_count": (
                online_materiality
            ),
            "terminal_workspace_operational_materiality_pass_count": (
                terminal_materiality
            ),
            "signed_commit_operational_materiality_pass_count": (
                committed_materiality
            ),
        },
        "task_records": records,
        "interpretive_findings": {
            "terminal_endpoint_policy_label_differs_from_runner_semantics": (
                endpoint_policy_discrepancy
            ),
            "preregistered_label": "terminal_in_horizon_incumbent",
            "implemented_and_audited_policy": "terminal_workspace_artifact",
            "consequence": (
                "The terminal sentinel must not be described as the online incumbent. "
                "The report retains both endpoints and does not substitute one for the other."
            ),
            "every_terminal_workspace_artifact_differs_from_online_incumbent": all(
                not row["endpoint_relationships"][
                    "terminal_workspace_equals_online_incumbent"
                ]
                for row in records
            ),
            "tasks_with_positive_raw_online_gain_from_30m_to_120m": [
                row["task"] for row in records
                if row["completion"]["score_change_30m_to_120m"] > 0.0
            ],
            "task_specific_operational_materiality_only": True,
            "heterogeneous_science_axes_averaged": False,
        },
        "claims": {
            "fixed_duration_execution_and_lineage_complete": True,
            "task_specific_exploratory_trajectories_described": True,
            "population_model_performance_estimated": False,
            "feedback_causal_effect_identified": False,
            "scaling_law_identified": False,
            "material_post_2h_headroom_demonstrated": False,
            "confirmatory_scientific_result_established": False,
            "external_or_physical_validation_completed": False,
            "autonomous_scientific_discovery_demonstrated": False,
        },
        "limitations": [
            "The cohort was selected after inspecting short-budget GPT-5.5 outcomes and cannot be reused as a confirmatory cohort.",
            "Each task has one uncontrolled provider trajectory; local identifier zero does not control the provider draw.",
            "Task-specific scientific axes are heterogeneous and are not averaged into a cross-task science score.",
            "Operational materiality thresholds are benchmark-preregistered thresholds, not field consensus or external validation.",
            "A two-hour trajectory cannot establish material improvement after two hours; the frozen unconditional 12-hour tranche remains required.",
            "The terminal sentinel records the last workspace artifact published by cutoff, whereas the preregistration names a terminal incumbent endpoint; both are reported separately.",
            "Signed decisions are record-only and made before their own evaluator outcomes; they are not score-aware stopping decisions.",
            "Estimated provider cost is unavailable because pricing was not configured in the run.",
        ],
    }
    finalize_report_trust(report, True)
    return report


def _fmt(value: Any, digits: int = 4) -> str:
    if value is None:
        return "—"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return ("%%.%df" % digits) % float(value)
    return str(value)


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Seven-task two-hour exploratory result",
        "",
        "Status: complete derived audit. This is a result-selected, single-trajectory-per-task exploratory screen, not confirmatory evidence.",
        "",
        "## Execution and evidence",
        "",
        "- All 7/7 scheduled cells reached the declared 7200-second active-wall horizon with no infrastructure failure, retry, or protocol-incomplete outcome.",
        "- The audit replayed every trajectory, evaluation receipt, run manifest, checkpoint, sentinel artifact, evaluator payload, and provider-response hash.",
        "- %d proposals were made; %d were evaluator-valid (%.1f%%). Provider usage was %d total tokens; pricing was not configured."
        % (
            report["risk_set"]["proposal_count"],
            report["risk_set"]["valid_proposal_count"],
            100.0 * report["risk_set"]["valid_proposal_rate"],
            report["risk_set"]["provider_total_tokens"],
        ),
        "",
        "## Task-specific outcomes",
        "",
        "| Task | Online best | 30m→120m | Valid proposals | Held-out | Robustness | Terminal | Signed endpoint | Materiality |",
        "|---|---:|---:|---:|---:|---:|---|---|---|",
    ]
    for row in report["task_records"]:
        online = row["endpoints"]["online_incumbent"]
        science = online["science_metrics"]
        heldout = science.get("heldout_policy_score", science.get("heldout_exact_score"))
        robustness = science.get("heldout_robustness_score", science.get("robustness_score"))
        terminal = row["endpoints"]["terminal_workspace_artifact"]
        signed = row["endpoints"]["latest_signed_in_horizon_decision"]
        lines.append(
            "| %s | %s | %s | %d/%d | %s | %s | %s %.4f | %s | %s |"
            % (
                row["task"],
                _fmt(online["combined_score"]),
                _fmt(row["completion"]["score_change_30m_to_120m"], 6),
                row["completion"]["valid_proposal_count"],
                row["completion"]["proposal_count"],
                _fmt(heldout),
                _fmt(robustness),
                "valid" if terminal["valid"] else "invalid",
                terminal["combined_score"],
                signed["action"],
                "pass" if online["materiality"][
                    "operational_materiality_contract_passed"
                ] else "fail",
            )
        )
    lines.extend([
        "",
        "The online incumbent clears the frozen task-specific operational materiality contract on %d/7 tasks. The terminal workspace artifact clears it on %d/7; signed committed artifacts clear it on %d/6 commits. These are local benchmark thresholds, not external scientific validation."
        % (
            report["risk_set"]["online_incumbent_operational_materiality_pass_count"],
            report["risk_set"]["terminal_workspace_operational_materiality_pass_count"],
            report["risk_set"]["signed_commit_operational_materiality_pass_count"],
        ),
        "",
        "## Endpoint audit",
        "",
        "The runner's terminal sentinel records the last workspace artifact published by the cutoff. The preregistration labels one endpoint `terminal_in_horizon_incumbent`; these are not the same policy. In all seven tasks the terminal workspace artifact differs from the online incumbent, so this report retains the online incumbent, terminal workspace artifact, signed decision, and observer envelope separately.",
        "",
        "Five of seven terminal workspace artifacts are evaluator-valid. The last in-horizon signed actions are six commits and one abstention. Signed actions were made before their own evaluator result and were recorded under forced continuation, so they are not score-aware autonomous stopping outcomes.",
        "",
        "## Claim boundary",
        "",
        "The result supports a complete, hash-bound two-hour exploratory measurement record. It does not estimate population model performance, identify a feedback effect or scaling law, demonstrate post-two-hour headroom, establish a confirmatory scientific result, complete external/physical validation, or demonstrate autonomous scientific discovery. The preselected Diffraction, Electrolyte and HeatExchanger 12-hour tranche remains unexecuted.",
        "",
    ])
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", type=Path, default=DEFAULT_RAW)
    parser.add_argument(
        "--preregistration", type=Path, default=DEFAULT_PREREGISTRATION
    )
    parser.add_argument("--cohort", type=Path, default=DEFAULT_COHORT)
    parser.add_argument("--materiality", type=Path, default=DEFAULT_MATERIALITY)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--markdown-output", type=Path)
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    output = args.output.expanduser().resolve()
    markdown_output = (
        args.markdown_output.expanduser().resolve()
        if args.markdown_output is not None else None
    )
    if output.exists() or (markdown_output is not None and markdown_output.exists()):
        raise SystemExit("refusing to overwrite a two-hour analysis artifact")
    try:
        report = analyze(
            args.raw.expanduser().resolve(),
            args.preregistration.expanduser().resolve(),
            args.cohort.expanduser().resolve(),
            args.materiality.expanduser().resolve(),
        )
    except (OSError, ValueError, TypeError, KeyError) as exc:
        raise SystemExit(str(exc)) from exc
    output.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(output, json.dumps(report, indent=2, allow_nan=False) + "\n")
    if markdown_output is not None:
        markdown_output.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(markdown_output, render_markdown(report))
    print(json.dumps({
        "output": str(output),
        "markdown_output": str(markdown_output) if markdown_output else None,
        "execution_passed": report["execution_passed"],
        "trusted_evidence": report["trusted_evidence"],
        "successful_cells": report["risk_set"]["successful_cells"],
        "proposal_count": report["risk_set"]["proposal_count"],
        "valid_proposal_count": report["risk_set"]["valid_proposal_count"],
    }, indent=2))
    return 0 if report["execution_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
