"""Record the standard task contribution gate without publishing full oracle metrics.

This is a reviewer-side recorder only. It wraps evaluate_candidate to persist its
unchanged return value; check_task owns all candidates, checks and repeat policy.
No model calls, parameter search, task changes or certification promotion occur.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np
import scipy
from scripts import check_task_contribution as gate

TASK = "ParticlePhysics/DarkMatterRecoilAttribution"
THREAD_KEYS = ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def canonical(data):
    return json.dumps(data, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def git(*args):
    return subprocess.check_output(["git", "-C", str(ROOT), *args], text=True).strip()


def source_hashes():
    paths = git("ls-files", "sle", "scripts/check_task_contribution.py",
                "scripts/shortcut_probe_contract.py", "scripts/check_evaluator_survives_bad_candidates.py",
                "benchmarks/Physics/DarkMatterRecoilAttribution", str(Path(__file__).resolve().relative_to(ROOT)))
    return {path: sha((ROOT / path).read_bytes()) for path in paths.splitlines()}


def write_new(path, value):
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
    path.chmod(0o600)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--private-root", type=Path, required=True)
    args = parser.parse_args()
    if platform.system() != "Linux" or sys.version_info[:2] != (3, 8):
        raise SystemExit("fixed Linux Python 3.8 environment required")
    if np.__version__ != "1.24.4" or scipy.__version__ != "1.10.1":
        raise SystemExit("fixed NumPy 1.24.4 / SciPy 1.10.1 environment required")
    if any(os.environ.get(key) != "1" for key in THREAD_KEYS):
        raise SystemExit("all four numerical thread limits must equal one")
    if git("status", "--porcelain"):
        raise SystemExit("clean source checkout required")
    private = args.private_root.resolve()
    private.mkdir(mode=0o700, parents=False, exist_ok=False)
    os.umask(0o077)
    sources = source_hashes()
    records = []
    started = time.time()
    original = gate.evaluate_candidate
    spec = gate.find_task(TASK, include_uncertified=True)
    if spec.task_dir != ROOT / "benchmarks/Physics/DarkMatterRecoilAttribution":
        raise SystemExit("unexpected logical task mapping")

    def recorded_evaluate(task_spec, candidate, **kwargs):
        index = len(records) + 1
        source = Path(candidate).read_bytes()
        tick = time.monotonic()
        metrics = original(task_spec, candidate, **kwargs)
        path = private / ("full_metrics_%02d.json" % index)
        write_new(path, metrics)
        try:
            candidate_path = str(Path(candidate).relative_to(spec.task_dir))
        except ValueError:
            candidate_path = "gate-generated-candidate"
        record = {"index": index, "candidate": candidate_path,
                  "candidate_sha256": sha(source), "timeout_s": kwargs["timeout_s"],
                  "wall_seconds": time.monotonic() - tick,
                  "full_metrics_file_sha256": sha(path.read_bytes()),
                  "full_metrics_sha256": sha(canonical(metrics)),
                  "per_instance_sha256": sha(canonical(metrics.get("per_instance", []))),
                  "scalar_metrics": {key: value for key, value in metrics.items()
                                     if type(value) in (int, float, bool)}}
        records.append(record)
        write_new(private / ("receipt_%02d.json" % index), record)
        print(index, candidate_path, metrics.get("valid"), metrics.get("combined_score"), flush=True)
        return metrics

    gate.evaluate_candidate = recorded_evaluate
    report = gate.check_task(TASK, timeout_s=300.0)
    unchanged = sources == source_hashes() and not git("status", "--porcelain")
    envelope = {"schema_version": 1, "task_id": TASK,
                "source_revision": git("rev-parse", "HEAD"), "source_hashes": sources,
                "source_unchanged": unchanged, "started_unix": started, "finished_unix": time.time(),
                "runtime": {"python": sys.version, "numpy": np.__version__, "scipy": scipy.__version__,
                            "platform": platform.platform(), "thread_environment": {k: os.environ[k] for k in THREAD_KEYS}},
                "expected_evaluate_candidate_calls": 13, "actual_evaluate_candidate_calls": len(records),
                "model_calls": 0, "new_parameter_configurations_searched": 0,
                "scientific_admission": "not_assessed", "records": records, "contribution_gate": report}
    write_new(private / "aggregate.json", envelope)
    write_new(private / "contribution.json", report)
    print("contribution", report["status"], report["phases"], "source_unchanged", unchanged, flush=True)
    return 0 if report["passed"] and unchanged and len(records) == 13 else 1


if __name__ == "__main__":
    raise SystemExit(main())
