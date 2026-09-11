"""Six frozen PR74 candidate runs through the current trusted Linux sandbox.

This driver does not import or execute the author diagnostics/oracle drivers.
Full per-world metrics stay outside the checkout in a private directory.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import platform
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import numpy as np
import scipy
from sle import benchmark_layout
from sle.algorithms.common import runtime_source_sha256, task_package_sha256
from sle.evaluate import evaluate_candidate
from sle.spec import load_task_spec

BASE = "2660c38a413fb7281d0e7012a6446eb384a934d1"
TASK_HEAD = "8193c5aa6abff91ff8cbbce9f617518ff3bb9b61"
TASK = ROOT / "benchmarks/EarthScience/FocalMechanismStressInversion"
AUDIT = ROOT / ".research/pr74_shortcut_candidates_2026-09-11"


def digest(value):
    if not isinstance(value, bytes):
        value = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return hashlib.sha256(value).hexdigest()


def sources():
    return {str(path.relative_to(TASK)): digest(path.read_bytes())
            for path in sorted(TASK.rglob("*"))
            if path.is_file() and "__pycache__" not in path.parts}


def write_json(path, value):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")
    temporary.replace(path)


def public_aggregate(metrics):
    # The oracle's per_world output is deliberately never copied into the public report.
    result = {key: value for key, value in metrics.items()
              if key not in {"per_world", "per_instance"}
              and isinstance(value, (int, float, bool))}
    budget = {}
    for split in ("development", "heldout"):
        rows = [row for row in metrics.get("per_world", []) if row["split"] == split]
        units = [row["budget_used"] for row in rows]
        budget[split] = {"world_count": len(rows), "valid_world_count": sum(row["valid"] for row in rows),
                         "total_units": sum(units), "min_units": min(units) if units else None,
                         "max_units": max(units) if units else None,
                         "mean_units": sum(units) / len(units) if units else None}
    return {"metrics": result, "budget_aggregate": budget}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--private-root", type=Path, required=True)
    args = parser.parse_args()
    private = args.private_root.resolve()
    if private == ROOT or ROOT in private.parents:
        raise ValueError("private evidence must be outside checkout")
    os.umask(0o077)
    private.mkdir(mode=0o700, parents=True, exist_ok=True)
    private.chmod(0o700)
    if any(private.glob("*_?.json")):
        raise ValueError("refuse to overwrite earlier private evidence")
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    if revision != BASE:
        raise ValueError("wrong integration source revision")
    if sys.version_info[:3] != (3, 8, 10) or np.__version__ != "1.24.4" or scipy.__version__ != "1.10.1":
        raise ValueError("unexpected scientific Python environment")
    if any(os.environ.get(key) != "1" for key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS")):
        raise ValueError("thread counts must be pinned before imports")
    expected = json.loads((ROOT / ".research/pr74_task_sources_2026-09-11.json").read_text())
    if sources() != expected:
        raise ValueError("task differs from frozen PR74 archive")
    provenance = json.loads((AUDIT / "source_provenance.json").read_text())
    derived = (AUDIT / "paired62208_refined.py").read_bytes()
    prefix = derived[:provenance["original_byte_length"]]
    if (digest(prefix) != provenance["original_sha256"]
            or derived[len(prefix):].decode() != provenance["appended_configuration_utf8"]
            or digest(derived) != provenance["candidate_sha256"]):
        raise ValueError("derived candidate differs from its frozen exact-source provenance")
    # Static import check is supplementary to the recorded full source review.
    modules = {item.name for node in ast.walk(ast.parse(derived))
               if isinstance(node, ast.Import) for item in node.names}
    if modules != {"numpy", "itertools"} or any(isinstance(node, ast.ImportFrom) for node in ast.walk(ast.parse(derived))):
        raise ValueError("probe import boundary changed")
    previous = benchmark_layout.DOMAIN_DISCIPLINES.get("Geophysics")
    if previous not in (None, "EarthScience"):
        raise ValueError("conflicting Geophysics mapping")
    benchmark_layout.DOMAIN_DISCIPLINES["Geophysics"] = "EarthScience"
    spec = load_task_spec(TASK)
    if spec.task_id != "Geophysics/FocalMechanismStressInversion":
        raise ValueError("unexpected logical task ID")
    candidates = {"baseline": TASK / "solution.py",
                  "reference": TASK / "verification/reference_solver.py",
                  "paired62208_refined": AUDIT / "paired62208_refined.py"}
    frozen = {name: path.read_bytes() for name, path in candidates.items()}
    runtime_hash = runtime_source_sha256()
    if not runtime_hash.startswith("8159a99"):
        raise ValueError("unexpected runtime source hash " + runtime_hash)
    report = {
        "schema_version": 1,
        "scope": "six fixed latest-head sandbox replays; no model call, new grid or heldout selection",
        "task_head": TASK_HEAD, "integration_head": BASE, "task_id": spec.task_id,
        "runtime_source_sha256": runtime_hash,
        "task_package_sha256": task_package_sha256(spec), "task_source_hashes": expected,
        "driver_sha256": digest(Path(__file__).read_bytes()),
        "loader_adapter": {"mapping": "Geophysics -> EarthScience", "previous": previous, "in_memory_only": True},
        "derivation": provenance, "started_utc": datetime.now(timezone.utc).isoformat(),
        "runtime": {"python": sys.version, "executable": sys.executable,
                    "platform": platform.platform(), "numpy": np.__version__, "scipy": scipy.__version__,
                    "thread_environment": {key: os.environ.get(key) for key in (
                        "OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS")}},
        "timeout_seconds": 300.0, "candidate_order": list(candidates), "repeats_per_candidate": 2,
        "candidate_plan_sha256": {name: digest(source) for name, source in frozen.items()},
        "raw_metrics_scope": "complete per-world metrics private; public report has scalar and budget aggregates only",
        "candidates": {},
    }
    public = ROOT / ".research/pr74_shortcut_review_2026-09-11.json"
    write_json(public, report)
    for name, source in frozen.items():
        record = {"source_path": str(candidates[name].relative_to(ROOT)),
                  "candidate_sha256": digest(source), "runs": []}
        report["candidates"][name] = record
        full = []
        for repeat in range(1, 3):
            with tempfile.TemporaryDirectory(prefix="sle_pr74_candidate_") as temporary:
                candidate = Path(temporary) / "solution.py"
                candidate.write_bytes(source)
                started = time.monotonic()
                metrics = evaluate_candidate(spec, candidate, timeout_s=300.0)
                elapsed = time.monotonic() - started
            write_json(private / ("%s_%d.json" % (name, repeat)), metrics)
            full.append(metrics)
            record["runs"].append({"repeat": repeat, "wall_seconds": elapsed,
                                   **public_aggregate(metrics), "full_metrics_sha256": digest(metrics)})
            write_json(public, report)
            print(json.dumps({"candidate": name, "repeat": repeat, "seconds": round(elapsed, 3),
                              "valid": metrics.get("valid"), "heldout_feasibility": metrics.get("heldout_feasibility_rate"),
                              "dev": metrics.get("combined_score"), "heldout": metrics.get("robustness_score"),
                              "infrastructure_failure": bool(metrics.get("infrastructure_failure"))}), flush=True)
            if metrics.get("infrastructure_failure") or metrics.get("valid") != 1 or metrics.get("heldout_feasibility_rate") != 1:
                raise RuntimeError("failed fixed replay for " + name + "; inspect private evidence")
        record["full_metrics_repeat_identical"] = full[0] == full[1]
        write_json(public, report)
    if sources() != expected or runtime_source_sha256() != runtime_hash:
        raise ValueError("source changed during evaluation")
    report["completed_evaluations"] = 6
    report["all_repeats_identical"] = all(row["full_metrics_repeat_identical"] for row in report["candidates"].values())
    report["finished_utc"] = datetime.now(timezone.utc).isoformat()
    write_json(public, report)


if __name__ == "__main__":
    main()
