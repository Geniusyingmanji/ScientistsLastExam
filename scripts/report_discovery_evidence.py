#!/usr/bin/env python3
"""Inspect discovery profiles or sealed process/outcome evidence without an LLM.

Standalone files are structurally checked, never authenticated by their own hashes.
Use the enclosing run verifier before treating them as benchmark evidence.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sle.certification import certification_status
from sle.discovery_profiles import profile_for
from sle.discovery_trace import evidence_report
from sle.registry import list_tasks


def inventory():
    rows = []
    for spec in list_tasks(None):
        if spec.metadata.get("scientific_role") == "discovery":
            row = profile_for(spec)
            row["certification_status"] = certification_status(spec.task_id)
            rows.append(row)
    return {"schema_version": 1, "kind": "discovery_profiles", "task_count": len(rows),
            "assessment_counts": dict(Counter(row["assessment_status"] for row in rows)),
            "rows": rows}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--metrics", type=Path, help="private full metrics JSON from sle eval")
    parser.add_argument("--candidate", type=Path, help="optionally verify exact source binding")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    if args.candidate and not args.metrics:
        parser.error("--candidate requires --metrics")
    try:
        if args.metrics:
            metrics = json.loads(args.metrics.read_text())
            if not isinstance(metrics, dict):
                raise ValueError("metrics must be an object")
            expected = hashlib.sha256(args.candidate.read_bytes()).hexdigest() if args.candidate else None
            report = evidence_report(metrics, expected_candidate_sha256=expected)
        else:
            report = inventory()
        rendered = json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
        if args.output:
            args.output.write_text(rendered)
        else:
            print(rendered, end="")
        return 0
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print("discovery evidence rejected: %s" % exc, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
