#!/usr/bin/env python3
"""Evaluate inventory baselines through the trusted sandbox and check determinism."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from frontier_science.evaluate import INVALID_SCORE, evaluate_candidate  # noqa: E402
from frontier_science.provenance import finalize_report_trust, source_provenance  # noqa: E402
from frontier_science.registry import list_tasks  # noqa: E402


def _canonical(metrics: dict[str, Any]) -> str:
    # Runtime is diagnostic, not an oracle output invariant.
    stable = {k: v for k, v in metrics.items() if k not in {"runtime_s"}}
    return json.dumps(stable, sort_keys=True, separators=(",", ":"), allow_nan=False)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repeats", type=int, default=2)
    parser.add_argument("--timeout", type=float, default=180.0)
    args = parser.parse_args()
    if args.repeats < 1:
        raise SystemExit("--repeats must be >= 1")

    report: dict[str, Any] = {
        "schema_version": 1,
        "trust_status": "TRUSTED_SECURE_EVAL",
        "source_provenance": source_provenance(ROOT),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "environment": {"python": sys.version, "platform": platform.platform()},
        "config": {"repeats": args.repeats, "timeout_s": args.timeout},
        "tasks": [],
    }
    specs = list_tasks(None)
    for index, spec in enumerate(specs, 1):
        source = spec.initial_program_path.read_bytes()
        runs = []
        for repeat in range(args.repeats):
            started = time.monotonic()
            metrics = evaluate_candidate(spec, spec.initial_program_path, timeout_s=args.timeout)
            runs.append({
                "repeat": repeat,
                "wall_seconds": time.monotonic() - started,
                "metrics": metrics,
            })
        signatures = [_canonical(run["metrics"]) for run in runs]
        infrastructure_failure = any(
            float(run["metrics"].get("combined_score", INVALID_SCORE)) == INVALID_SCORE
            and not run["metrics"].get("error_message")
            for run in runs
        )
        entry = {
            "task": spec.task_id,
            "candidate_sha256": hashlib.sha256(source).hexdigest(),
            "deterministic": len(set(signatures)) == 1,
            "valid_all": all(float(run["metrics"].get("valid", 0.0)) >= 1.0 for run in runs),
            "fail_closed_all": all(
                float(run["metrics"].get("valid", 0.0)) >= 1.0
                or float(run["metrics"].get("combined_score", 0.0)) == INVALID_SCORE
                for run in runs
            ),
            "infrastructure_failure": infrastructure_failure,
            "runs": runs,
        }
        report["tasks"].append(entry)
        print("[%d/%d] %s deterministic=%s valid=%s" %
              (index, len(specs), spec.task_id, entry["deterministic"], entry["valid_all"]), flush=True)

    report["summary"] = {
        "inventory_count": len(specs),
        "deterministic_count": sum(bool(row["deterministic"]) for row in report["tasks"]),
        "valid_count": sum(bool(row["valid_all"]) for row in report["tasks"]),
        "fail_closed_count": sum(bool(row["fail_closed_all"]) for row in report["tasks"]),
        "infrastructure_failure_count": sum(bool(row["infrastructure_failure"]) for row in report["tasks"]),
    }
    execution_passed = (
        report["summary"]["deterministic_count"] == len(specs)
        and report["summary"]["fail_closed_count"] == len(specs)
        and report["summary"]["infrastructure_failure_count"] == 0
    )
    finalize_report_trust(report, execution_passed)
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"], indent=2))
    print("Report: %s" % output)
    return 0 if execution_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
