"""Version-bound eligibility for frontier discovery claims, separate from scores.

Historical packages remain executable. A candidate's score cannot confer frontier
eligibility, nor can an edit or a new task name inherit an older qualification.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "sle/conf/discovery_eligibility.yaml"
STATUSES = {
    "retired_saturated", "quarantined_shortcut", "quarantined_provisional",
    "calibration_required", "qualified",
}
EXCLUSION_STATUSES = {"retired_saturated", "quarantined_shortcut", "quarantined_provisional"}
QUALIFICATION_CHECKS = (
    "repeated_frontier_calibration", "independent_confirmation_worlds",
    "degenerate_controls_below_ceiling", "scientific_validity",
    "process_result_verification", "material_headroom",
)
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def load_discovery_eligibility(path: Path | None = None) -> dict[str, Any]:
    document = yaml.safe_load((path or POLICY_PATH).read_text(encoding="utf-8"))
    if (not isinstance(document, dict) or document.get("schema_version") != 1
            or document.get("default_discovery_status") != "calibration_required"
            or not isinstance(document.get("tasks"), dict)):
        raise ValueError("invalid discovery eligibility policy")
    for task_id, record in document["tasks"].items():
        if (not isinstance(task_id, str) or "/" not in task_id
                or not isinstance(record, dict) or record.get("status") not in STATUSES
                or not isinstance(record.get("reason"), str) or not record["reason"]
                or not _SHA256.fullmatch(str(record.get("task_package_sha256", "")))):
            raise ValueError("invalid discovery eligibility record: %s" % task_id)
    return document


def _qualification_error(record: dict, task_id: str, package_hash: str) -> str | None:
    """Verify the reviewed evidence binding; this does not replace domain review."""
    review = record.get("qualification")
    if not isinstance(review, dict):
        return "missing reviewed calibration evidence"
    if not all(isinstance(review.get(key), str) and review[key].strip()
               for key in ("reviewer", "reviewed_at", "evidence_path", "evidence_sha256")):
        return "incomplete calibration review identity"
    relative = Path(review["evidence_path"])
    root = ROOT.resolve()
    artifact = (root / relative).resolve()
    if relative.is_absolute() or ".." in relative.parts or root not in artifact.parents:
        return "calibration evidence must be a repository-relative artifact"
    try:
        payload = artifact.read_bytes()
        if hashlib.sha256(payload).hexdigest() != review["evidence_sha256"]:
            return "calibration evidence hash changed"
        evidence = json.loads(payload)
    except (OSError, ValueError):
        return "calibration evidence is missing or invalid"
    if (not isinstance(evidence, dict) or evidence.get("schema_version") != 1
            or evidence.get("task_id") != task_id
            or evidence.get("task_package_sha256") != package_hash):
        return "calibration evidence is bound to a different task version"
    checks = evidence.get("qualification_checks")
    if not isinstance(checks, dict) or any(checks.get(key) is not True for key in QUALIFICATION_CHECKS):
        return "calibration qualification checks are incomplete"
    refs = evidence.get("evidence_refs")
    if (not isinstance(refs, list) or not refs
            or any(not isinstance(ref, str) or not ref.strip() for ref in refs)):
        return "calibration lacks supporting evidence references"
    return None


def discovery_eligibility(
    spec: Any, *, scientific_role: str | None = None, policy_path: Path | None = None,
) -> dict[str, Any]:
    """Return an explicit verdict for the current package, without changing its score.

    A known hold follows the logical task ID even after a package or role edit.
    Unknown discovery packages fail closed, including newly named v2 tasks.
    Optimization packages are outside this gate, subject to their existing gates.
    """
    policy = load_discovery_eligibility(policy_path)
    task_id = spec.task_id
    record = policy["tasks"].get(task_id)
    role = scientific_role or (getattr(spec, "metadata", {}) or {}).get("scientific_role")
    if record is None and role != "discovery":
        return {"task_id": task_id, "status": "not_applicable", "frontier_eligible": None,
                "reason": "discovery eligibility does not qualify optimization tasks"}
    from .algorithms.common import task_package_sha256

    package_hash = task_package_sha256(spec)
    out = {
        "task_id": task_id, "task_package_sha256": package_hash,
        "status": "calibration_required", "frontier_eligible": False,
        "historical_evaluation_allowed": True,
        "reason": "no reviewed calibration for this discovery task version",
    }
    if record is None:
        return out
    out.update({"status": record["status"], "reason": record["reason"],
                "reviewed_task_package_sha256": record["task_package_sha256"],
                "reviewed_package_matches": package_hash == record["task_package_sha256"],
                "evidence": record.get("evidence", [])})
    if record["status"] != "qualified":
        # Changing task files cannot erase a retirement/quarantine decision.
        return out
    if not out["reviewed_package_matches"]:
        out.update(status="calibration_required", reason="qualified task package changed; recalibration required")
        return out
    error = _qualification_error(record, task_id, package_hash)
    if error:
        out.update(status="calibration_required", reason=error)
        return out
    out["frontier_eligible"] = True
    return out


def require_discovery_frontier_eligibility(spec: Any, *, scientific_role: str | None = None) -> dict:
    verdict = discovery_eligibility(spec, scientific_role=scientific_role)
    if verdict["frontier_eligible"] is False:
        raise ValueError("discovery frontier promotion blocked: %s (%s); %s" % (
            spec.task_id, verdict["status"], verdict["reason"]))
    return verdict
