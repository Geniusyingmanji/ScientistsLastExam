"""Execute declared cheap candidates through the same sandbox as submissions.

This checks a measured upper guard; it does not certify difficulty or discover new
shortcuts. Declarations live in TASK_CARD.yaml, never in a candidate's output.

The guard is only as wide as what the card declares, so the contract also has to be
complete: every program in the task package that exposes the task's entrypoint is a
candidate someone already wrote, and each one must appear as the reference, as a probe,
or in `excluded` with a reason. Reviewed submissions repeatedly shipped an in-tree
candidate stronger than the declared probes and left it out of `probes`, which the
measured guard cannot see.
"""
from __future__ import annotations

import hashlib
import json
import math
import pathlib
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "schemas" / "shortcut_probe_migration.json"


def _number(value):
    return type(value) in (int, float) and math.isfinite(value)


def _candidate(root, value):
    if not isinstance(value, str) or not value or Path(value).is_absolute():
        raise ValueError("candidate must be a task-relative path")
    path = (root / value).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError("candidate path escapes the task package") from exc
    if not path.is_file():
        raise ValueError("candidate must be an existing file within the task package: " + value)
    if path.suffix != ".py":
        raise ValueError("candidate must be Python source")
    return path


def validate_contract(contract, task_dir):
    """Validate structure even when measurements have explicitly not been supplied."""
    if not isinstance(contract, dict) or contract.get("schema_version") != 1:
        raise ValueError("shortcut_probe requires schema_version: 1")
    if contract.get("metric") != "combined_score":
        raise ValueError("shortcut_probe metric must be combined_score")
    margin, tolerance = contract.get("relative_margin"), contract.get("score_tolerance")
    if not _number(margin) or not 0 < margin < 1:
        raise ValueError("relative_margin must be finite and between zero and one")
    if not _number(tolerance) or not 0 <= tolerance < 0.05:
        raise ValueError("score_tolerance must be finite and in [0, 0.05)")
    probes = contract.get("probes")
    if not isinstance(probes, list) or not probes:
        raise ValueError("at least one shortcut probe is required")
    entries = [contract.get("reference"), *probes]
    names = set()
    paths = set()
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict) or "expected_score" not in entry:
            raise ValueError("every candidate needs an expected_score (null means unmeasured)")
        if index:
            name = entry.get("id")
            if not isinstance(name, str) or not name or name in names:
                raise ValueError("probe ids must be nonempty and unique")
            names.add(name)
        path = _candidate(task_dir, entry.get("candidate"))
        if path in paths:
            raise ValueError("reference and probes must name distinct candidates")
        paths.add(path)
        if entry["expected_score"] is not None and not _number(entry["expected_score"]):
            raise ValueError("expected_score must be finite or null")
    excluded = contract.get("excluded", [])
    if not isinstance(excluded, list):
        raise ValueError("excluded must be a list of {candidate, reason}")
    for entry in excluded:
        if not isinstance(entry, dict):
            raise ValueError("excluded must be a list of {candidate, reason}")
        reason = entry.get("reason")
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("every excluded candidate needs a nonempty reason")
        path = _candidate(task_dir, entry.get("candidate"))
        if path in paths:
            raise ValueError("a candidate cannot be both declared and excluded")
        paths.add(path)
    return entries


def _entrypoint_programs(task_dir, entrypoint):
    """Every program in the package that a submission could be: it defines the entrypoint.

    `frontier_eval/` is the harness rather than a candidate, and `runs/` is generated
    output, so neither is enumerated.
    """
    found = set()
    for path in sorted(task_dir.rglob("*.py")):
        relative = path.relative_to(task_dir)
        if relative.parts[0] in ("frontier_eval", "runs") or "__pycache__" in relative.parts:
            continue
        try:
            source = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if re.search(r"^\s*def\s+%s\s*\(" % re.escape(entrypoint), source, re.M):
            found.add(path.resolve())
    return found


def undeclared_candidates(contract, spec):
    """Programs that expose the entrypoint but are neither declared nor excluded."""
    entrypoint = getattr(spec, "entrypoint", None)
    if not isinstance(entrypoint, str) or not entrypoint:
        return None
    task_dir = pathlib.Path(spec.task_dir)
    accounted = set()
    for entry in [contract.get("reference"), *contract.get("probes", []),
                  *contract.get("excluded", [])]:
        if isinstance(entry, dict) and isinstance(entry.get("candidate"), str):
            accounted.add((task_dir / entry["candidate"]).resolve())
    return sorted(str(p.relative_to(task_dir.resolve()))
                  for p in _entrypoint_programs(task_dir, entrypoint) - accounted)


def inspect_probe(spec, evaluate, *, timeout_s=180.0, skip_eval=False):
    result = {"status": "pending", "passed": False, "observations": [],
              "scope": "declared shortcut guard only; independent model calibration still required"}
    try:
        card = yaml.safe_load((spec.task_dir / "TASK_CARD.yaml").read_text()) or {}
        if not isinstance(card, dict):
            raise ValueError("task card root must be a mapping")
    except (OSError, ValueError, yaml.YAMLError) as exc:
        result.update(status="failed", detail="cannot read task card: " + str(exc))
        return result
    contract = card.get("shortcut_probe")
    if contract is None:
        migration = json.loads(MIGRATION.read_text()).get("tasks", {}).get(spec.task_id)
        if migration:
            # `detail` is the human-readable line the gate's CLI prints, so it stays a string
            # even when the structured record is the more useful thing to keep. The record
            # itself moves to `migration`, where a reader that wants the reason and the
            # recorded probe paths can still find it. Putting the mapping in `detail` made
            # `check_task_contribution.py` raise TypeError for all 85 pending tasks - every
            # task in the tree except the two that already declare a contract - including the
            # example command in docs/task_admission_workflows.md.
            result.update(status="migration_pending", detail=str(
                migration.get("reason") or "listed in the shortcut-probe migration inventory"))
            result["migration"] = migration
        else:
            result.update(status="failed",
                          detail="new task is missing TASK_CARD.yaml shortcut_probe")
        return result
    try:
        entries = validate_contract(contract, spec.task_dir)
    except (ValueError, OSError) as exc:
        result.update(status="failed", detail=str(exc))
        return result
    missing = undeclared_candidates(contract, spec)
    if missing:
        result["undeclared_candidates"] = missing
        result.update(status="failed", detail=(
            "these programs expose the entrypoint but are neither declared nor excluded: "
            + ", ".join(missing)))
        return result
    result["contract_sha256"] = hashlib.sha256(
        json.dumps(contract, sort_keys=True, allow_nan=False).encode()).hexdigest()
    if skip_eval:
        result.update(status="skipped", detail="shortcut candidates were not evaluated")
        return result
    errors = []
    scores = []
    for index, entry in enumerate(entries):
        path = _candidate(spec.task_dir, entry["candidate"])
        observation = {"id": "reference" if index == 0 else entry["id"],
                       "candidate": entry["candidate"], "expected_score": entry["expected_score"],
                       "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        try:
            metrics = evaluate(spec, path, timeout_s=timeout_s)
            repeat = evaluate(spec, path, timeout_s=timeout_s)
            score = metrics.get("combined_score")
            if metrics.get("infrastructure_failure") or repeat.get("infrastructure_failure"):
                raise ValueError("infrastructure failure is not a probe measurement")
            if metrics != repeat:
                raise ValueError("full probe metrics are nondeterministic")
            if metrics.get("valid") != 1 or not _number(score):
                raise ValueError("shortcut/reference must be a valid finite-scoring candidate")
            observation["measured_score"] = score
            if index == 0:
                # The reference's own discovery axes, recorded so a reader can see whether the
                # triple still costs the witness anything at the top of the scale. Measured
                # across the tree, nineteen of thirty-one references sit at false discovery 0,
                # correct refusal 1 and coverage 1 - there the three axes carry no information
                # and the headline is the mechanism number alone. This is reported, never scored.
                axes = {key: metrics[key] for key in metrics
                        if isinstance(metrics.get(key), (int, float))
                        and any(key.endswith(suffix) for suffix in (
                            "false_discovery_rate", "correct_refusal_rate",
                            "discovery_coverage", "mechanism_score"))}
                if axes:
                    result["reference_axes"] = axes
                    result["reference_axes_saturated"] = all(
                        (value == 0.0 if key.endswith("false_discovery_rate") else value == 1.0)
                        for key, value in axes.items()
                        if not key.endswith("mechanism_score"))
            scores.append(score)
            expected = entry["expected_score"]
            if expected is not None and abs(score - expected) > contract["score_tolerance"]:
                raise ValueError("measured score does not match the task-card declaration")
        except Exception as exc:
            observation["error"] = str(exc)
            errors.append(observation["id"] + ": " + str(exc))
        result["observations"].append(observation)
    if errors:
        result.update(status="failed", detail="; ".join(errors))
    elif any(entry["expected_score"] is None for entry in entries):
        result.update(status="unmeasured_declaration", detail="record and independently review measured declarations in a separate task-card change")
    elif scores[0] <= 0:
        result.update(status="failed", detail="reference must score above zero")
    else:
        threshold = scores[0] * (1 - contract["relative_margin"])
        result.update(reference_score=scores[0], probe_best=max(scores[1:]), threshold=threshold)
        result["passed"] = max(scores[1:]) < threshold
        result.update(status="passed" if result["passed"] else "failed",
                      detail="best declared shortcut must be strictly below the reference margin")
    return result
