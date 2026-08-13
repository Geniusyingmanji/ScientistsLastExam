#!/usr/bin/env python3
"""Validate and merge one official-backend smoke report from each Python environment."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from sle.protocol import SCHEMA_VERSION  # noqa: E402
from sle.provenance import finalize_report_trust, source_provenance  # noqa: E402
from sle.algorithms.abmcts_backend import (  # noqa: E402
    TREEQUEST_COMMIT,
    TREEQUEST_VERSION,
)
from sle.algorithms.openevolve_backend import (  # noqa: E402
    OPENEVOLVE_COMMIT,
    OPENEVOLVE_VERSION,
)
from sle.algorithms.shinkaevolve_backend import (  # noqa: E402
    SHINKA_COMMIT,
    SHINKA_VERSION,
)

EXPECTED = {"openevolve", "abmcts", "shinkaevolve"}
EXPECTED_UPSTREAM = {
    "openevolve": {
        "name": "openevolve", "version": OPENEVOLVE_VERSION, "commit": OPENEVOLVE_COMMIT,
    },
    "abmcts": {"name": "treequest", "version": TREEQUEST_VERSION,
                "commit": TREEQUEST_COMMIT},
    "shinkaevolve": {"name": "shinkaevolve", "version": SHINKA_VERSION,
                      "commit": SHINKA_COMMIT},
}
EXPECTED_DISTRIBUTIONS = {
    "openevolve": {"package": "openevolve", "version": OPENEVOLVE_VERSION},
    "abmcts": {"package": "treequest", "version": TREEQUEST_VERSION},
    "shinkaevolve": {"package": "shinka-evolve", "version": SHINKA_VERSION},
}


def merge_reports(paths: list[Path]) -> dict[str, Any]:
    reports = [json.loads(Path(path).read_text(encoding="utf-8")) for path in paths]
    rows = [row for report in reports for row in report.get("backends", [])]
    names = [row.get("backend") for row in rows]
    issues = []
    if set(names) != EXPECTED or len(names) != len(EXPECTED):
        issues.append("expected exactly one report for each official backend")
    revisions = {
        report.get("source_provenance", {}).get("git_revision") for report in reports
    }
    if len(revisions) != 1 or None in revisions:
        issues.append("backend reports do not share one source revision")
    if any(
        report.get("source_provenance", {}).get("source_tree_dirty") is not False
        for report in reports
    ):
        issues.append("at least one backend report lacks a clean source tree")
    for report in reports:
        if report.get("trust_status") != "TRUSTED_SECURE_EVAL":
            issues.append("unexpected trust status")
        if report.get("evidence_scope") != "UPSTREAM_BASELINE_SMOKE_ONLY":
            issues.append("unexpected evidence scope")
        if not report.get("execution_passed"):
            issues.append("child smoke did not pass")
    for row in rows:
        if (
            row.get("status") != "passed"
            or row.get("trajectory_schema_version") != SCHEMA_VERSION
            or row.get("budget_units") != 1
            or row.get("oracle_calls") != 1
        ):
            issues.append("backend row failed trajectory/accounting validation")
        if row.get("upstream") != EXPECTED_UPSTREAM.get(row.get("backend")):
            issues.append("backend upstream version/commit does not match the pinned adapter")
        distribution = row.get("installed_distribution") or {}
        expected_distribution = EXPECTED_DISTRIBUTIONS.get(row.get("backend"), {})
        if any(distribution.get(key) != value for key, value in expected_distribution.items()):
            issues.append("installed distribution does not match the pinned backend")
        if row.get("backend") == "shinkaevolve":
            vcs = (distribution.get("direct_url") or {}).get("vcs_info") or {}
            if vcs.get("commit_id") != SHINKA_COMMIT:
                issues.append("installed ShinkaEvolve Git commit does not match the pin")
        expected_sealed = row.get("expected_sealed_metric")
        if expected_sealed is not None and (
            row.get("sealed_metric_retained_in_trusted_trace") is not True
            or row.get("sealed_metric_absent_from_search_state") is not True
        ):
            issues.append("backend failed evaluator-only metric sealing validation")
    provenance = source_provenance(ROOT)
    if provenance.get("source_tree_dirty") is not False:
        issues.append("merge used a source tree that was not clean")
    if len(revisions) == 1 and provenance.get("git_revision") not in revisions:
        issues.append("merge source revision differs from child reports")
    execution_issues = [
        issue for issue in issues
        if "clean source" not in issue and "source revision" not in issue
        and "merge used a source tree" not in issue
    ]
    merged = {
        "schema_version": 1,
        "trust_status": "TRUSTED_SECURE_EVAL",
        "evidence_scope": "UPSTREAM_BASELINE_SMOKE_ONLY",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_provenance": provenance,
        "reports": reports,
        "issues": sorted(set(issues)),
    }
    finalize_report_trust(merged, not execution_issues)
    if issues:
        merged["trusted_evidence"] = False
        merged["passed"] = False
    return merged


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", action="append", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = merge_reports(args.input)
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"passed": report["passed"], "issues": report["issues"]}, indent=2))
    print("Report: %s" % output)
    return 0 if report["execution_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
