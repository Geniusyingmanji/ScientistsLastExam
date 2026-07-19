#!/usr/bin/env python3
"""Run the adversarial security suite and persist a machine-readable report."""

from __future__ import annotations

import argparse
import json
import platform
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEST_RE = re.compile(r"^(test_\S+) \(([^)]+)\) \.\.\. (ok|FAIL|ERROR|skipped .*)$")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    command = [sys.executable, "-W", "error::ResourceWarning", "-m", "unittest", "-v", "tests.test_secure_eval"]
    started_at = datetime.now(timezone.utc).isoformat()
    started = time.monotonic()
    proc = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
    duration = time.monotonic() - started
    combined = (proc.stdout or "") + (proc.stderr or "")
    tests = []
    for line in combined.splitlines():
        match = TEST_RE.match(line.strip())
        if match:
            tests.append({"name": match.group(1), "case": match.group(2), "status": match.group(3)})
    report = {
        "schema_version": 1,
        "trust_status": "TRUSTED_SECURE_EVAL",
        "started_at": started_at,
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "command": command,
        "environment": {"python": sys.version, "platform": platform.platform()},
        "duration_seconds": duration,
        "returncode": proc.returncode,
        "passed": proc.returncode == 0 and bool(tests),
        "test_count": len(tests),
        "tests": tests,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
    }
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("passed", "test_count", "duration_seconds", "returncode")}, indent=2))
    print("Report: %s" % output)
    return proc.returncode if tests else 2


if __name__ == "__main__":
    raise SystemExit(main())
