"""Replay PR46's corrected comparisons through the trusted Linux sandbox."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
TASK_ID = "Exoplanets/MicrolensingEventCharacterization"

BLANKET = '''
def infer_microlensing(problem, observe):
    ids = [observe(float(t), "r")["query_id"] for t in problem["candidate_times"][:6]]
    return {"abstain": True, "confidence": 0.5, "evidence_query_ids": ids}
'''


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    reference = (HERE / "reference_solver.py").read_text(encoding="utf-8")
    candidates = {
        "reference": reference,
        "reference_without_refusal": reference.replace(
            "return _infer(problem, observe)", "return _infer(problem, observe, refuse=False)"),
        "reference_sparse_cadence": reference.replace(
            "return _infer(problem, observe)", "return _infer(problem, observe, cadence_step=3)"),
        "baseline": (HERE.parent / "solution.py").read_text(encoding="utf-8"),
        "constant_shortcut": (HERE / "shortcut_constant.py").read_text(encoding="utf-8"),
        "textbook_fixed_source_shortcut": (HERE / "shortcut_textbook.py").read_text(encoding="utf-8"),
        "blanket_abstain": BLANKET,
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
