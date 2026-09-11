"""Check that the joint-noise null correction preserves recorded policy metrics.

This is historical compatibility evidence, not an assertion that the old null was
scientifically adequate. It avoids mislabelling earlier subset measurements as
runs on a later source revision.
"""
import argparse
import hashlib
import itertools
import json
import subprocess
import types

from audit_fwi_revision import ROOT, TASK, load


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    relative = "benchmarks/EarthScience/ActiveFullWaveformInversion/verification/evaluator.py"
    old_source = subprocess.check_output(["git", "show", "c3dccc4:" + relative], cwd=ROOT, text=True)
    old = types.ModuleType("pre_joint_noise_oracle")
    exec(compile(old_source, "pre_joint_noise_oracle", "exec"), old.__dict__)
    new = load(TASK / "verification/evaluator.py", "joint_noise_oracle")
    ref = load(TASK / "verification/reference_solver.py", "null_reference")
    baseline = load(TASK / "solution.py", "null_baseline")
    methods = {"reference": ref.invert_velocity_model, "baseline": baseline.invert_velocity_model}
    for size in (1, 2, 3):
        for indices in itertools.combinations(range(5), size):
            def candidate(*inputs, indices=indices):
                values = list(inputs)
                values[4] = values[4][list(indices)]
                values[-1] = len(indices)
                return ref.invert_velocity_model(*values)
            methods["subset_" + "_".join(map(str, indices))] = candidate
    for name, count, stop, depth in (("one", 1, 0, 1), ("three", 3, 0, 1),
                                    ("stop", 5, 5, 1), ("depth", 5, 5, .7)):
        probe = load(ROOT / ".research/pr20_fwi_continuous_probe.py", name)
        probe.LENSES, probe.STOP_NOISE, probe.DEPTH_CAP = count, stop, depth
        # Early null refusal also applies before the swept final-fit threshold.
        probe.THRESHOLD = float("inf")
        methods[name] = probe.invert_velocity_model
    cases = [s for s in new.DEVELOPMENT_SPECS + new.HELDOUT_SPECS if s[1] == "null"]
    cases += [(61201, "null", 0), (71201, "null", 0)]
    comparisons = []
    for name, candidate in methods.items():
        for index, spec in enumerate(cases):
            a = old._evaluate_world(candidate, spec, "null_compatibility", index)
            b = new._evaluate_world(candidate, spec, "null_compatibility", index)
            assert a == b and b["valid"], (name, spec, a, b)
            comparisons.append({"method": name, "spec": spec, "identical": True})
    report = {
        "old_revision": "c3dccc4", "old_oracle_sha256": hashlib.sha256(old_source.encode()).hexdigest(),
        "revision": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "new_oracle_sha256": hashlib.sha256((TASK / "verification/evaluator.py").read_bytes()).hexdigest(),
        "dirty": bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True).strip()),
        "comparisons": comparisons,
    }
    with open(args.output, "w") as handle:
        json.dump(report, handle, indent=2)
    print(len(comparisons), "identical policy-metric comparisons")


if __name__ == "__main__":
    main()
