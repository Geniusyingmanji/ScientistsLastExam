#!/usr/bin/env python3
"""Run the complete unittest suite and persist trusted machine-readable evidence."""

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
sys.path.insert(0, str(ROOT))

from sle.provenance import finalize_report_trust, source_provenance  # noqa: E402


SUMMARY_RE = re.compile(r"Ran (\d+) tests? in ([0-9.]+)s")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    command = [
        sys.executable,
        "-W", "error::ResourceWarning",
        "-m", "unittest", "discover", "-s", "tests", "-q",
    ]
    started_at = datetime.now(timezone.utc).isoformat()
    started = time.monotonic()
    proc = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
    wall_seconds = time.monotonic() - started
    completed_at = datetime.now(timezone.utc).isoformat()
    combined = (proc.stdout or "") + "\n" + (proc.stderr or "")
    matches = SUMMARY_RE.findall(combined)
    test_count = int(matches[-1][0]) if matches else 0
    unittest_seconds = float(matches[-1][1]) if matches else None
    unittest_ok = bool(re.search(r"(?m)^OK(?: \(skipped=\d+\))?$", combined))

    report = {
        "schema_version": 1,
        "trust_status": "TRUSTED_FULL_TEST_SUITE",
        "source_provenance": source_provenance(ROOT),
        "started_at": started_at,
        "completed_at": completed_at,
        "command": command,
        "environment": {"python": sys.version, "platform": platform.platform()},
        "wall_seconds": wall_seconds,
        "unittest_seconds": unittest_seconds,
        "returncode": proc.returncode,
        "test_count": test_count,
        "unittest_ok": unittest_ok,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
    }
    execution_passed = proc.returncode == 0 and test_count > 0 and unittest_ok
    finalize_report_trust(report, execution_passed)
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    print(json.dumps({
        key: report[key]
        for key in (
            "passed", "test_count", "unittest_seconds", "wall_seconds",
            "returncode", "trust_decision",
        )
    }, indent=2))
    print("Report: %s" % output)
    return 0 if execution_passed else (proc.returncode or 2)


if __name__ == "__main__":
    raise SystemExit(main())
