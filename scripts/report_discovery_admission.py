#!/usr/bin/env python3
"""Read an optimization admission table and refuse to treat discovery as one Δ.

`report_admission_criterion.py` compares `combined_score` across paired arms. That is the
right question for optimization. For discovery it is the wrong one: a public score at 1.0
can sit on a held-out mechanism of 0.5 (SequenceLawRecovery, hy3-ioa Wave-1), and averaging
the triple pays a candidate that refuses every world.

This script does not invent a second Δ. It labels each admission row with the task's
scientific role, and for discovery it:

    * keeps the public-score verdict as a statement about the visible scalar only
    * refuses to promote that verdict to `measures_iteration`
    * lists which of mechanism / FDR / refusal are rates, counts-without-denominator, or missing

Usage:
    python scripts/report_discovery_admission.py \\
        --admission experiments/opus5_admission_criterion_2026-09-02.json \\
        --output /tmp/discovery_admission.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from sle.registry import list_tasks  # noqa: E402


def role_index() -> dict[str, str]:
    out = {}
    for spec in list_tasks(None):
        role = str(spec.metadata.get("scientific_role") or "")
        out[spec.task_id] = role
        out[spec.task_dir.name] = role
    return out


def classify_discovery_row(
    row: dict,
    role: str,
    axes: dict | None = None,
    axis_evidence: list[dict] | None = None,
) -> dict:
    """Rewrite one admission row. Optimization rows pass through."""
    public = str(row.get("verdict") or "unknown")
    out = dict(row)
    out["scientific_role"] = role or "unspecified"
    if role != "discovery":
        return out
    out["public_score_verdict"] = public
    if public.startswith("measures_iteration"):
        out["verdict"] = "discovery_public_score_only"
        out["iteration_claim"] = (
            "not_from_combined_score: a discovery Δ on the public scalar is not an "
            "iteration claim; report mechanism, false-discovery and refusal separately"
        )
    elif public == "solved_at_ceiling":
        out["verdict"] = "public_score_at_ceiling"
        out["iteration_claim"] = (
            "public combined_score is at the ceiling; held-out mechanism may not be"
        )
    else:
        out["verdict"] = public
        out["iteration_claim"] = "public_score_only"
    if axis_evidence is not None:
        out["axis_evidence"] = axis_evidence
        out["missing_axes_by_run"] = [
            {
                "run_manifest_sha256": entry["run_manifest_sha256"],
                "join_status": entry["join_status"],
                "missing_axes": entry["missing_axes"],
            }
            for entry in axis_evidence
        ]
        out["count_without_denominator_by_run"] = [
            {
                "run_manifest_sha256": entry["run_manifest_sha256"],
                "join_status": entry["join_status"],
                "axes": entry["count_without_denominator"],
            }
            for entry in axis_evidence
        ]
        if len(axis_evidence) == 1 and axis_evidence[0]["join_status"] == "joined":
            axes = axis_evidence[0].get("axes")
        elif len(axis_evidence) > 1:
            out.pop("axes", None)
            return out
    axes = axes or {name: None for name in ("mechanism", "fdr", "refusal")}
    out["axes"] = axes
    out["count_without_denominator"] = [
        name for name, entry in axes.items()
        if entry is not None and entry.get("status") == "count_without_denominator"
    ]
    out["missing_axes"] = [
        name for name in ("mechanism", "fdr", "refusal")
        if axes.get(name) is None
    ]
    return out


IDENTITY_FIELDS = (
    "task",
    "model",
    "llm_condition_sha256",
    "task_version",
    "runtime_source_sha256",
    "trusted_evaluator_runtime_sha256",
    "algorithm",
    "feedback_mode",
    "proposal_budget",
    "seed",
    "run_manifest_sha256",
)

RUN_IDENTITY_FIELDS = (
    "feedback_mode", "proposal_budget", "seed", "run_manifest_sha256",
)


def _complete_identity(entry: dict) -> bool:
    integer_fields = {"proposal_budget", "seed"}
    return bool(
        all(
            isinstance(entry.get(field), int)
            and not isinstance(entry[field], bool)
            and entry[field] >= 0
            if field in integer_fields
            else isinstance(entry.get(field), str) and bool(entry[field])
            for field in IDENTITY_FIELDS
        )
    )


def triple_index(document: dict) -> dict[tuple[object, ...], dict]:
    """Index every addressable triple row, retaining unusable states."""
    grouped: dict[tuple[object, ...], list[dict]] = {}
    for entry in document.get("rows") or []:
        if not _complete_identity(entry):
            continue
        key = tuple(entry[field] for field in IDENTITY_FIELDS)
        grouped.setdefault(key, []).append(entry)
    indexed = {}
    for key, entries in grouped.items():
        if len(entries) != 1:
            indexed[key] = {
                "join_status": "unusable",
                "unusable_reason": "ambiguous_duplicate_triple_rows",
                "triple_status": "ambiguous",
            }
            continue
        entry = entries[0]
        if entry.get("status") == "ok" and entry.get("trusted_evidence") is True:
            indexed[key] = {**entry, "join_status": "joined"}
        else:
            indexed[key] = {
                **entry,
                "join_status": "unusable",
                "unusable_reason": "triple_row_is_not_trusted_ok_evidence",
                "triple_status": entry.get("status"),
            }
    return indexed


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--admission", required=True,
                    help="JSON from report_admission_criterion.py")
    ap.add_argument("--output", required=True)
    ap.add_argument(
        "--triple",
        help="optional JSON from report_discovery_triple.py; absent axes are reported missing",
    )
    args = ap.parse_args(argv)

    document = json.loads(Path(args.admission).read_text(encoding="utf-8"))
    roles = role_index()
    triples = {}
    if args.triple:
        triple_doc = json.loads(Path(args.triple).read_text(encoding="utf-8"))
        triples = triple_index(triple_doc)
    rows_in = document.get("rows") or []
    rows = []
    for row in rows_in:
        task = str(row.get("task") or "")
        role = roles.get(task) or roles.get(task.split("/")[-1]) or ""
        axis_evidence = []
        evidence_runs = row.get("evidence_runs") or []
        for run in evidence_runs:
            expected = {
                field: run.get(field) if field in RUN_IDENTITY_FIELDS else row.get(field)
                for field in IDENTITY_FIELDS
            }
            identity = tuple(expected[field] for field in IDENTITY_FIELDS)
            matched = triples.get(identity)
            if row.get("trusted_evidence") is not True:
                matched = {
                    "join_status": "unusable",
                    "unusable_reason": "admission_row_is_not_trusted_evidence",
                    "triple_status": None,
                }
            elif not _complete_identity(expected):
                matched = {
                    "join_status": "unusable",
                    "unusable_reason": "expected_run_identity_is_incomplete",
                    "triple_status": None,
                }
            elif matched is None:
                matched = {
                    "join_status": "missing",
                    "missing_reason": "no_matching_triple_row",
                    "triple_status": None,
                }
            axes = matched.get("axes") if matched["join_status"] == "joined" else None
            missing_axes = [
                name for name in ("mechanism", "fdr", "refusal")
                if (axes or {}).get(name) is None
            ]
            count_without_denominator = [
                name for name, value in (axes or {}).items()
                if value is not None
                and value.get("status") == "count_without_denominator"
            ]
            axis_evidence.append({
                **{field: run.get(field) for field in RUN_IDENTITY_FIELDS},
                "join_status": matched["join_status"],
                "triple_status": matched.get("triple_status", matched.get("status")),
                **({"reason": matched.get("unusable_reason")} if
                   matched["join_status"] == "unusable" else {}),
                **({"reason": matched.get("missing_reason")} if
                   matched["join_status"] == "missing" else {}),
                "selected_candidate_sha256": matched.get(
                    "selected_candidate_sha256"
                ),
                "axes": axes,
                "missing_axes": missing_axes,
                "count_without_denominator": count_without_denominator,
            })
        rows.append(classify_discovery_row(
            row, role, axis_evidence=axis_evidence,
        ))

    discovery = [r for r in rows if r.get("scientific_role") == "discovery"]
    rewritten = sum(
        1 for r in discovery
        if r.get("verdict") != r.get("public_score_verdict")
    )
    join_statuses = [
        evidence["join_status"]
        for row in discovery
        for evidence in row.get("axis_evidence") or []
    ]
    report = {
        "schema_version": 4,
        "source_admission": str(Path(args.admission)),
        "note": (
            "Discovery rows never inherit measures_iteration from combined_score. "
            "Axes are not averaged."
        ),
        "row_count": len(rows),
        "discovery_row_count": len(discovery),
        "discovery_verdicts_rewritten": rewritten,
        "expected_evidence_run_count": len(join_statuses),
        "axis_join_status_counts": {
            status: join_statuses.count(status)
            for status in sorted(set(join_statuses))
        },
        "evidence_runs_missing_axes_count": sum(
            bool(evidence.get("missing_axes"))
            for row in discovery
            for evidence in row.get("axis_evidence") or []
        ),
        "discovery_rows_missing_axes": sum(
            bool(row.get("missing_axes"))
            or any(
                bool(run.get("missing_axes"))
                for run in row.get("missing_axes_by_run") or []
            )
            for row in discovery
        ),
        "rows": rows,
    }
    Path(args.output).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("discovery admission: %d rows, %d discovery, %d verdicts rewritten"
          % (len(rows), len(discovery), rewritten))
    print("report:", args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
