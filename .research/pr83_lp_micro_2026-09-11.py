"""Data-free LP backend timing/compatibility; this fixture contains no task data."""
import time
import warnings

import numpy as np
from scipy.optimize import linprog


def solve_fixture(method):
    rng = np.random.default_rng(9183)
    a = rng.uniform(0.0, 1.0, (300, 24))
    b = a @ np.ones(24) + 0.25
    started = time.monotonic()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        result = linprog(-np.ones(24), A_ub=a, b_ub=b, bounds=[(0, 1)] * 24,
                         method=method, options={"tol": 1e-9, "maxiter": 1000})
    return {"status": int(result.status), "seconds": time.monotonic() - started,
            "fun": float(result.fun) if result.fun is not None else None,
            "max_error": float(np.max(np.abs(result.x - 1))) if result.x is not None else None}


if __name__ == "__main__":
    import argparse
    import hashlib
    import json
    import os
    import subprocess
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root))
    from sle.secure_eval import CandidateProxy, sanitized_candidate_failure
    from sle.algorithms.common import runtime_source_sha256

    parser = argparse.ArgumentParser()
    parser.add_argument("--private-root", type=Path, required=True)
    args = parser.parse_args()
    os.umask(0o077)
    args.private_root.mkdir(mode=0o700, exist_ok=False)
    report = {"scope": "engineering only; no task evaluations or model calls", "rows": [],
              "revision": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
              "runtime_source_sha256": runtime_source_sha256(),
              "fixture_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    for method in ("revised simplex", "interior-point"):
        for repeat in range(2):
            proxy = None
            row = {"method": method, "repeat": repeat}
            try:
                proxy = CandidateProxy(Path(__file__), "solve_fixture", timeout_s=30, memory_mb=4096)
                row["result"] = proxy(method)
            except Exception as exc:
                row["failure_kind"] = sanitized_candidate_failure(exc)["candidate_failure_kind"]
            finally:
                if proxy:
                    proxy.close(kill=True)
            report["rows"].append(row)
            print(json.dumps(row, sort_keys=True), flush=True)
    (args.private_root / "summary.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
