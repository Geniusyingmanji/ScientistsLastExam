"""Source provenance shared by machine-readable experiment reports."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any, Optional, Sequence


REPO_ROOT = Path(__file__).resolve().parent.parent
SOURCE_SCOPE = (
    "frontier_science", "scripts", "tests", "benchmarks", "requirements-upstream.txt"
)


def _git(args: Sequence[str], root: Path) -> str:
    try:
        return subprocess.check_output(
            ["git", *args], cwd=str(root), text=True, stderr=subprocess.DEVNULL
        ).rstrip("\r\n")
    except (OSError, subprocess.CalledProcessError):
        return ""


def source_provenance(
    root: Path = REPO_ROOT,
    command: Optional[Sequence[str]] = None,
) -> dict[str, Any]:
    """Return the commit and scoped source-tree state used by an experiment.

    Experiment outputs and narrative notes are deliberately outside ``SOURCE_SCOPE`` so
    writing a report does not mark its own source as dirty. Any code, task, or dependency
    change is retained verbatim in ``source_changes`` and prevents a clean-source claim.
    """
    root = Path(root).resolve()
    revision = _git(["rev-parse", "HEAD"], root)
    status = _git(
        ["status", "--porcelain=v1", "--untracked-files=all", "--", *SOURCE_SCOPE], root
    )
    changes = [line for line in status.splitlines() if line.strip()]
    return {
        "git_available": bool(revision),
        "git_revision": revision or "unknown",
        "source_tree_dirty": bool(changes) if revision else None,
        "source_changes": changes,
        "source_scope": list(SOURCE_SCOPE),
        "command": list(command or [sys.executable, *sys.argv]),
    }


def finalize_report_trust(report: dict[str, Any], execution_passed: bool) -> bool:
    """Attach uniform execution/trust status and return the execution status.

    A report may be useful for debugging when its execution succeeds on a dirty tree, but it
    is benchmark evidence only when the scoped source tree is a clean, known Git revision.
    ``trust_status`` is retained as the report/evidence class for compatibility; the
    authoritative trust decision is ``trusted_evidence`` and its machine-readable reason is
    ``trust_decision``.
    """
    provenance = report.get("source_provenance") or {}
    report["execution_passed"] = bool(execution_passed)
    if not execution_passed:
        trust_decision = "execution_failed"
    elif provenance.get("git_available") is not True:
        trust_decision = "git_unavailable"
    elif provenance.get("git_revision") in {None, "", "unknown"}:
        trust_decision = "unknown_revision"
    elif provenance.get("source_tree_dirty") is not False:
        trust_decision = "source_tree_dirty_or_unknown"
    else:
        trust_decision = "trusted_clean_revision"
    report["trust_decision"] = trust_decision
    report["trusted_evidence"] = trust_decision == "trusted_clean_revision"
    report["passed"] = report["trusted_evidence"]
    return report["execution_passed"]
