#!/usr/bin/env python3
"""Report discovery axes of each run's selected artifact on one explicit split.

Metric names alone do not establish an estimand: false claims divided by claims
(FDR) differs from false claims divided by unsupported worlds (FPR). Contracts
are read only from task packages matching the manifest's exact package hash.
Historical runs without a matching contract retain raw values with unresolved
semantics. No axis is averaged across tasks or selected across runs.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from sle.registry import list_tasks  # noqa: E402
from sle.task_versions import version_class  # noqa: E402
from scripts.reporting_runtime import report_runtime_binding  # noqa: E402
from scripts.reporting_trajectory import read_incumbents, read_events, trajectory_selection_evidence  # noqa: E402


def known_conditions() -> dict[str, str]:
    import yaml

    path = ROOT / "sle" / "llm_conditions.yaml"
    document = yaml.safe_load(path.read_text(encoding="utf-8")) if path.is_file() else {}
    return {str(digest): str(entry.get("model") or "unrecorded")
            for digest, entry in ((document or {}).get("conditions") or {}).items()}


# These aliases locate raw values; they do not assert compatible denominators.
AXES = {
    "mechanism": ("mechanism_score", "body_support_f1", "supported_correct_model_rate",
                  "hypothesis_score"),
    "fdr": ("false_discovery_rate",),
    "refusal": ("unsupported_refusal_rate", "correct_refusal_rate", "null_abstention_correct"),
    "coverage": ("discovery_coverage", "supported_claim_coverage", "attempt_rate"),
}
COUNT_ONLY = {"fdr": ("false_discoveries",), "refusal": ("correct_abstentions",)}


def discovery_task_names() -> set[str]:
    return {str(spec.metadata.get("task")) for spec in list_tasks(None)
            if str(spec.metadata.get("scientific_role", "")) == "discovery"}


def best_metrics(directory: Path) -> dict | None:
    """Metrics belonging to the final incumbent, including a retained baseline."""
    path = directory / "trajectory.jsonl"
    if not path.is_file():
        return None
    selected = read_incumbents(path)
    return (selected[-1].get("metrics") or {}) if selected else None


def run_identity(document: dict) -> tuple[str, str, str, str, str] | None:
    task = str(document.get("task_id") or "")
    if not task:
        return None
    condition = str(document.get("llm_condition_sha256") or "unrecorded")
    model = str((document.get("llm_condition") or {}).get("model") or "")
    if not model:
        model = known_conditions().get(condition, "unrecorded")
    task_version = version_class(task, str(document.get("task_package_sha256") or "unknown"))[:14]
    runtime = str(document.get("runtime_source_sha256") or "unrecorded")
    return task, model, condition, task_version, runtime


def _metric_key(name: str, split: str) -> str:
    return name if split == "unsplit" else split + "_" + name


def _first_present(metrics: dict, names: tuple[str, ...], split: str) -> str | None:
    return next((key for name in names if (key := _metric_key(name, split)) in metrics), None)


def _published_elsewhere(metrics: dict, names: tuple[str, ...], requested: str) -> tuple[str, str] | None:
    for split in ("heldout", "development", "unsplit"):
        if split == requested:
            continue
        key = _first_present(metrics, names, split)
        if key is not None:
            return key, split
    return None


def extract(metrics: dict, split: str = "heldout", contract: dict | None = None) -> dict:
    """No value fallback between heldout, development and unsplit measurements.

    A key published only on another split is reported as published_on_other_split,
    not as a missing axis and not as a copied value.
    """
    out = {}
    for axis, aliases in AXES.items():
        definition = (contract or {}).get(axis)
        candidates = (definition["metric"],) if definition else aliases
        key = _first_present(metrics, candidates, split)
        if key is None:
            counted = _first_present(metrics, COUNT_ONLY.get(axis, ()), split)
            if counted is not None:
                out[axis] = {"value": None, "key": counted, "split": split,
                             "status": "count_without_denominator"}
                continue
            elsewhere = _published_elsewhere(
                metrics, candidates + COUNT_ONLY.get(axis, ()), split)
            if elsewhere is not None:
                other_key, other_split = elsewhere
                out[axis] = {
                    "value": None,
                    "key": other_key,
                    "split": other_split,
                    "requested_split": split,
                    "status": "published_on_other_split",
                }
            else:
                out[axis] = None
            continue
        value = metrics[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError("discovery metric must be finite numeric: " + key)
        entry = {"value": float(value), "key": key, "split": split,
                 "status": "semantics_unrecorded"}
        if definition:
            entry.update({name: definition[name] for name in
                          ("estimand", "numerator", "denominator", "direction")})
            entry["status"] = "declared"
            denominator_key = definition.get("denominator_metric")
            if denominator_key:
                denominator = metrics.get(_metric_key(denominator_key, split))
                entry["denominator_value"] = denominator
                if (isinstance(denominator, bool) or not isinstance(denominator, (int, float))
                        or not math.isfinite(denominator) or denominator < 0):
                    entry.update(value=None, status="denominator_unavailable")
                elif denominator == 0:
                    entry.update(value=None, status="zero_denominator")
        out[axis] = entry
    return out


def current_contracts() -> dict:
    import yaml
    from sle.algorithms.common import task_package_sha256

    contracts = {}
    for spec in list_tasks(None):
        path = spec.task_dir / "TASK_CARD.yaml"
        if path.is_file():
            contract = (yaml.safe_load(path.read_text()) or {}).get("metric_contract")
            if contract:
                contracts[(spec.task_id, task_package_sha256(spec))] = contract
    return contracts


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--runs", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--split", choices=("heldout", "development", "unsplit"), default="heldout")
    args = ap.parse_args(argv)
    wanted, contracts = discovery_task_names(), current_contracts()
    rows, represented = [], set()
    for manifest in sorted(Path(args.runs).rglob("run_manifest.json")):
        try:
            document = json.loads(manifest.read_text(encoding="utf-8"))
        except (ValueError, OSError) as exc:
            rows.append({"task": "unknown", "run_directory": str(manifest.parent.resolve()),
                         "status": "invalid_manifest", "error": "%s: %s" % (manifest, exc)})
            continue
        identity = run_identity(document)
        if identity is None or identity[0].split("/")[-1] not in wanted:
            continue
        task, model, condition, task_version, runtime = identity
        represented.add(task.split("/")[-1])
        row = {"task": task, "model": model, "llm_condition_sha256": condition,
               "task_version": task_version, "runtime_source_sha256": runtime,
               "task_package_sha256": document.get("task_package_sha256"),
               "feedback_mode": document.get("feedback_mode"), "seed": document.get("seed"),
               "budget": document.get("budget"), "algorithm": document.get("algorithm"),
               "run_directory": str(manifest.parent.resolve()), "split": args.split,
               "endpoint": "incumbent"}
        row.update(report_runtime_binding(manifest.parent, document))
        if row["trusted_evidence"]:
            row["budget"] = row["proposal_budget"]
        try:
            metrics = best_metrics(manifest.parent)
            if metrics is not None:
                row["selection_evidence"] = trajectory_selection_evidence(
                    read_events(manifest.parent / "trajectory.jsonl"))
            contract = contracts.get((task, document.get("task_package_sha256")))
            axes = extract(metrics, args.split, contract) if metrics is not None else None
        except ValueError as exc:
            row.update(status="invalid_trajectory_or_metrics", error=str(exc))
        else:
            if axes is None:
                row.update(status="missing_trajectory")
            else:
                row.update(
                    status="ok",
                    combined_score=metrics.get("combined_score"),
                    combined_score_scope="search objective; axes use the requested split",
                    axes=axes,
                    missing_axes=[a for a, v in axes.items() if v is None],
                    published_on_other_split=[
                        a for a, v in axes.items()
                        if v is not None and v.get("status") == "published_on_other_split"
                    ],
                )
        if row["verification_status"] == "unverified":
            row["diagnostic_status"] = row.get("status")
            row["status"] = "unverified_run"
        rows.append(row)
    rows.extend({"task": name, "status": "missing_run"} for name in sorted(wanted - represented))
    report = {"schema_version": 3, "split": args.split,
              "note": "One row per run; selected incumbent; axes never averaged. Undeclared semantics are unresolved.",
              "task_count": len({r["task"].split("/")[-1] for r in rows}),
              "run_count": sum("run_directory" in r for r in rows), "rows": rows}
    Path(args.output).write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    for row in rows:
        print(row["task"], row.get("feedback_mode", ""), row.get("seed", ""), row["status"])
    print("report:", args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
