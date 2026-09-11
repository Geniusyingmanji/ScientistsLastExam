"""Fixed candidate pairs for PR83; private full metrics, public scalar summary only."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import numpy as np
import scipy
from sle.algorithms.common import runtime_source_sha256, task_package_sha256
from sle.evaluate import evaluate_candidate
from sle.spec import load_task_spec

TASK = ROOT / "benchmarks/ComputerScience/ClockSyncInversion"
CANDIDATES = {
    "baseline": TASK / "solution.py",
    "reference": TASK / "verification/reference_envelope_lp.py",
    "detection_only": TASK / "verification/shortcut_detection_only.py",
    "no_order_rows": TASK / "verification/ablation_no_order_rows.py",
    "no_atom_rows": TASK / "verification/ablation_no_atom_rows.py",
}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def write_json(path, data):
    with path.open("x", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")
    path.chmod(0o600)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--head", required=True)
    parser.add_argument("--private-root", type=Path, required=True)
    parser.add_argument("--candidates", default="baseline,reference")
    args = parser.parse_args()
    names = args.candidates.split(",")
    if len(set(names)) != len(names) or any(name not in CANDIDATES for name in names):
        raise ValueError("candidate list must be distinct known programs")
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    dirty = subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=no"], cwd=ROOT, text=True)
    if revision != args.head or dirty:
        raise ValueError("expected a clean pinned revision")
    private = args.private_root.resolve()
    if private == ROOT or ROOT in private.parents or private in ROOT.parents:
        raise ValueError("private directory must be separate from checkout")
    os.umask(0o077)
    private.mkdir(mode=0o700, parents=True, exist_ok=False)
    spec = load_task_spec(TASK)
    before = task_package_sha256(spec)
    report = {
        "schema_version": 1, "scope": "fixed pairs, no model calls or parameter search",
        "source_revision": revision, "source_tree_clean": True,
        "task_id": spec.task_id, "task_package_sha256": before,
        "runtime_source_sha256": runtime_source_sha256(),
        "driver_sha256": digest(Path(__file__).read_bytes()),
        "python": platform.python_version(), "numpy": np.__version__, "scipy": scipy.__version__,
        "candidate_order": names, "repeats_per_candidate": 2, "timeout_seconds": 300,
        "thread_environment": {k: os.environ.get(k) for k in (
            "OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS")},
        "runs": [], "scientific_admission": "not_assessed",
    }
    write_json(private / "plan.json", report)
    for name in names:
        path = CANDIDATES[name]
        candidate_hash = digest(path.read_bytes())
        for repeat in range(2):
            start = time.monotonic()
            metrics = evaluate_candidate(spec, path, timeout_s=300)
            elapsed = time.monotonic() - start
            raw = private / (name + "-" + str(repeat) + ".json")
            write_json(raw, metrics)
            row = {
                "candidate": name, "repeat": repeat, "candidate_sha256": candidate_hash,
                "elapsed_seconds": elapsed, "raw_sha256": digest(raw.read_bytes()),
                "canonical_metrics_sha256": digest(json.dumps(metrics, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()),
                "metrics": {k: v for k, v in metrics.items() if type(v) in (int, float, bool)},
                "candidate_failure_kind": metrics.get("candidate_failure_kind"),
                "valid_worlds": sum(bool(r.get("valid")) for r in metrics.get("per_instance", [])),
                "world_count": len(metrics.get("per_instance", [])),
            }
            report["runs"].append(row)
            print(json.dumps(row, sort_keys=True, allow_nan=False), flush=True)
    if task_package_sha256(spec) != before:
        raise ValueError("task sources changed during evaluation")
    report["repeat_metrics_identical"] = {
        name: len({r["canonical_metrics_sha256"] for r in report["runs"] if r["candidate"] == name}) == 1
        for name in names
    }
    write_json(private / "summary.json", report)


if __name__ == "__main__":
    main()
