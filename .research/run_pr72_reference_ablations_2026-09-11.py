"""Six fixed current-source sandbox checks of the three already-declared ablations.

Run outside the frozen checkout, using --root to select that clean source. The
reference's ablation default is the only candidate change. No oracle imports,
model calls, new parameter searches or retries are made by this reviewer driver.
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

SOURCE_REVISION = "9516d4b0fc9ddcb6d2853ee7a39448fc851e549b"
REFERENCE_SHA256 = "78da166c44b216e3f69a492ba1a4aa605af0cc21d3223f2168196a9d68325d2c"
THREAD_KEYS = ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS")
ABLATIONS = ("one_unit", "ignore_gain", "fixed_halo")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def write_new(path, value):
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
    path.chmod(0o600)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--private-root", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    sys.path.insert(0, str(root))
    import numpy as np
    import scipy
    from sle.evaluate import evaluate_candidate
    from sle.registry import find_task

    def git(*words):
        return subprocess.check_output(["git", "-C", str(root), *words], text=True).strip()

    if (platform.system() != "Linux" or sys.version_info[:2] != (3, 8) or
            np.__version__ != "1.24.4" or scipy.__version__ != "1.10.1" or
            any(os.environ.get(key) != "1" for key in THREAD_KEYS)):
        raise SystemExit("fixed Linux Python 3.8 / NumPy 1.24.4 / SciPy 1.10.1 single-thread environment required")
    if git("rev-parse", "HEAD") != SOURCE_REVISION or git("status", "--porcelain"):
        raise SystemExit("specified clean source revision required")
    spec = find_task("ParticlePhysics/DarkMatterRecoilAttribution", include_uncertified=True)
    if spec.task_dir != root / "benchmarks/Physics/DarkMatterRecoilAttribution":
        raise SystemExit("unexpected logical task mapping")
    reference = (spec.task_dir / "verification/reference_profile.py").read_bytes()
    if sha(reference) != REFERENCE_SHA256 or reference.count(b"ablation=None") != 1:
        raise SystemExit("unchanged reference source required")
    paths = git("ls-files", "sle", "benchmarks/Physics/DarkMatterRecoilAttribution").splitlines()
    source_hashes = {path: sha((root / path).read_bytes()) for path in paths}
    private = args.private_root.resolve()
    private.mkdir(mode=0o700, parents=False, exist_ok=False)
    os.umask(0o077)
    records = []
    plan = {"schema_version": 1, "source_revision": SOURCE_REVISION,
            "source_hashes": source_hashes, "driver_sha256": sha(Path(__file__).read_bytes()),
            "reference_sha256": REFERENCE_SHA256, "ablations": list(ABLATIONS),
            "repeats_per_candidate": 2, "timeout_s": 300.0,
            "scope": "fixed existing reference ablations; no new parameter selection",
            "runtime": {"python": sys.version, "numpy": np.__version__, "scipy": scipy.__version__,
                        "platform": platform.platform(), "thread_environment": {k: os.environ[k] for k in THREAD_KEYS}}}
    write_new(private / "plan.json", plan)
    for ablation in ABLATIONS:
        source = reference.replace(b"ablation=None", ("ablation=%r" % ablation).encode(), 1)
        candidate = private / (ablation + ".py")
        candidate.write_bytes(source)
        candidate.chmod(0o600)
        for repeat in (1, 2):
            tick = time.monotonic()
            metrics = evaluate_candidate(spec, candidate, timeout_s=300.0)
            path = private / ("%s_%d.full_metrics.json" % (ablation, repeat))
            write_new(path, metrics)
            row = {"ablation": ablation, "repeat": repeat, "candidate_sha256": sha(source),
                   "derivation": {"before": "ablation=None", "after": "ablation=%r" % ablation},
                   "wall_seconds": time.monotonic() - tick,
                   "full_metrics_file_sha256": sha(path.read_bytes()),
                   "full_metrics_sha256": sha(canonical(metrics)),
                   "per_instance_sha256": sha(canonical(metrics.get("per_instance", []))),
                   "scalar_metrics": {k: v for k, v in metrics.items() if type(v) in (int, float, bool)}}
            records.append(row)
            write_new(private / ("%s_%d.receipt.json" % (ablation, repeat)), row)
            print(ablation, repeat, metrics.get("valid"), metrics.get("combined_score"), flush=True)
    unchanged = source_hashes == {path: sha((root / path).read_bytes()) for path in paths} and not git("status", "--porcelain")
    valid = all(row["scalar_metrics"].get("valid") == 1 and not row["scalar_metrics"].get("infrastructure_failure") for row in records)
    repeat_identical = all(records[i]["full_metrics_sha256"] == records[i+1]["full_metrics_sha256"] for i in (0, 2, 4))
    report = dict(plan, records=records, source_unchanged=unchanged, all_valid=valid,
                  all_repeats_identical=repeat_identical, evaluate_candidate_calls=len(records),
                  model_calls=0, new_parameter_configurations_searched=0, scientific_admission="not_assessed")
    write_new(private / "aggregate.json", report)
    print("complete", "all_valid", valid, "repeat_identical", repeat_identical, "source_unchanged", unchanged)
    return 0 if valid and repeat_identical and unchanged else 1


if __name__ == "__main__":
    raise SystemExit(main())
