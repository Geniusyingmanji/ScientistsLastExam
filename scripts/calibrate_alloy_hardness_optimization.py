#!/usr/bin/env python3
"""Rebuild and calibrate the DOI-held alloy-hardness replay."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import itertools
import json
import platform
import sys
import tempfile
import textwrap
from datetime import datetime, timezone
from pathlib import Path

import numpy as np


sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from frontier_science.evaluate import evaluate_candidate  # noqa: E402
from frontier_science.metric_visibility import search_visible_metrics  # noqa: E402
from frontier_science.provenance import finalize_report_trust, source_provenance  # noqa: E402
from frontier_science.registry import find_task  # noqa: E402


ROOT = Path(__file__).resolve().parent.parent
TASK = ROOT / "benchmarks/MaterialsScience/AlloyHardnessOptimization"
DATA = TASK / "verification/alloy_hardness_v1.json"
BUILDER_PATH = ROOT / "scripts/build_alloy_hardness_data.py"


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError("cannot load %s" % path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


BUILDER = _load(BUILDER_PATH, "alloy_builder_calibration")
ORACLE = _load(TASK / "verification/evaluator.py", "alloy_oracle_calibration")


def _sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _rebuild(csv_path):
    rebuilt = BUILDER.build(Path(csv_path))
    rendered = json.dumps(
        rebuilt, indent=2, sort_keys=True, allow_nan=False, ensure_ascii=True
    ) + "\n"
    return {
        "rebuilt_sha256": hashlib.sha256(rendered.encode("utf-8")).hexdigest(),
        "expected_sha256": _sha256(DATA),
        "exact_match": rendered.encode("utf-8") == DATA.read_bytes(),
        "contract": rebuilt["contract"],
    }


def _distance(left, right):
    elements = set(left["composition"]) | set(right["composition"])
    return 0.5 * sum(abs(
        float(left["composition"].get(element, 0.0))
        - float(right["composition"].get(element, 0.0))
    ) for element in elements)


def _choose_batch(rows, prediction):
    values = np.asarray(prediction, dtype=float)
    normalized = (values - np.min(values)) / (np.ptp(values) + 1.0e-12)
    best = None
    for indices in itertools.combinations(range(len(rows)), 3):
        diversity = np.mean([
            _distance(rows[left], rows[right])
            for left, right in itertools.combinations(indices, 2)
        ])
        value = 0.90 * float(np.mean(normalized[list(indices)]))
        value += 0.10 * float(diversity)
        key = tuple(rows[index]["id"] for index in indices)
        if (
            best is None or value > best[0] + 1.0e-15
            or (abs(value - best[0]) <= 1.0e-15 and key < best[1])
        ):
            best = (value, key, indices)
    return list(best[2])


def truth_blind_assay_policy(problem, assay):
    """Assay proxy extremes and spatially smooth the two observed residuals."""
    rows = list(problem["candidates"])
    proxy = np.asarray([row["proxy_hardness_hv"] for row in rows], dtype=float)
    queried = [int(np.argmin(proxy)), int(np.argmax(proxy))]
    observed = np.asarray([
        float(assay(rows[index]["id"])["hardness_hv"])
        for index in queried
    ])
    residual = observed - proxy[queried]
    predicted = []
    for index, row in enumerate(rows):
        distances = np.asarray([
            _distance(row, rows[queried_index]) for queried_index in queried
        ])
        weights = 1.0 / (distances + 0.05) ** 2
        predicted.append(float(proxy[index] + np.dot(weights, residual) / np.sum(weights)))
    selected = _choose_batch(rows, predicted)

    # Two observations cannot identify study effects, detailed processing or
    # microstructure.  Use a deliberately conservative fixed floor plus the
    # observed correction scale; interval quality is evaluated separately.
    width = max(250.0, 1.645 * (float(np.max(abs(residual))) + 100.0))
    predictions = {}
    for index in selected:
        point = float(np.clip(predicted[index], 0.0, 2000.0))
        predictions[rows[index]["id"]] = {
            "predicted_hardness_hv": point,
            "interval_hv": [max(0.0, point - width), min(2000.0, point + width)],
        }
    return {
        "alloy_ids": [rows[index]["id"] for index in selected],
        "predictions": predictions,
    }


def _secure_isolation_and_failure_checks(spec):
    valid = textwrap.dedent(
        """
        from pathlib import Path
        CALLS = 0
        def design_alloy_batch(problem, assay):
            global CALLS
            CALLS += 1
            marker = Path('/tmp/alloy_calibration_seen')
            if CALLS != 1 or marker.exists():
                return {'alloy_ids': [], 'predictions': {}}
            marker.write_text('seen')
            rows = problem['candidates'][:3]
            return {
                'alloy_ids': [row['id'] for row in rows],
                'predictions': {
                    row['id']: {'predicted_hardness_hv': row['proxy_hardness_hv'],
                                'interval_hv': [0.0, 2000.0]}
                    for row in rows
                },
            }
        """
    )
    failures = {
        "overspend": (
            "for _ in range(3): assay(problem['candidates'][0]['id'])"
        ),
        "invalid_assay": "assay('unknown-alloy')",
        "malformed_submission": "pass",
    }
    template = textwrap.dedent(
        """
        def design_alloy_batch(problem, assay):
            try:
                BODY
            except Exception:
                pass
            if MODE == 'malformed_submission':
                return {'alloy_ids': [], 'predictions': {}}
            rows = problem['candidates'][:3]
            return {
                'alloy_ids': [row['id'] for row in rows],
                'predictions': {
                    row['id']: {'predicted_hardness_hv': row['proxy_hardness_hv'],
                                'interval_hv': [0.0, 2000.0]}
                    for row in rows
                },
            }
        """
    )
    records = []
    with tempfile.TemporaryDirectory(prefix="alloy_hardness_calibration_") as tmp:
        root = Path(tmp)
        candidate = root / "valid.py"
        candidate.write_text(valid, encoding="utf-8")
        result = evaluate_candidate(spec, candidate, timeout_s=90)
        records.append({
            "mode": "fresh_process",
            "valid": result.get("valid"),
            "combined_score": result.get("combined_score"),
            "candidate_world_call_count": result.get("candidate_world_call_count"),
            "candidate_world_valid_rate": result.get("candidate_world_valid_rate"),
            "passed": bool(
                result.get("valid") == 1.0
                and result.get("candidate_world_call_count") == 13
                and result.get("candidate_world_valid_rate") == 1.0
            ),
        })
        for mode, body in failures.items():
            candidate = root / (mode + ".py")
            source = template.replace("BODY", body).replace("MODE", repr(mode))
            candidate.write_text(source, encoding="utf-8")
            result = evaluate_candidate(spec, candidate, timeout_s=90)
            records.append({
                "mode": mode,
                "valid": result.get("valid"),
                "combined_score": result.get("combined_score"),
                "passed": bool(
                    result.get("valid") == 0.0
                    and float(result.get("combined_score", 1.0)) <= 0.0
                    and result.get("infrastructure_failure") is None
                ),
            })
    return {
        "records": records,
        "fresh_process_per_world_passed": records[0]["passed"],
        "fail_closed_passed": all(row["passed"] for row in records[1:]),
        "passed": all(row["passed"] for row in records),
    }


def calibrate(csv_path):
    document = json.loads(DATA.read_text(encoding="utf-8"))
    baseline = ORACLE.evaluate(ORACLE._baseline_policy)
    reference = ORACLE.evaluate(ORACLE._reference_policy)
    truth_blind = ORACLE.evaluate(truth_blind_assay_policy)
    source_dois = {row["doi"] for row in document["historical_source_recipes"]}
    confirmation_dois = {
        row["doi"] for row in document["reserved_confirmation_recipes"]
    }
    target_dois = {row["source_doi"] for row in document["worlds"]}
    source_keys = {
        (tuple(row["composition"].items()), row["processing_method"])
        for row in document["historical_source_recipes"]
    }
    target_keys = {
        (tuple(row["composition"].items()), row["processing_method"])
        for world in document["worlds"] for row in world["candidates"]
    }
    confirmation_keys = {
        (tuple(row["composition"].items()), row["processing_method"])
        for row in document["reserved_confirmation_recipes"]
    }
    anchors = ORACLE._anchors()
    spec = find_task(
        "MaterialsScience/AlloyHardnessOptimization", include_uncertified=True
    )
    secure_baseline = evaluate_candidate(spec, spec.initial_program_path, timeout_s=90)
    direct_baseline = json.loads(json.dumps(baseline, allow_nan=False))
    direct_baseline["raw_score"] = direct_baseline["combined_score"]
    visible = search_visible_metrics(secure_baseline)
    isolation = _secure_isolation_and_failure_checks(spec)
    source_paths = (
        TASK / "Task.md",
        TASK / "TASK_CARD.yaml",
        TASK / "solution.py",
        TASK / "verification/evaluator.py",
        TASK / "verification/alloy_hardness_v1.json",
        TASK / "frontier_eval/metadata.yaml",
        TASK / "frontier_eval/run_eval.py",
        BUILDER_PATH,
        Path(__file__).resolve(),
    )
    checks = {
        "source_target_dois_disjoint": not source_dois & target_dois,
        "source_target_exact_recipes_disjoint": not source_keys & target_keys,
        "confirmation_target_exact_recipes_overlap": bool(
            confirmation_keys & target_keys
        ),
        "confirmation_not_in_proxy_source": not confirmation_keys & source_keys,
        "target_world_count_is_thirteen": len(document["worlds"]) == 13,
        "development_world_count_is_eight": len(ORACLE.DEVELOPMENT_WORLDS) == 8,
        "heldout_world_count_is_five": len(ORACLE.HELDOUT_WORLDS) == 5,
        "baseline_is_zero_on_both_splits": (
            baseline["combined_score"] == 0.0
            and baseline["heldout_policy_score"] == 0.0
        ),
        "reference_is_one_on_both_splits": (
            reference["combined_score"] == 1.0
            and reference["heldout_policy_score"] == 1.0
        ),
        "truth_blind_uses_full_unique_budget": (
            truth_blind["development_mean_assay_calls"] == 2.0
            and truth_blind["heldout_mean_assay_calls"] == 2.0
            and truth_blind["development_assay_unique_rate"] == 1.0
            and truth_blind["heldout_assay_unique_rate"] == 1.0
        ),
        "truth_blind_improves_development": truth_blind["combined_score"] > 0.30,
        "truth_blind_transfers_heldout": truth_blind["heldout_policy_score"] > 0.30,
        "every_world_keeps_utility_range": all(
            np.ptp([row["study_hardness_hv"] for row in world["candidates"]]) > 0
            for world in document["worlds"]
        ),
        "both_split_anchors_have_headroom": (
            anchors["split_development"]["reference_utility"]
            > anchors["split_development"]["baseline_utility"] + 0.05
            and anchors["split_heldout"]["reference_utility"]
            > anchors["split_heldout"]["baseline_utility"] + 0.05
        ),
        "secure_baseline_matches_direct": secure_baseline == direct_baseline,
        "search_visible_metrics_are_sealed": set(visible) == {
            "combined_score", "valid", "feasibility_rate", "raw_score"
        },
        "fresh_process_and_fail_closed": isolation["passed"],
    }
    report = {
        "schema_version": 1,
        "trust_status": "TRUSTED_TASK_CALIBRATION",
        "evidence_scope": (
            "RETROSPECTIVE_DOI_GROUPED_MPEA_HARDNESS_ACTIVE_DESIGN_REPLAY_"
            "NOT_PROSPECTIVE_ALLOY_SYNTHESIS_MECHANICAL_VALIDATION_OR_"
            "AUTONOMOUS_DISCOVERY_EVIDENCE"
        ),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "environment": {
            "python": sys.version,
            "numpy": np.__version__,
            "platform": platform.platform(),
        },
        "task": "MaterialsScience/AlloyHardnessOptimization",
        "task_source_sha256": {
            str(path.relative_to(ROOT)): _sha256(path) for path in source_paths
        },
        "data_rebuild": _rebuild(csv_path),
        "counts": {
            "historical_proxy_recipes": len(document["historical_source_recipes"]),
            "historical_proxy_studies": len(source_dois),
            "reserved_confirmation_recipes": len(document["reserved_confirmation_recipes"]),
            "reserved_confirmation_studies": len(confirmation_dois),
            "target_recipes": sum(len(world["candidates"]) for world in document["worlds"]),
            "target_studies": len(target_dois),
        },
        "anchors": {
            "development": anchors["split_development"],
            "heldout": anchors["split_heldout"],
        },
        "baseline_metrics": baseline,
        "secure_baseline_metrics": secure_baseline,
        "secure_baseline_exactly_matches_direct": secure_baseline == direct_baseline,
        "reference_metrics": reference,
        "truth_blind_assay_metrics": truth_blind,
        "search_visible_metric_keys": sorted(visible),
        "secure_isolation_and_failure_checks": isolation,
        "checks": checks,
        "limitations": [
            "The source is a retrospective literature compilation, not a prospective campaign.",
            "The benchmark rules were developed after inspecting the public compilation and were not prospectively preregistered.",
            "DOI grouping prevents row leakage but does not harmonize processing, microstructure or indentation protocol.",
            "Only six of sixty-five target recipes have any exact composition/process record from another DOI; absence is not failed replication.",
            "Exact composition/process matches are still not controlled experimental replicates and can differ by hundreds of HV.",
            "Public finite worlds cannot rule out memorization or pretraining contamination.",
        ],
    }
    report["execution_passed"] = bool(
        report["data_rebuild"]["exact_match"] and all(checks.values())
    )
    report["source_provenance"] = source_provenance(ROOT)
    finalize_report_trust(report, report["execution_passed"])
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = calibrate(args.csv)
    text = json.dumps(report, indent=2, allow_nan=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0 if report["execution_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
