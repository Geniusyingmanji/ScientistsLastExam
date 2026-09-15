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
    * lists which of mechanism / FDR / refusal are rates, counts-without-denominator,
      published on another split, or missing

Usage:
    python scripts/report_discovery_admission.py \\
        --admission experiments/opus5_admission_criterion_2026-09-02.json \\
        --output /tmp/discovery_admission.json
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
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


def classify_discovery_row(row: dict, role: str, axes: dict | None = None,
                           axis_evidence: list[dict] | None = None) -> dict:
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
    out["published_on_other_split"] = [
        name for name, entry in axes.items()
        if entry is not None and entry.get("status") == "published_on_other_split"
    ]
    out["missing_axes"] = [
        name for name in ("mechanism", "fdr", "refusal")
        if axes.get(name) is None
    ]
    return out


# Admission tables from report_admission_criterion.py are pooled across seeds and
# feedback arms. Triple reports are one row per run. Join the pooled run list when
# the admission producer wrote it; otherwise attach every coarse match instead of
# treating a paired queue as unpublished axes.
COARSE_IDENTITY_FIELDS = (
    "task",
    "model",
    "llm_condition_sha256",
    "task_version",
    "runtime_source_sha256",
)
RUN_IDENTITY_FIELDS = COARSE_IDENTITY_FIELDS + ("seed", "feedback_mode")
IDENTITY_FIELDS = RUN_IDENTITY_FIELDS
AXIS_NAMES = ("mechanism", "fdr", "refusal")


def _identity_value(entry: dict, field: str) -> str:
    value = entry.get(field)
    return "" if value is None else str(value)


def _run_key(entry: dict) -> tuple[str, ...]:
    return tuple(_identity_value(entry, field) for field in RUN_IDENTITY_FIELDS)


def _coarse_key(entry: dict) -> tuple[str, ...]:
    return tuple(_identity_value(entry, field) for field in COARSE_IDENTITY_FIELDS)


def _run_attachment(entry: dict, axes: dict | None, cohort=None) -> dict:
    attached = {
        "seed": entry.get("seed"),
        "feedback_mode": entry.get("feedback_mode"),
        "axes": axes,
        **{field: entry[field] for field in
           ("algorithm", "budget", "run_directory", "split", "selection_evidence", "endpoint")
           if field in entry},
    }
    if cohort is not None:
        attached["cohort"] = cohort
    return attached


def _axes_view(attached: list[dict]) -> dict | None:
    """Presence union across pooled runs. Values are never averaged."""
    if not attached:
        return None
    if len(attached) == 1:
        return attached[0].get("axes")
    out = {}
    for name in AXIS_NAMES:
        present = [
            (item.get("axes") or {}).get(name)
            for item in attached
        ]
        present = [entry for entry in present if entry is not None]
        if not present:
            out[name] = None
        elif all(entry == present[0] for entry in present):
            out[name] = present[0]
        else:
            out[name] = {
                "value": None,
                "status": "pooled_across_runs",
                "run_count": len(present),
            }
    return out


def index_triples(document: dict) -> tuple[dict[tuple[str, ...], dict], dict[tuple[str, ...], list[dict]]]:
    """Index ok triple rows by full run identity and by coarse admission identity."""
    grouped: dict[tuple[str, ...], list[dict]] = {}
    by_coarse: dict[tuple[str, ...], list[dict]] = {}
    for entry in document.get("rows") or []:
        if entry.get("status") != "ok":
            continue
        if any(entry.get(field) is None for field in COARSE_IDENTITY_FIELDS):
            continue
        axes = entry.get("axes")
        run_key = _run_key(entry)
        grouped.setdefault(run_key, []).append(axes)
        by_coarse.setdefault(_coarse_key(entry), []).append(
            _run_attachment(entry, axes)
        )
    # Seed and arm are not a unique run across cohorts, algorithms, or splits.
    # Historical callers may use this coarse key only when it resolves once.
    by_run = {key: entries[0] for key, entries in grouped.items() if len(entries) == 1}
    return by_run, by_coarse


def triple_index(document: dict) -> dict[tuple[str, ...], dict]:
    """Index fully attributable triple rows by run identity, including seed and mode."""
    by_run, _by_coarse = index_triples(document)
    return by_run


def lookup_triple_axes(
    by_run: dict[tuple[str, ...], dict],
    by_coarse: dict[tuple[str, ...], list[dict]],
    row: dict,
) -> tuple[dict | None, list[dict], str]:
    """Join one pooled admission row onto every matching triple run."""
    coarse = _coarse_key(row)
    listed = row.get("runs")
    if isinstance(listed, list) and listed:
        attached = []
        matched = 0
        ambiguous = False
        for spec in listed:
            if not isinstance(spec, dict):
                continue
            candidates = [item for item in by_coarse.get(coarse, [])
                          if all(_identity_value(item, field) == _identity_value(spec, field)
                                 for field in ("seed", "feedback_mode"))]
            for field in ("run_directory", "algorithm", "budget", "split"):
                expected = spec.get(field, row.get(field))
                if expected is not None and expected != "unrecorded":
                    candidates = [item for item in candidates if item.get(field) == expected]
            if len(candidates) == 1:
                matched += 1
                item = _run_attachment(candidates[0], candidates[0]["axes"], spec.get("cohort"))
                item["axes_match_status"] = "matched"
            else:
                ambiguous = ambiguous or len(candidates) > 1
                item = _run_attachment(spec, None, spec.get("cohort"))
                item["axes_match_status"] = "ambiguous" if candidates else "missing"
            attached.append(item)
        if matched == len(attached) and attached:
            return _axes_view(attached), attached, "pooled_runs"
        if matched:
            return _axes_view(attached), attached, "pooled_runs_partial"
        return None, attached, "ambiguous_runs" if ambiguous else "no_match"
    exact = _run_key(row)
    if exact in by_run:
        attached = [_run_attachment(row, by_run[exact])]
        return by_run[exact], attached, "exact"
    named_run = row.get("seed") is not None or row.get("feedback_mode") is not None
    if named_run:
        return None, [], "no_match"
    matches = list(by_coarse.get(coarse) or [])
    if len(matches) == 1:
        return matches[0].get("axes"), matches, "unique_coarse"
    if len(matches) > 1:
        return _axes_view(matches), matches, "all_coarse"
    return None, [], "no_match"


EVIDENCE_IDENTITY_FIELDS = (
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

EVIDENCE_RUN_FIELDS = (
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
            for field in EVIDENCE_IDENTITY_FIELDS
        )
    )


def strict_triple_index(document: dict) -> dict[tuple[object, ...], dict]:
    """Index every addressable triple row, retaining unusable states."""
    grouped: dict[tuple[object, ...], list[dict]] = {}
    for entry in document.get("rows") or []:
        if not _complete_identity(entry):
            continue
        key = tuple(entry[field] for field in EVIDENCE_IDENTITY_FIELDS)
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
    by_run, by_coarse = {}, {}
    strict_triples = {}
    if args.triple:
        triple_doc = json.loads(Path(args.triple).read_text(encoding="utf-8"))
        by_run, by_coarse = index_triples(triple_doc)
        strict_triples = strict_triple_index(triple_doc)
    rows_in = document.get("rows") or []
    rows = []
    for row in rows_in:
        task = str(row.get("task") or "")
        role = roles.get(task) or roles.get(task.split("/")[-1]) or ""
        if args.triple:
            axes, attached, join_status = lookup_triple_axes(by_run, by_coarse, row)
        else:
            axes, attached, join_status = None, [], "no_triple"
        axis_evidence = []
        evidence_runs = row.get("evidence_runs") or []
        for run in evidence_runs:
            expected = {
                field: run.get(field) if field in EVIDENCE_RUN_FIELDS else row.get(field)
                for field in EVIDENCE_IDENTITY_FIELDS
            }
            identity = tuple(expected[field] for field in EVIDENCE_IDENTITY_FIELDS)
            matched = strict_triples.get(identity)
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
                **{field: run.get(field) for field in EVIDENCE_RUN_FIELDS},
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
        if "evidence_runs" in row:
            axes = None
            attached = []
            join_status = ("exact" if len(axis_evidence) == 1 and
                           axis_evidence[0]["join_status"] == "joined" else "evidence_runs")
        classified = classify_discovery_row(
            row, role, axes, axis_evidence if "evidence_runs" in row else None)
        classified["axes_join"] = join_status
        if attached:
            classified["axes_by_run"] = attached
        rows.append(classified)

    discovery = [r for r in rows if r.get("scientific_role") == "discovery"]
    rewritten = sum(
        1 for r in discovery
        if r.get("verdict") != r.get("public_score_verdict")
    )
    join_hist = dict(Counter(row.get("axes_join") for row in rows))
    discovery_join_hist = dict(Counter(row.get("axes_join") for row in discovery))
    join_statuses = [item["join_status"] for row in discovery
                     for item in row.get("axis_evidence", [])]
    report = {
        "schema_version": 4,
        "expected_evidence_run_count": len(join_statuses),
        "axis_join_status_counts": dict(Counter(join_statuses)),
        "evidence_runs_missing_axes_count": sum(
            bool(item["missing_axes"]) for row in discovery
            for item in row.get("axis_evidence", [])),
        "source_admission": str(Path(args.admission)),
        "note": (
            "Discovery rows never inherit measures_iteration from combined_score. "
            "Axes are not averaged. Admission rows list the runs they pooled; "
            "those runs are attached as axes_by_run. A coarse identity with "
            "several triple rows is all_coarse, not unpublished axes."
        ),
        "row_count": len(rows),
        "discovery_row_count": len(discovery),
        "discovery_verdicts_rewritten": rewritten,
        "discovery_rows_missing_axes": sum(
            bool(row.get("missing_axes")) or any(
                item["missing_axes"] for item in row.get("axis_evidence", []))
            for row in discovery
        ),
        "axes_join": join_hist,
        "discovery_axes_join": discovery_join_hist,
        "rows": rows,
    }
    Path(args.output).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("discovery admission: %d rows, %d discovery, %d verdicts rewritten"
          % (len(rows), len(discovery), rewritten))
    print("axes_join:", join_hist)
    print("report:", args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
