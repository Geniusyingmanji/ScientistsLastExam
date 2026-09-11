"""Two independent PR30 revised-simplex calls; never rerun or replace prior evidence."""
from __future__ import annotations

import argparse
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
TASK_HEAD = "90366563a7605e8f6eb6226200b1463615419b4a"
RUNTIME_HASH = "8159a99d54894dd304e3ac48956cd05d4389f12a041f5d5d86a2c079641c2c86"
TASK = ROOT / "benchmarks/ComputerScience/AffineLoopRankingCertificate"
AUDIT = ROOT / ".research/pr30_simplex_candidates_2026-09-11"


def digest(value):
    if not isinstance(value, bytes):
        value = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return hashlib.sha256(value).hexdigest()


def sources():
    return {str(p.relative_to(TASK)): digest(p.read_bytes()) for p in sorted(TASK.rglob("*"))
            if p.is_file() and "__pycache__" not in p.parts}


def write_json(path, value):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")
    temporary.replace(path)


def public_aggregate(metrics):
    rows = metrics.get("per_instance", [])
    scores = [row["instance_score"] for row in rows]
    return {
        "metrics": {key: value for key, value in metrics.items()
                    if key not in {"per_world", "per_instance"} and isinstance(value, (int, float, bool))},
        "instance_aggregate": {"count": len(rows), "valid_count": sum(row["valid"] for row in rows),
                               "score_min": min(scores) if scores else None,
                               "score_max": max(scores) if scores else None,
                               "score_mean": sum(scores) / len(scores) if scores else None},
        "outcome": {"candidate_failure_kind": metrics.get("candidate_failure_kind"),
                    "infrastructure_failure": bool(metrics.get("infrastructure_failure")),
                    "scientific_score_available": metrics.get("valid") == 1 and metrics.get("feasibility_rate") == 1},
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--private-root", type=Path, required=True)
    private = parser.parse_args().private_root.resolve()
    if private == ROOT or ROOT in private.parents:
        raise ValueError("private evidence must be outside checkout")
    os.umask(0o077)
    private.mkdir(mode=0o700, parents=True, exist_ok=True)
    private.chmod(0o700)
    if any(private.iterdir()):
        raise ValueError("refuse to reuse private evidence directory")
    if subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip() != BASE:
        raise ValueError("wrong runtime revision")
    if runtime_source_sha256() != RUNTIME_HASH:
        raise ValueError("wrong runtime source")
    if sys.version_info[:3] != (3, 8, 10) or np.__version__ != "1.24.4" or scipy.__version__ != "1.10.1":
        raise ValueError("wrong Python/NumPy/SciPy versions")
    if any(os.environ.get(key) != "1" for key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS")):
        raise ValueError("all numerical thread counts must be one")
    frozen = json.loads((ROOT / ".research/pr30_simplex_task_sources_2026-09-11.json").read_text())
    if sources() != frozen:
        raise ValueError("task archive changed")
    provenance = json.loads((AUDIT / "source_provenance.json").read_text())
    source = (AUDIT / "exact_lp_revised_simplex.py").read_bytes()
    if source.count(b'method="revised simplex"') != 1 or b'method="highs"' in source:
        raise ValueError("expected exactly the frozen solver-method replacement")
    prior = source.replace(b'method="revised simplex"', b'method="highs"', 1)
    if digest(source) != provenance["candidate_sha256"] or digest(prior) != provenance["prior_candidate_sha256"]:
        raise ValueError("candidate differs by more than the declared single line")
    compare = provenance["prior_reference_comparison"]
    if (compare["integration_head"] != BASE or compare["runtime_source_sha256"] != RUNTIME_HASH
            or compare["task_head"] != TASK_HEAD
            or digest((TASK / "verification/reference_ranking.py").read_bytes()) != compare["reference_sha256"]):
        raise ValueError("prior reference is not from the same task/runtime source")
    previous = benchmark_layout.DOMAIN_DISCIPLINES.get("ScientificComputing")
    if previous not in (None, "ComputerScience"):
        raise ValueError("conflicting logical-domain mapping")
    benchmark_layout.DOMAIN_DISCIPLINES["ScientificComputing"] = "ComputerScience"
    spec = load_task_spec(TASK)
    if spec.task_id != "ScientificComputing/AffineLoopRankingCertificate" or task_package_sha256(spec) != compare["task_package_sha256"]:
        raise ValueError("task contract differs from prior reference plan")
    public = ROOT / ".research/pr30_simplex_review_2026-09-11.json"
    report = {
        "schema_version": 1,
        "scope": "independent two-call revised-simplex plan; previous six calls unchanged; no baseline/reference reruns or new method search",
        "task_head": TASK_HEAD, "integration_head": BASE, "task_id": spec.task_id,
        "runtime_source_sha256": RUNTIME_HASH, "task_package_sha256": task_package_sha256(spec),
        "task_source_hashes": frozen, "driver_sha256": digest(Path(__file__).read_bytes()),
        "candidate_sha256": digest(source), "candidate_source_path": str((AUDIT / "exact_lp_revised_simplex.py").relative_to(ROOT)),
        "derivation": provenance,
        "loader_adapter": {"mapping": "ScientificComputing -> ComputerScience", "previous": previous, "in_memory_only": True},
        "runtime": {"python": sys.version, "executable": sys.executable, "platform": platform.platform(),
                    "numpy": np.__version__, "scipy": scipy.__version__,
                    "thread_environment": {key: os.environ.get(key) for key in (
                        "OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS")}},
        "timeout_seconds": 300.0, "planned_evaluations": 2,
        "raw_metrics_scope": "complete per-instance metrics private; only scalar and instance score aggregates public",
        "started_utc": datetime.now(timezone.utc).isoformat(), "runs": [],
    }
    write_json(public, report)
    full = []
    for repeat in (1, 2):
        with tempfile.TemporaryDirectory(prefix="sle_pr30_simplex_candidate_") as tmp:
            candidate = Path(tmp) / "solution.py"
            candidate.write_bytes(source)
            start = time.monotonic()
            metrics = evaluate_candidate(spec, candidate, timeout_s=300.0)
            elapsed = time.monotonic() - start
        write_json(private / ("exact_lp_revised_simplex_%d.json" % repeat), metrics)
        full.append(metrics)
        report["runs"].append({"repeat": repeat, "wall_seconds": elapsed,
                               "full_metrics_sha256": digest(metrics), **public_aggregate(metrics)})
        write_json(public, report)
        print(json.dumps({"repeat": repeat, "seconds": elapsed, "score": metrics.get("combined_score"),
                          "valid": metrics.get("valid"), "feasibility": metrics.get("feasibility_rate"),
                          "candidate_failure_kind": metrics.get("candidate_failure_kind"),
                          "infrastructure_failure": bool(metrics.get("infrastructure_failure"))}), flush=True)
    if sources() != frozen or runtime_source_sha256() != RUNTIME_HASH:
        raise ValueError("task/runtime changed during evaluation")
    report["completed_evaluations"] = 2
    report["scientifically_valid_evaluations"] = sum(run["outcome"]["scientific_score_available"] for run in report["runs"])
    report["full_metrics_repeat_identical"] = full[0] == full[1]
    report["finished_utc"] = datetime.now(timezone.utc).isoformat()
    write_json(public, report)


if __name__ == "__main__":
    main()
