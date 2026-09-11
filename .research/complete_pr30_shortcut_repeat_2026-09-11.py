"""Complete only the sixth frozen PR30 run after the first LP worker exit."""
from __future__ import annotations

import importlib.util
import json
import stat
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DRIVER = ROOT / ".research/audit_pr30_shortcuts_2026-09-11.py"
loader = importlib.util.spec_from_file_location("pr30_initial_driver", DRIVER)
audit = importlib.util.module_from_spec(loader)
loader.loader.exec_module(audit)


def main():
    private = Path(sys.argv[1]).resolve()
    if private == ROOT or ROOT in private.parents or stat.S_IMODE(private.stat().st_mode) != 0o700:
        raise ValueError("private evidence root must remain outside checkout and 0700")
    public = ROOT / ".research/pr30_shortcut_review_2026-09-11.json"
    report = json.loads(public.read_text())
    name = "exact_lp_public_adapter"
    rows = report["candidates"]
    if {key: len(row["runs"]) for key, row in rows.items()} != {"baseline": 2, "reference": 2, name: 1}:
        raise ValueError("only the sixth predeclared run may be completed")
    first_path = private / (name + "_1.json")
    second_path = private / (name + "_2.json")
    if second_path.exists():
        raise ValueError("refuse to overwrite sixth run")
    first = json.loads(first_path.read_text())
    if first.get("candidate_failure_kind") != "candidate_worker_exit":
        raise ValueError("unexpected initial failure classification")
    if audit.digest(first) != rows[name]["runs"][0]["full_metrics_sha256"]:
        raise ValueError("initial private evidence changed")
    if audit.digest(DRIVER.read_bytes()) != report["driver_sha256"]:
        raise ValueError("initial driver source changed")
    if audit.subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip() != audit.BASE:
        raise ValueError("runtime revision changed")
    if audit.sources() != report["task_source_hashes"] or audit.runtime_source_sha256() != report["runtime_source_sha256"]:
        raise ValueError("task/runtime changed")
    if sys.version_info[:3] != (3, 8, 10) or audit.np.__version__ != "1.24.4" or audit.scipy.__version__ != "1.10.1":
        raise ValueError("environment changed")
    if any(audit.os.environ.get(key) != "1" for key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS")):
        raise ValueError("thread environment changed")
    candidate_source = (ROOT / rows[name]["source_path"]).read_bytes()
    if audit.digest(candidate_source) != rows[name]["candidate_sha256"]:
        raise ValueError("candidate changed")
    audit.benchmark_layout.DOMAIN_DISCIPLINES["ScientificComputing"] = "ComputerScience"
    spec = audit.load_task_spec(audit.TASK)
    audit.os.umask(0o077)
    with tempfile.TemporaryDirectory(prefix="sle_pr30_candidate_") as temporary:
        candidate = Path(temporary) / "solution.py"
        candidate.write_bytes(candidate_source)
        started = time.monotonic()
        metrics = audit.evaluate_candidate(spec, candidate, timeout_s=300.0)
        elapsed = time.monotonic() - started
    audit.write_json(second_path, metrics)
    rows[name]["runs"].append({"repeat": 2, "wall_seconds": elapsed,
                               **audit.public_aggregate(metrics), "full_metrics_sha256": audit.digest(metrics)})
    for run, complete in zip(rows[name]["runs"], (first, metrics)):
        run["outcome"] = {"candidate_failure_kind": complete.get("candidate_failure_kind"),
                          "infrastructure_failure": bool(complete.get("infrastructure_failure")),
                          "scientific_score_available": complete.get("valid") == 1 and complete.get("feasibility_rate") == 1}
    rows[name]["full_metrics_repeat_identical"] = first == metrics
    report["completion_driver_sha256"] = audit.digest(Path(__file__).read_bytes())
    report["completion_reason"] = "original driver stopped after fifth evaluation on LP worker exit; only the same-source sixth planned repeat was resumed"
    report["completed_evaluations"] = 6
    report["scientifically_valid_evaluations"] = sum(run["metrics"].get("valid") == 1 and run["metrics"].get("feasibility_rate") == 1 for row in rows.values() for run in row["runs"])
    report["all_repeats_identical"] = all(row["full_metrics_repeat_identical"] for row in rows.values())
    report["all_candidates_scientifically_valid"] = report["scientifically_valid_evaluations"] == 6
    report["finished_utc"] = datetime.now(timezone.utc).isoformat()
    audit.write_json(public, report)
    print(json.dumps({"candidate": name, "repeat": 2, "seconds": elapsed,
                      "candidate_failure_kind": metrics.get("candidate_failure_kind"),
                      "valid": metrics.get("valid"), "feasibility": metrics.get("feasibility_rate"),
                      "infrastructure_failure": bool(metrics.get("infrastructure_failure")),
                      "repeat_identical": first == metrics}), flush=True)


if __name__ == "__main__":
    main()
