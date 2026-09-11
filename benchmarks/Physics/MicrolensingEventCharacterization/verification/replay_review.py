"""Replay PR46's corrected comparisons through the trusted Linux sandbox."""
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
TASK_ID = "Exoplanets/MicrolensingEventCharacterization"

UNCERTAINTY_POLICY = '''
def infer_microlensing(problem, observe):
    rows = [observe(float(t), "r") for t in problem["candidate_times"][:6]]
    ids = [row["query_id"] for row in rows]
    return {"abstain": rows[0]["uncertainty"] > 0.05, "confidence": 1.0,
            "model": "point_lens", "timescale_days": 10.0, "amplitude": 0.0,
            "evidence_query_ids": ids}
'''


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    reference = (HERE / "reference_solver.py").read_text(encoding="utf-8")
    analysis = (HERE / "analysis.py").read_text(encoding="utf-8")
    functions = {node.name: ast.get_source_segment(analysis, node)
                 for node in ast.parse(analysis).body if isinstance(node, ast.FunctionDef)}
    candidates = {
        "reference": reference,
        "reference_without_refusal": reference.replace(
            "return _infer(problem, observe)", "return _infer(problem, observe, refuse=False)"),
        "baseline": (HERE.parent / "solution.py").read_text(encoding="utf-8"),
        "weak_threshold_r_only": functions["threshold_policy"] + "\ninfer_microlensing = threshold_policy(use_g=False)\n",
        "weak_threshold_never_refuse": functions["threshold_policy"] + "\ninfer_microlensing = threshold_policy(refuse=False)\n",
        "blanket_abstain": functions["blanket"] + "\ninfer_microlensing = blanket\n",
        "uncertainty_threshold": UNCERTAINTY_POLICY,
    }
    report = {"task": TASK_ID, "execution": "Linux trusted driver and bubblewrap; no model generation",
              "source_revision": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
              "source_tree_clean": not bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True).strip()),
              "probes": {}}
    with tempfile.TemporaryDirectory(prefix="microlensing-review-") as tmp:
        for name, source in candidates.items():
            candidate = Path(tmp) / (name + ".py")
            candidate.write_text(source, encoding="utf-8")
            results = []
            for _ in range(2):
                run = subprocess.run([sys.executable, "-m", "sle", "eval", "--allow-uncertified",
                    "--task", TASK_ID, "--candidate", str(candidate)], cwd=ROOT,
                    capture_output=True, text=True, timeout=360)
                if run.returncode:
                    raise RuntimeError(run.stderr[-2000:])
                results.append(json.loads(run.stdout))
            if results[0] != results[1] or results[0]["valid"] != 1:
                raise AssertionError("invalid or nondeterministic: " + name)
            report["probes"][name] = {"complete_metrics_identical_twice": True, "metrics": results[0]}
            print(name, results[0]["combined_score"], results[0]["heldout_mechanism_score"],
                  results[0]["development_mean_budget_used"], flush=True)
    Path(args.output).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
