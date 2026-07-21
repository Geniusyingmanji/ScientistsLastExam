#!/usr/bin/env python3
"""Baseline-only smoke for installed official search backends.

Run this from each backend's compatible virtual environment. Missing packages are reported
as skipped; an installed backend that cannot evaluate the secure baseline is a failure.
"""

from __future__ import annotations

import argparse
import importlib.util
import importlib.metadata
import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from frontier_science.algorithms import get_algorithm  # noqa: E402
from frontier_science.config import load_llm_client  # noqa: E402
from frontier_science.protocol import SCHEMA_VERSION, load_trajectory  # noqa: E402
from frontier_science.provenance import finalize_report_trust, source_provenance  # noqa: E402
from frontier_science.registry import find_task  # noqa: E402

MODULES = {"openevolve": "openevolve", "abmcts": "treequest", "shinkaevolve": "shinka"}


def _search_artifact_contains(workdir: Path, backend: str, needle: str) -> bool:
    """Search only upstream-owned state, never the trusted trajectory/metric sidecar."""
    roots = [workdir / "upstream"] if backend in {"openevolve", "shinkaevolve"} else [
        workdir / "checkpoint.pkl", workdir / "checkpoint.json"
    ]
    encoded = needle.encode("utf-8")
    for root in roots:
        paths = root.rglob("*") if root.is_dir() else [root]
        for path in paths:
            if not path.is_file():
                continue
            try:
                if encoded in path.read_bytes():
                    return True
            except OSError:
                continue
    return False


def _installed_distribution(backend: str) -> dict:
    package = {
        "openevolve": "openevolve",
        "abmcts": "treequest",
        "shinkaevolve": "shinka-evolve",
    }[backend]
    dist = importlib.metadata.distribution(package)
    metadata = {"package": package, "version": dist.version}
    direct_url = dist.read_text("direct_url.json")
    if direct_url:
        metadata["direct_url"] = json.loads(direct_url)
    return metadata


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend", action="append", choices=tuple(MODULES))
    parser.add_argument("--task", default="LennardJonesCluster")
    parser.add_argument("--all", action="store_true",
                        help="allow an uncertified task for integration diagnostics")
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--expect-sealed-metric", default=None,
                        help="assert this metric is retained in trusted trace but absent from search state")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    selected = args.backend or list(MODULES)
    spec = find_task(args.task, include_uncertified=args.all)
    llm = load_llm_client()
    report = {
        "schema_version": 1,
        "trust_status": "TRUSTED_SECURE_EVAL",
        "evidence_scope": "UPSTREAM_BASELINE_SMOKE_ONLY",
        "source_provenance": source_provenance(ROOT),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "python": sys.version,
        "task": spec.task_id,
        "backends": [],
    }
    failures = 0
    for backend in selected:
        module = MODULES[backend]
        if importlib.util.find_spec(module) is None:
            report["backends"].append({"backend": backend, "status": "skipped", "reason": "not installed"})
            continue
        try:
            with tempfile.TemporaryDirectory(prefix="fs_%s_smoke_" % backend) as tmp:
                workdir = Path(tmp)
                result = get_algorithm(backend)(
                    spec, llm, budget=0, timeout_s=args.timeout, workdir=workdir,
                    seed=0, feedback_mode="normal", log_fn=lambda _: None,
                )
                sealed_retained = None
                sealed_absent_from_search = None
                if args.expect_sealed_metric:
                    events = load_trajectory(workdir / "trajectory.jsonl")
                    sealed_retained = all(
                        args.expect_sealed_metric in (event.get("metrics") or {})
                        for event in events
                    )
                    sealed_absent_from_search = not _search_artifact_contains(
                        workdir, backend, args.expect_sealed_metric
                    )
                    if not sealed_retained:
                        raise AssertionError("sealed metric missing from trusted trajectory")
                    if not sealed_absent_from_search:
                        raise AssertionError("sealed metric leaked into search-owned state")
            if result.evaluated != 1 or result.best_score != result.baseline_score:
                raise AssertionError("baseline-only result has inconsistent accounting")
            if (
                result.summary.get("schema_version") != SCHEMA_VERSION
                or result.summary.get("budget_units") != 1
                or result.summary.get("oracle_calls") != 1
            ):
                raise AssertionError("baseline-only result has inconsistent trajectory accounting")
            report["backends"].append({
                "backend": backend, "status": "passed", "evaluated": result.evaluated,
                "installed_distribution": (
                    result.summary.get("installed_distribution")
                    or _installed_distribution(backend)
                ),
                "baseline_score": result.baseline_score,
                "trajectory_schema_version": result.summary.get("schema_version"),
                "budget_units": result.summary.get("budget_units"),
                "oracle_calls": result.summary.get("oracle_calls"),
                "best_so_far_auc": result.summary.get("best_so_far_auc"),
                "upstream": result.summary.get("upstream"),
                "expected_sealed_metric": args.expect_sealed_metric,
                "sealed_metric_retained_in_trusted_trace": sealed_retained,
                "sealed_metric_absent_from_search_state": sealed_absent_from_search,
            })
        except Exception as exc:  # noqa: BLE001
            failures += 1
            report["backends"].append({"backend": backend, "status": "failed",
                                       "error": "%s: %s" % (type(exc).__name__, exc)})
    execution_passed = failures == 0 and any(
        row["status"] == "passed" for row in report["backends"]
    )
    finalize_report_trust(report, execution_passed)
    text = json.dumps(report, indent=2, allow_nan=False) + "\n"
    if args.output:
        output = args.output.resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0 if execution_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
