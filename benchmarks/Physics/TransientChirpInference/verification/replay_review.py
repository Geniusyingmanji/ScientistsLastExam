"""Validate selected public-input probes in the Linux trusted sandbox."""
from __future__ import annotations
import argparse
import ast
import json
from pathlib import Path
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
TASK_ID = "Gravitation/TransientChirpInference"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sweep", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    sweep = json.loads(Path(args.sweep).read_text())
    ref = (HERE / "reference_solver.py").read_text().replace("def infer_transient(", "def reference_infer_transient(")
    calibration = (HERE / "calibrate.py").read_text()
    names = {"_line_fit", "no_chirp_grid", "h1_only", "never_refuse", "threshold_policy",
             "sign_count_policy", "morphology_policy"}
    functions = [ast.get_source_segment(calibration, node) for node in ast.parse(calibration).body
                 if isinstance(node, ast.FunctionDef) and node.name in names]
    library = ref + "\n\n" + "\n\n".join(functions)
    library = library.replace("REFERENCE._fit_grid", "_fit_grid").replace(
        "REFERENCE.infer_transient", "reference_infer_transient")
    candidates = {name: library + "\ninfer_transient = " + entry + "\n"
                  for name, entry in (("reference", "reference_infer_transient"),
                      ("h1_only", "h1_only"), ("no_chirp_grid", "no_chirp_grid"),
                      ("never_refuse", "never_refuse"), ("maintainer_sign_count", "sign_count_policy()"))}
    for name, factory in (("shortcut_probe", "threshold_policy"),
                          ("sign_count_shortcut_probe", "sign_count_policy"),
                          ("morphology_shortcut_probe", "morphology_policy")):
        parameters = sweep[name]["best_parameters"]
        candidates[name] = library + "\ninfer_transient = %s(*%r)\n" % (factory, parameters)
    candidates["baseline"] = (HERE.parent / "solution.py").read_text()
    candidates["all_abstain"] = '''def infer_transient(problem, observe):
    ids = [observe(t, "H1")["query_id"] for t in problem["candidate_times"][:6]]
    return {"abstain": True, "confidence": 0.7, "evidence_query_ids": ids}
'''
    candidates["constant_slope"] = library + '''
def infer_transient(problem, observe):
    answer = reference_infer_transient(problem, observe)
    if not answer["abstain"]:
        answer["frequency_slope"] = 0.02
    return answer
'''
    report = {"source_revision": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
              "source_tree_clean": not bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True).strip()),
              "execution": "Linux trusted driver and bubblewrap", "task": TASK_ID, "probes": {}}
    with tempfile.TemporaryDirectory(prefix="chirp-review-") as tmp:
        for name, source in candidates.items():
            candidate = Path(tmp) / (name + ".py")
            candidate.write_text(source, encoding="utf-8")
            results = []
            for _ in range(2):
                result = subprocess.run([sys.executable, "-m", "sle", "eval", "--allow-uncertified",
                    "--task", TASK_ID, "--candidate", str(candidate)], cwd=ROOT,
                    capture_output=True, text=True, timeout=360)
                if result.returncode:
                    raise RuntimeError(result.stderr[-2000:])
                results.append(json.loads(result.stdout))
            if results[0] != results[1] or results[0]["valid"] != 1:
                raise AssertionError("invalid or nondeterministic: " + name)
            report["probes"][name] = {"complete_metrics_identical_twice": True, "metrics": results[0]}
            print(name, results[0]["combined_score"], results[0]["robustness_score"], flush=True)
    for name in ("maintainer_sign_count", "shortcut_probe", "sign_count_shortcut_probe",
                 "morphology_shortcut_probe"):
        if report["probes"][name]["metrics"]["combined_score"] >= report["probes"]["reference"]["metrics"]["combined_score"]:
            raise AssertionError("shortcut reaches reference: " + name)
    Path(args.output).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
