"""Bounded development-only engineering diagnostic; no task evaluation or score.

Derive a candidate only by replacing the numerical-failure exception with a
private LP export. Stop at the first such failure. The candidate retains exactly
the original algorithm, observations, parameters and solver; no truth is passed.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--head", required=True)
    p.add_argument("--private-root", type=Path, required=True)
    args = p.parse_args()
    root = args.root.resolve()
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    if head != args.head or subprocess.check_output(["git", "status", "--porcelain"], cwd=root):
        raise ValueError("clean pinned source required")
    sys.path.insert(0, str(root))
    from sle.secure_eval import CandidateProxy, sanitized_candidate_failure
    os.umask(0o077)
    private = args.private_root.resolve()
    if private == root or root in private.parents or private in root.parents:
        raise ValueError("private output must be outside checkout")
    private.mkdir(mode=0o700, exist_ok=False)
    task = root / "benchmarks/ComputerScience/ClockSyncInversion"
    source = (task / "verification/reference_envelope_lp.py").read_text()
    needle = 'raise RuntimeError("LP did not establish an optimum or infeasibility")'
    if source.count(needle) != 1:
        raise ValueError("expected one numerical failure branch")
    derived = source.replace(needle, 'raise CapturedLP({"status": int(result.status), "message": str(result.message), "c": c.tolist(), "A": A.tolist(), "b": b.tolist(), "bounds": bounds, "center": center.tolist(), "scale": scale.tolist()})')
    derived += '''
class CapturedLP(Exception):
    pass
_original_identify = identify
def identify(problem, exchange, wait):
    try:
        return _original_identify(problem, exchange, wait)
    except CapturedLP as exc:
        return {"engineering_lp_export": exc.args[0]}
'''
    candidate = private / "capture_candidate.py"
    candidate.write_text(derived)
    spec = importlib.util.spec_from_file_location("clock_capture_oracle", task / "verification/evaluator.py")
    oracle = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(oracle)
    report = {"scope": "development-only first numerical LP failure; no scoring", "source_revision": head,
              "source_candidate_sha256": sha(source.encode()), "derived_candidate_sha256": sha(derived.encode()),
              "runs": [], "captured": False}
    for index, world_spec in enumerate(oracle.DEVELOPMENT_WORLDS):
        world = oracle.make_world(world_spec)
        bench = oracle._Bench(world, world_spec["run_seed"])
        exchange, wait = bench.oracle()
        proxy = CandidateProxy(candidate, "identify", timeout_s=300, memory_mb=4096)
        started = time.monotonic()
        row = {}
        try:
            answer = proxy(oracle.public_problem(world), exchange, wait)
            payload = json.dumps(answer, sort_keys=True, allow_nan=False) + "\n"
            (private / ("answer_%d.json" % index)).write_text(payload)
            row.update(returned=True, answer_sha256=sha(payload.encode()))
            if isinstance(answer, dict) and "engineering_lp_export" in answer:
                report["captured"] = True
                (private / "failed_lp.json").write_text(json.dumps(answer["engineering_lp_export"], sort_keys=True) + "\n")
                row["solver_status"] = answer["engineering_lp_export"]["status"]
        except Exception as exc:
            row.update(returned=False, failure_kind=sanitized_candidate_failure(exc)["candidate_failure_kind"])
        finally:
            proxy.close(kill=True)
        row.update(seconds=time.monotonic() - started, probes_used=bench.used,
                   budget_violated=bench.violated)
        report["runs"].append(row)
        print(json.dumps(row, sort_keys=True), flush=True)
        if report["captured"] or not row["returned"]:
            break
    (private / "summary.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
