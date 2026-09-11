"""Replay exactly four frozen PR72 candidates twice in the integrated sandbox.

No author driver import, search, model calls, or heldout parameter selection.
Full per-world metrics stay in a 0700 directory outside this checkout.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import math
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
RUNTIME_HASH = "8159a99d54894dd304e3ac48956cd05d4389f12a041f5d5d86a2c079641c2c86"
TASK_HEAD = "8497bd455d3090087e6a15e99fb85f5fae75e5cd"
TASK = ROOT / "benchmarks/Physics/DarkMatterRecoilAttribution"
AUDIT = ROOT / ".research/pr72_shortcut_candidates_2026-09-11"
THREAD_KEYS = ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS")


def digest(value):
    if not isinstance(value, bytes):
        value = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return hashlib.sha256(value).hexdigest()


def sources():
    return {str(path.relative_to(TASK)): digest(path.read_bytes())
            for path in sorted(TASK.rglob("*"))
            if path.is_file() and "__pycache__" not in path.parts}


def write_json(path, value, private=False):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")
    if private:
        temporary.chmod(0o600)
    temporary.replace(path)


def function_sources(source):
    return {node.name: ast.get_source_segment(source, node)
            for node in ast.parse(source).body if isinstance(node, ast.FunctionDef)}


def verify_derivation(provenance, reference, fixed_mass, four_way):
    mass = provenance["fixed_mass_57_8"]
    old, new = mass["replace_before"].encode(), mass["replace_after"].encode()
    if not (old == b'"mass_gev": best[2]' and new == b'"mass_gev": 57.8'
            and reference.count(old) == 1 and fixed_mass == reference.replace(old, new)
            and digest(fixed_mass) == mass["candidate_sha256"]):
        raise ValueError("fixed-mass candidate differs from the disclosed replacement")
    probe = provenance["published_four_way_probe"]
    functions = function_sources(four_way.decode())
    if set(functions) != {"peak_features", "probe_answer", "infer_recoil"}:
        raise ValueError("unexpected four-way candidate functions")
    for helper in probe["functions"]:
        if digest(functions[helper["name"]].encode()) != helper["sha256"]:
            raise ValueError("four-way helper bytes differ from the author source segment")
    if not (probe["fixed_config"] == [1, 1, 60, 2, 95.83680934806682, 1, 0.5]
            and digest(four_way) == probe["candidate_sha256"]):
        raise ValueError("four-way candidate differs from the frozen configuration")


def denominators(metrics):
    result = {}
    for split in ("development", "heldout"):
        rows = [row for row in metrics["per_instance"] if row["split"] == split]
        if len(rows) != 28:
            raise ValueError("unexpected split denominator")
        supported = [r for r in rows if r["kind"] in ("contact", "q2")]
        null = [r for r in rows if r["kind"] == "none"]
        refusal = [r for r in rows if r["kind"] == "unsupported"]
        if (len(supported), len(null), len(refusal)) != (20, 4, 4):
            raise ValueError("unexpected task class counts")
        result[split] = {
            "world_count": len(rows),
            "mechanism_utility_sum": sum(r["mechanism"] for r in rows),
            "mechanism_utility_mean": sum(r["mechanism"] for r in rows) / len(rows),
            "positive_claim_count": sum(r["claim"] for r in rows),
            "false_claim_count": sum(r["false_claim"] for r in rows),
            "correct_refusal_count": sum(r["correct_refusal"] for r in rows),
            "refusal_world_count": len(refusal),
            "supported_claim_count": sum(r["claim"] for r in supported),
            "supported_world_count": len(supported),
            "null_correct_count": sum(r["model"] == "none" for r in null),
            "null_world_count": len(null),
            "valid_world_count": sum(r["valid"] for r in rows),
            "charged_experiment_units_sum": sum(r["units"] for r in rows),
        }
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--private-root", type=Path, required=True)
    args = parser.parse_args()
    private = args.private_root.resolve()
    public = ROOT / ".research/pr72_shortcut_review_2026-09-11.json"
    if private == ROOT or ROOT in private.parents:
        raise ValueError("private evidence must be outside checkout")
    if public.exists() or private.exists():
        raise ValueError("refusing to overwrite or rerun an existing fixed campaign")
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    if revision != BASE or runtime_source_sha256() != RUNTIME_HASH:
        raise ValueError("wrong integration source revision or runtime bytes")
    if not (platform.system() == "Linux" and sys.version_info[:2] == (3, 8)
            and sys.executable == "/usr/bin/python3" and np.__version__ == "1.24.4"
            and scipy.__version__ == "1.10.1" and all(os.environ.get(k) == "1" for k in THREAD_KEYS)):
        raise ValueError("wrong scientific environment")
    expected = json.loads((ROOT / ".research/pr72_task_sources_2026-09-11.json").read_text())
    if sources() != expected:
        raise ValueError("task differs from the frozen PR72 archive")
    provenance = json.loads((AUDIT / "source_provenance.json").read_text())
    candidates = {
        "baseline": TASK / "solution.py",
        "reference": TASK / "verification/reference_profile.py",
        "fixed_mass_57_8": AUDIT / "fixed_mass_57_8.py",
        "published_four_way_probe": AUDIT / "published_four_way_probe.py",
    }
    frozen = {name: path.read_bytes() for name, path in candidates.items()}
    verify_derivation(provenance, frozen["reference"], frozen["fixed_mass_57_8"], frozen["published_four_way_probe"])
    # Verify the logical ID mapping explicitly; do not infer identity from the
    # physical path or copy any of the PR's older runtime files.
    if benchmark_layout.DOMAIN_DISCIPLINES.get("ParticlePhysics") != "Physics":
        raise ValueError("ParticlePhysics must explicitly map to Physics")
    spec = load_task_spec(TASK)
    if spec.task_id != "ParticlePhysics/DarkMatterRecoilAttribution":
        raise ValueError("unexpected logical task identity")
    private.mkdir(mode=0o700, parents=True)
    private.chmod(0o700)
    report = {
        "schema_version": 1, "status": "running", "attempted_evaluations": 0, "completed_evaluations": 0,
        "scope": "fixed disclosed strategy replay; no grid, model call or heldout selection",
        "model_calls": 0, "new_parameter_configurations_searched": 0,
        "task_head": TASK_HEAD, "integration_head": BASE, "task_id": spec.task_id,
        "runtime_source_sha256": RUNTIME_HASH, "task_package_sha256": task_package_sha256(spec),
        "task_source_hashes": expected,
        "driver_sha256": digest(Path(__file__).read_bytes()),
        "loader_adapter": "existing ParticlePhysics -> Physics mapping explicitly verified; no mapping or runtime file change",
        "derivation": provenance, "started_utc": datetime.now(timezone.utc).isoformat(),
        "runtime": {"python": sys.version, "executable": sys.executable, "platform": platform.platform(),
                    "numpy": np.__version__, "scipy": scipy.__version__,
                    "thread_environment": {k: os.environ.get(k) for k in THREAD_KEYS}},
        "timeout_seconds": 300.0, "candidate_order": list(candidates), "repeats_per_candidate": 2,
        "planned_evaluations": 8, "candidate_plan_sha256": {name: digest(src) for name, src in frozen.items()},
        "axes": {
            "mechanism_score": "reported; normalized utility couples correct positive law with mass recovery",
            "parameter_recovery_score": "not separately reported by this oracle; do not infer an independent axis",
            "prediction_score": "not reported by this oracle",
            "aggregate_precision": "oracle split aggregates rounded to 10 decimals; private rows retain returned precision",
        },
        "scientific_admission": "not assessed; fixed probes do not establish general difficulty or independent calibration",
        "candidates": {},
    }
    write_json(public, report)
    for name, source in frozen.items():
        record = {"source_path": str(candidates[name].relative_to(ROOT)), "candidate_sha256": digest(source),
                  "paid_query_calls": {"observed": None, "status": "oracle does not report callback count",
                                       "source_derived_expected_per_world": 3 if name in ("reference", "fixed_mass_57_8") else 1},
                  "runs": []}
        report["candidates"][name] = record
        full = []
        for repeat in range(1, 3):
            started = time.monotonic()
            try:
                with tempfile.TemporaryDirectory(prefix="sle_pr72_candidate_") as temporary:
                    candidate = Path(temporary) / "solution.py"
                    candidate.write_bytes(source)
                    report["attempted_evaluations"] += 1
                    write_json(public, report)
                    metrics = evaluate_candidate(spec, candidate, timeout_s=300.0)
                elapsed = time.monotonic() - started
                report["completed_evaluations"] += 1
                path = private / ("%s_%d.json" % (name, repeat))
                write_json(path, metrics, private=True)
                if metrics.get("infrastructure_failure") or "per_instance" not in metrics:
                    raise RuntimeError("secure evaluator did not return scientific metrics")
                counts = denominators(metrics)
                scalar_metrics = {key: value for key, value in metrics.items()
                                  if type(value) in (int, float) and math.isfinite(value)}
                record["runs"].append({"repeat": repeat, "wall_seconds": elapsed,
                                       "metrics": scalar_metrics, "denominators": counts,
                                       "full_metrics_sha256": digest(metrics),
                                       "full_metrics_file_sha256": digest(path.read_bytes()),
                                       "per_instance_sha256": digest(metrics["per_instance"])})
                full.append(metrics)
                write_json(public, report)
                print(json.dumps({"candidate": name, "repeat": repeat, "seconds": round(elapsed, 3),
                                  "valid": metrics.get("valid"), "dev": metrics.get("development_mechanism_score"),
                                  "heldout": metrics.get("heldout_mechanism_score")}), flush=True)
            except Exception as exc:
                report["status"] = "execution_failed"
                report["failure"] = {"candidate": name, "repeat": repeat, "exception_type": type(exc).__name__}
                write_json(public, report)
                raise
        record["full_metrics_repeat_identical"] = full[0] == full[1]
        record["all_worlds_valid"] = all(m.get("valid") == 1 for m in full)
        write_json(public, report)
    report["task_sources_unchanged"] = sources() == expected
    report["runtime_source_unchanged"] = runtime_source_sha256() == RUNTIME_HASH
    report["candidate_sources_unchanged"] = all(candidates[n].read_bytes() == src for n, src in frozen.items())
    report["all_repeats_identical"] = all(r["full_metrics_repeat_identical"] for r in report["candidates"].values())
    report["all_worlds_valid"] = all(r["all_worlds_valid"] for r in report["candidates"].values())
    report["status"] = "completed" if all(report[key] for key in (
        "task_sources_unchanged", "runtime_source_unchanged", "candidate_sources_unchanged",
        "all_repeats_identical", "all_worlds_valid")) else "verification_failed"
    report["finished_utc"] = datetime.now(timezone.utc).isoformat()
    write_json(public, report)
    return 0 if report["status"] == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
