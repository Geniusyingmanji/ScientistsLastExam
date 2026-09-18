#!/usr/bin/env python3
"""Evaluate inventory baselines through the trusted sandbox and check determinism."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import stat
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from sle.evaluate import INVALID_SCORE, evaluate_candidate  # noqa: E402
from sle.provenance import finalize_report_trust, source_provenance  # noqa: E402
from sle.registry import list_tasks  # noqa: E402
from sle.metric_visibility import SEARCH_VISIBLE_KEYS, public_error_message  # noqa: E402

EVALUATION_SOURCE_SCOPE = ("sle", "benchmarks", "requirements-upstream.txt")


def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()


def _private_path(path: Path, *, existing: bool) -> Path:
    """Require an owner-only location outside every Git worktree; never follow links."""
    path = Path(os.path.abspath(str(path.expanduser())))
    if any(part.is_symlink() for part in (path, *path.parents)):
        raise ValueError("private evidence path must not contain symlinks")
    if not path.parent.exists():
        if existing:
            raise ValueError("private evidence directory is missing")
        path.parent.mkdir(parents=True, mode=0o700)
    info = path.parent.stat()
    if not stat.S_ISDIR(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o700:
        raise ValueError("private evidence directory must have mode 0700")
    if info.st_uid != os.getuid():
        raise ValueError("private evidence directory must belong to the operator")
    git = subprocess.run(["git", "-C", str(path.parent), "rev-parse", "--show-toplevel"],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if git.returncode == 0:
        raise ValueError("private evidence must be outside a Git worktree")
    if existing:
        info = path.stat()
        if (not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o600
                or info.st_uid != os.getuid() or info.st_nlink != 1):
            raise ValueError("private evidence must be a single owner-only regular file (0600)")
    elif path.exists():
        raise FileExistsError("private evidence already exists; originals cannot be overwritten")
    return path


def _open_private(path: Path):
    path = _private_path(path, existing=False)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    return os.fdopen(os.open(str(path), flags, 0o600), "w", encoding="utf-8")


def _validate_new_outputs(*paths: Path) -> None:
    paths = [path for path in paths if path is not None]
    resolved = [path.resolve() for path in paths]
    if len(set(resolved)) != len(resolved):
        raise ValueError("public, private and markdown destinations must be distinct")
    if any(path.exists() or path.is_symlink() for path in paths):
        raise FileExistsError("output already exists; evidence cannot be overwritten")


def _public_metrics(metrics: dict[str, Any]) -> dict[str, Any]:
    # A closed allowlist plus scalar types prevents nested diagnostics and exception text
    # from becoming a second route for publishing sealed world data.
    public = {key: metrics[key] for key in SEARCH_VISIBLE_KEYS
              if key in metrics and key != "error_message"
              and isinstance(metrics[key], (int, float, bool, type(None)))}
    if metrics.get("error_message"):
        public["error_message"] = public_error_message(metrics)
    return public


def _entry(task: str, candidate_sha256: str, runs: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "task": task,
        "candidate_sha256": candidate_sha256,
        "deterministic": len(runs) >= 2 and len({_canonical(run["metrics"]) for run in runs}) == 1,
        "valid_all": all(float(run["metrics"].get("valid", 0.0)) >= 1.0 for run in runs),
        "fail_closed_all": all(float(run["metrics"].get("valid", 0.0)) >= 1.0
                               or float(run["metrics"].get("combined_score", 0.0)) == INVALID_SCORE
                               for run in runs),
        "infrastructure_failure": any(_infrastructure_failure(run["metrics"]) for run in runs),
        "runs": runs,
    }


def _summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "inventory_count": len(rows),
        "deterministic_count": sum(bool(row["deterministic"]) for row in rows),
        "valid_count": sum(bool(row["valid_all"]) for row in rows),
        "fail_closed_count": sum(bool(row["fail_closed_all"]) for row in rows),
        "infrastructure_failure_count": sum(bool(row["infrastructure_failure"]) for row in rows),
    }


def public_projection(raw: dict[str, Any], private_sha256: str,
                      export_provenance: dict[str, Any], compatibility: dict[str, Any]) -> dict[str, Any]:
    """Project measured private results without changing their evaluation provenance."""
    rows = []
    repeats = raw.get("config", {}).get("repeats")
    if type(repeats) is not int or repeats < 2:
        raise ValueError("private determinism report requires at least two repeats")
    for row in raw["tasks"]:
        runs = row["runs"]
        if len(runs) != repeats or [run.get("repeat") for run in runs] != list(range(repeats)):
            raise ValueError("private report has missing or duplicated repeat cells")
        measured = _entry(row["task"], row["candidate_sha256"], runs)
        if any(row.get(key) != value for key, value in measured.items() if key != "runs"):
            raise ValueError("private report decisions disagree with complete metrics")
        rows.append(dict(measured, runs=[{
            "repeat": run["repeat"], "wall_seconds": run["wall_seconds"],
            "metrics": _public_metrics(run["metrics"]),
            "full_metrics_sha256": _digest(run["metrics"]),
            "comparable_metrics_sha256": hashlib.sha256(_canonical(run["metrics"]).encode()).hexdigest(),
            "nested_payload_sha256": {key: _digest(value) for key, value in run["metrics"].items()
                                      if isinstance(value, (dict, list))},
        } for run in runs]))
    summary = _summary(rows)
    if raw.get("summary") != summary:
        raise ValueError("private report summary disagrees with complete metrics")
    execution_passed = (summary["deterministic_count"] == len(rows)
                        and summary["fail_closed_count"] == len(rows)
                        and summary["infrastructure_failure_count"] == 0)
    if raw.get("execution_passed") is not execution_passed:
        raise ValueError("private report execution decision disagrees with complete metrics")
    provenance = {key: value for key, value in raw["source_provenance"].items() if key != "command"}
    report = {
        "schema_version": 2, "trust_status": raw["trust_status"],
        "evidence_scope": "BASELINE_DETERMINISM_ONLY_NOT_MALFORMED_CANDIDATE_COVERAGE",
        "source_provenance": provenance,
        "evaluation_source_provenance_sha256": _digest(raw["source_provenance"]),
        "export_provenance": {key: value for key, value in export_provenance.items() if key != "command"},
        "export_runtime_compatibility": compatibility,
        "private_evidence": {"sha256": private_sha256, "schema_version": raw["schema_version"],
                             "access": "operator_private_original; not published"},
        "created_at": raw["created_at"], "environment": raw["environment"], "config": raw["config"],
        "determinism_excluded_metrics": ["runtime_s"],
        "tasks": rows, "summary": dict(summary,
            invalid_baseline_run_count=sum(float(run["metrics"].get("valid", 0.0)) < 1.0
                                           for row in raw["tasks"] for run in row["runs"]),
            malformed_candidate_evaluations=0),
        "fail_closed_scope": "The compatibility field checks observed baselines only: valid>=1 or "
                             "score==INVALID_SCORE. Valid baselines do not test malformed candidates.",
    }
    finalize_report_trust(report, execution_passed)
    return report


def export_private(private: Path, output: Path) -> dict[str, Any]:
    _validate_new_outputs(output)
    private = _private_path(private, existing=True)
    payload = private.read_bytes()
    raw = json.loads(payload)
    if raw.get("schema_version") != 1:
        raise ValueError("expected an original schema-1 private report")
    source = raw.get("source_provenance", {})
    current = source_provenance(ROOT)
    if (source.get("git_available") is not True or source.get("source_tree_dirty") is not False
            or current.get("source_tree_dirty") is not False):
        raise ValueError("evaluation and export must both have clean, known source revisions")
    revision = source.get("git_revision", "")
    subprocess.run(["git", "merge-base", "--is-ancestor", revision, "HEAD"], cwd=ROOT, check=True)
    changed = subprocess.check_output(["git", "diff", "--name-only", revision, "HEAD", "--",
                                       *EVALUATION_SOURCE_SCOPE], cwd=ROOT, text=True).splitlines()
    if changed:
        raise ValueError("evaluation runtime/task source changed since private measurement")
    expected = {spec.task_id: hashlib.sha256(spec.initial_program_path.read_bytes()).hexdigest()
                for spec in list_tasks(None)}
    actual = {row["task"]: row["candidate_sha256"] for row in raw["tasks"]}
    if actual != expected or len(actual) != len(raw["tasks"]):
        raise ValueError("private report inventory or candidate source differs")
    report = public_projection(raw, hashlib.sha256(payload).hexdigest(), current, {
        "evaluation_revision": revision, "export_revision": current["git_revision"],
        "scope": list(EVALUATION_SOURCE_SCOPE), "changed_paths": changed,
        "evaluation_revision_is_ancestor": True, "unchanged": True,
    })
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as handle:
        handle.write(json.dumps(report, indent=2, allow_nan=False) + "\n")
    return report


def _canonical(metrics: dict[str, Any]) -> str:
    # Runtime is diagnostic, not an oracle output invariant.
    stable = {k: v for k, v in metrics.items() if k not in {"runtime_s"}}
    return json.dumps(stable, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _infrastructure_failure(metrics: dict[str, Any]) -> bool:
    # Explicit fault classification wins over legacy score/error heuristics.
    # Infrastructure failures normally carry an error message too.
    return bool(metrics.get("infrastructure_failure")) or bool(
        float(metrics.get("combined_score", INVALID_SCORE)) == INVALID_SCORE
        and not metrics.get("error_message")
    )


def _evaluate_spec(spec, repeats: int, timeout: float) -> dict[str, Any]:
    """Keep repeats sequential; each evaluation still uses its own trusted subprocess."""
    source = spec.initial_program_path.read_bytes()
    runs = []
    for repeat in range(repeats):
        started = time.monotonic()
        metrics = evaluate_candidate(spec, spec.initial_program_path, timeout_s=timeout)
        runs.append({"repeat": repeat, "wall_seconds": time.monotonic() - started,
                     "metrics": metrics})
    return _entry(spec.task_id, hashlib.sha256(source).hexdigest(), runs)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--private-output", type=Path,
                      help="new full-result file outside Git, in a 0700 directory; created as 0600")
    mode.add_argument("--export-private", type=Path,
                      help="export an unchanged private original without executing any evaluations")
    parser.add_argument("--repeats", type=int, default=2)
    parser.add_argument("--timeout", type=float, default=180.0)
    parser.add_argument("--workers", type=int, default=1,
                        help="concurrent tasks; repeats for each task remain sequential")
    args = parser.parse_args()
    if args.export_private:
        report = export_private(args.export_private, args.output)
        print(json.dumps(report["summary"], indent=2))
        return 0 if report["execution_passed"] else 1
    if args.repeats < 2:
        raise SystemExit("--repeats must be >= 2 for determinism evidence")
    if args.workers < 1:
        raise SystemExit("--workers must be >= 1")
    _validate_new_outputs(args.output, args.private_output)
    if source_provenance(ROOT).get("source_tree_dirty") is not False:
        raise SystemExit("baseline evaluation requires a clean source revision")
    # Reserve the private destination before spending any evaluations.
    private_handle = _open_private(args.private_output)

    report: dict[str, Any] = {
        "schema_version": 1,
        "trust_status": "TRUSTED_SECURE_EVAL",
        "source_provenance": source_provenance(ROOT),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "environment": {"python": sys.version, "platform": platform.platform()},
        "config": {"repeats": args.repeats, "timeout_s": args.timeout,
                   "workers": args.workers},
        "tasks": [],
    }
    specs = list_tasks(None)
    # map yields in registry order regardless of completion order. Threads only
    # supervise independent subprocesses; no oracle runs in this shared process.
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        entries = pool.map(lambda spec: _evaluate_spec(spec, args.repeats, args.timeout), specs)
        for index, entry in enumerate(entries, 1):
            report["tasks"].append(entry)
            print("[%d/%d] %s deterministic=%s valid=%s" %
                  (index, len(specs), entry["task"], entry["deterministic"], entry["valid_all"]),
                  flush=True)

    report["summary"] = _summary(report["tasks"])
    execution_passed = (
        report["summary"]["deterministic_count"] == len(specs)
        and report["summary"]["fail_closed_count"] == len(specs)
        and report["summary"]["infrastructure_failure_count"] == 0
    )
    finalize_report_trust(report, execution_passed)
    with private_handle:
        private_handle.write(json.dumps(report, indent=2, allow_nan=False) + "\n")
        private_handle.flush()
        os.fsync(private_handle.fileno())
    public = export_private(args.private_output, args.output)
    print(json.dumps(public["summary"], indent=2))
    print("Public report: %s" % args.output.resolve())
    return 0 if execution_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
