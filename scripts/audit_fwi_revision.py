"""Reproduce the FWI review families without hiding failed admission checks.

Run on a clean Linux checkout for publishable measurements. Default runs the
reference and four continuous Gaussian probes. --budget-sweep tests all five
single shots and ten pairs, without selecting source positions using heldout.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import itertools
import json
import platform
import subprocess
import time
from pathlib import Path

import numpy as np
import scipy

ROOT = Path(__file__).resolve().parents[1]
TASK = ROOT / "benchmarks/EarthScience/ActiveFullWaveformInversion"


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def bootstrap(metrics):
    """Stratified world bootstrap, including uncertainty in refusal outcomes.

    Percentile intervals describe this small procedural sample only. They do not
    certify new geology, server-hidden instances, or frontier-model difficulty.
    """
    report = {}
    for split in ("development", "heldout"):
        rows = [r for r in metrics["per_world"] if r["split"] == split]
        key = "supported_world_count" if split == "development" else "heldout_supported_world_count"
        n = metrics[key]
        # The evaluator keeps supported specs first; assert this in its tests.
        supported = np.asarray([r["mechanism_score"] for r in rows[:n]])
        unsupported = np.asarray([r["mechanism_score"] for r in rows[n:]])
        rng = np.random.default_rng(90113)
        draws = (rng.choice(supported, (20000, n)).sum(axis=1)
                 + rng.choice(unsupported, (20000, len(unsupported))).sum(axis=1)
                 - len(unsupported)) / n
        report[split] = {
            "supported_count": n,
            "supported_mean": float(supported.mean()),
            "supported_standard_error": float(supported.std(ddof=1) / np.sqrt(n)),
            "normalized_percentile_95": np.quantile(np.clip(draws, 0, 1), [.025, .975]).tolist(),
        }
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--methods", nargs="+", default=["reference", "gaussian_one", "gaussian_three", "gaussian_stop", "gaussian_depth"])
    parser.add_argument("--budget-sweep", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--fresh", action="store_true", help="use predeclared confirmation seeds, without retuning")
    args = parser.parse_args()
    oracle = load(TASK / "verification/evaluator.py", "audit_oracle")
    if args.fresh:
        oracle.DEVELOPMENT_SPECS = tuple((61001 + 17*i, "supported", i) for i in range(10)) + (
            (61201, "null", 0), (61217, "misspecified", 1), (61231, "structured_attenuation", 2))
        oracle.HELDOUT_SPECS = tuple((71003 + 19*i, "supported", i) for i in range(10)) + (
            (71201, "null", 0), (71217, "misspecified", 1), (71231, "structured_attenuation", 2))
    reference = load(TASK / "verification/reference_solver.py", "audit_reference")
    baseline = load(TASK / "solution.py", "audit_baseline")
    methods = {"baseline": baseline.invert_velocity_model,
               "reference": reference.invert_velocity_model}
    finite = load(TASK / "verification/reference_solver.py", "audit_finite_difference")
    finite._USE_EXACT_JACOBIAN = False
    exact = load(TASK / "verification/reference_solver.py", "audit_exact")
    exact._USE_EXACT_JACOBIAN = True
    methods["exact_jacobian"] = exact.invert_velocity_model
    methods["finite_difference"] = finite.invert_velocity_model
    for name, count, stop, depth in (
        ("gaussian_one", 1, 0, 1), ("gaussian_three", 3, 0, 1),
        ("gaussian_stop", 5, 5, 1), ("gaussian_depth", 5, 5, .7),
    ):
        probe = load(ROOT / ".research/pr20_fwi_continuous_probe.py", name)
        probe.LENSES, probe.STOP_NOISE, probe.DEPTH_CAP = count, stop, depth
        methods[name] = probe.invert_velocity_model
    for count in (1, 2):
        for indices in itertools.combinations(range(len(oracle.SOURCE_INDICES)), count):
            name = "shots_" + "_".join(str(oracle.SOURCE_INDICES[i]) for i in indices)

            def candidate(*inputs, indices=indices):
                values = list(inputs)
                values[4] = values[4][list(indices)]
                values[-1] = len(indices)
                return reference.invert_velocity_model(*values)

            methods[name] = candidate
            if args.budget_sweep:
                args.methods.append(name)
    sources = [TASK / "verification/evaluator.py", TASK / "verification/reference_solver.py",
               ROOT / ".research/pr20_fwi_continuous_probe.py", Path(__file__)]
    hashes = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
    report = {
        "scope": "procedural_review_diagnostics_not_frontier_calibration",
        "platform": platform.platform(), "numpy": np.__version__, "scipy": scipy.__version__,
        "revision": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "dirty": bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True).strip()),
        "source_sha256": hashes, "results": {},
        "fresh_confirmation": args.fresh,
        "development_specs": oracle.DEVELOPMENT_SPECS,
        "heldout_specs": oracle.HELDOUT_SPECS,
    }
    if args.resume and args.output.exists():
        previous = json.loads(args.output.read_text())
        if previous["source_sha256"] != hashes or previous["fresh_confirmation"] != args.fresh:
            raise ValueError("Refusing to combine measurements from different sources")
        report = previous
    args.output.parent.mkdir(parents=True, exist_ok=True)
    for name in args.methods:
        if name in report["results"]:
            continue
        start = time.monotonic()
        metrics = oracle.evaluate(methods[name])
        metrics["wall_seconds"] = time.monotonic() - start
        metrics["sampling_uncertainty"] = bootstrap(metrics)
        report["results"][name] = metrics
        # Record failure just as readily as success. No bound is relaxed here.
        ref = report["results"].get("reference")
        if ref:
            report["continuous_probe_gate"] = {
                name: all(ref[k] > result[k] + .15 and result[k] < .7 * ref[k]
                          for k in ("combined_score", "robustness_score"))
                for name, result in report["results"].items() if name.startswith("gaussian_")
            }
        args.output.write_text(json.dumps(report, indent=2) + "\n")
        print(name, metrics["combined_score"], metrics["robustness_score"],
              metrics["wall_seconds"], flush=True)


if __name__ == "__main__":
    main()
