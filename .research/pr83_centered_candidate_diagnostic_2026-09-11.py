"""First-development-world candidate execution for engineering diagnosis, without scoring.

The trusted driver supplies the same allowed problem and paid callbacks as the
task. It never calls _metrics/evaluate, never inspects truth in the candidate and
does not change the candidate's scientific parameters. Full answers stay private.
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

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from sle.secure_eval import CandidateProxy, sanitized_candidate_failure


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--head", required=True)
    parser.add_argument("--private-root", type=Path, required=True)
    args = parser.parse_args()
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    if head != args.head or subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT):
        raise SystemExit("clean specified source required")
    task = ROOT / "benchmarks/ComputerScience/ClockSyncInversion"
    spec = importlib.util.spec_from_file_location("clock_engineering_oracle", task / "verification/evaluator.py")
    oracle = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(oracle)
    os.umask(0o077)
    args.private_root.mkdir(mode=0o700, exist_ok=False)
    candidate = task / "verification/reference_envelope_lp.py"
    digest = hashlib.sha256(candidate.read_bytes()).hexdigest()
    report = {"scope": "first public-world candidate execution only; no task score or model call",
              "source_revision": head, "candidate_sha256": digest, "rows": []}
    for repeat in (1, 2):
        source_spec = oracle.DEVELOPMENT_WORLDS[0]
        world = oracle.make_world(source_spec)
        bench = oracle._Bench(world, source_spec["run_seed"])
        proxy = None
        row = {"repeat": repeat}
        started = time.monotonic()
        try:
            proxy = CandidateProxy(candidate, "identify", timeout_s=300, memory_mb=4096)
            exchange, wait = bench.oracle()
            answer = proxy(oracle.public_problem(world), exchange, wait)
            path = args.private_root / ("answer_%d.json" % repeat)
            path.write_text(json.dumps(answer, sort_keys=True, allow_nan=False) + "\n")
            row.update(returned=True, answer_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                       verdict=answer.get("verdict") if isinstance(answer, dict) else None)
        except Exception as exc:
            row.update(returned=False, exception_type=type(exc).__name__,
                       failure_kind=sanitized_candidate_failure(exc)["candidate_failure_kind"])
            (args.private_root / ("error_%d.json" % repeat)).write_text(json.dumps({"message": str(exc)}) + "\n")
        finally:
            if proxy is not None:
                proxy.close(kill=True)
        row.update(seconds=time.monotonic()-started, probes_used=bench.used, budget_violated=bench.violated)
        report["rows"].append(row)
        print(json.dumps(row, sort_keys=True), flush=True)
    (args.private_root / "summary.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    return 0 if all(row["returned"] and not row["budget_violated"] for row in report["rows"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
