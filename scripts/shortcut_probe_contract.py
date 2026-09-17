"""Execute declared cheap candidates through the same sandbox as submissions.

This checks a measured upper guard; it does not certify difficulty or discover new
shortcuts. Declarations live in TASK_CARD.yaml, never in a candidate's output.

The guard is only as wide as what the card declares, so the contract also has to be
complete: every program in the task package that exposes the task's entrypoint is a
candidate someone already wrote, and each one must appear as the reference, as a probe,
or in `excluded` with a reason. Reviewed submissions repeatedly shipped an in-tree
candidate stronger than the declared probes and left it out of `probes`, which the
measured guard cannot see.

Three ways this guard used to be a floor rather than a measurement, each closed below:

* The author picked their own bar. Nothing bounded `relative_margin`, so `0.999` left a
  threshold of `0.001 * reference` and any probe that scored at all cleared it. The bar is
  a review decision, so it is now a policy ceiling (`MARGIN_CEILING`) rather than a fixed
  value - the widest margin a card may declare without a separate review decision.
* `excluded` was a free escape hatch. A strong in-tree program parked there with a
  plausible reason dropped out of `undeclared_candidates` and was never scored, because
  only `[reference, *probes]` was ever evaluated. Excluded programs are now measured too
  - see `inspect_probe` - so a listed reason buys an exclusion from the probe ladder, not
  from measurement.
* Enumeration was text-based. `^\\s*def\\s+<entrypoint>\\s*\\(` missed `audit = _impl`,
  missed anything under `runs/` (gitignored, so invisible to review and to any diff-based
  gate), and matched `def audit(` inside a string literal - it was wrong in both
  directions. Binding is now decided by parsing (see `_entrypoint_programs`).
"""
from __future__ import annotations

import ast
import hashlib
import json
import math
import pathlib
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "schemas" / "shortcut_probe_migration.json"

# The widest reference margin a task card may declare. The three observed values it is drawn
# from, all verifiable:
#   0.1 - the template (docs/task_admission_workflows.md) and both cards on main
#         (ComputerScience/SparseVectorAudit, ComputerScience/CacheReplacementPolicyID).
#   0.2 - the maintainer's own guard review of the transit-timing integration; recorded in
#         .research/pr11_shortcut_guard_review_2026-09-12.json as guard.relative_margin, verdict
#         passed.
#   0.3 - ParticlePhysics/DarkMatterRecoilAttribution's card on pull request 72, not yet merged,
#         so it is not on main and cannot be grepped there. Read it with
#         `git show origin/pr72:benchmarks/Physics/DarkMatterRecoilAttribution/TASK_CARD.yaml`.
# A tier table would contradict two of the three and force a review-record rewrite that measures
# nothing, so the ceiling is deliberately the loosest of the observed values: it exists to catch
# the margin that is not a margin at all, not to re-litigate 0.2 vs 0.1. Tightening it per tier
# is a superseding review decision, not a code change.
MARGIN_CEILING = 0.3


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
    if margin > MARGIN_CEILING:
        raise ValueError(
            "relative_margin %g exceeds the %g policy ceiling; at 0.999 the threshold is "
            "0.001 * reference and any probe that scores at all passes. Declaring a wider "
            "margin is a review decision: record it against this task and raise the "
            "ceiling, do not slide the bar" % (margin, MARGIN_CEILING))
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


def _binds_entrypoint(tree, entrypoint):
    """Whether this module binds the entrypoint name at module level.

    A `def` that shadows the entrypoint is the obvious case, but `audit = _impl` binds it
    just as well and the submission sandbox only ever does `getattr(module, entrypoint)`.
    `from reference_solver import audit` binds it too, and importing is the same act as
    assigning the name. An assignment that is later overwritten is still a candidate someone
    wrote, so this is deliberately a structural check rather than a dataflow one.
    """
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == entrypoint:
            return True
        if isinstance(node, ast.Assign):
            if any(isinstance(target, ast.Name) and target.id == entrypoint
                   for target in node.targets):
                return True
        if isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name) and node.target.id == entrypoint:
                return True
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            if any((alias.asname or alias.name) == entrypoint for alias in node.names):
                return True
    return False


def _entrypoint_programs(task_dir, entrypoint):
    """Every program in the package that a submission could be: it binds the entrypoint.

    Decided by parsing rather than by regex. Text search was wrong in both directions: it
    missed `audit = _impl` and matched `def audit(` inside a string literal (which is how
    TransitTimingAttribution's `replay_probes.py` carries its candidate templates, and why
    that file read as a candidate it was not). A file that does not parse falls back to the
    text match rather than to nothing, so a syntax error costs the guard no coverage.

    `runs/` is generated output, but it is *gitignored* output, so a candidate parked there
    is invisible to review and to any diff-based gate; the guard must still see a `.py` there
    that binds the entrypoint. It is not enumerated for helper files that do not, and
    `__pycache__` is skipped because a compiled copy is not a submitted candidate.

    `frontier_eval/` stays skipped: it is the harness that scores the submission, and a
    program there that binds the entrypoint is reached by shape rather than by naming. With
    that shape removed, a future such file and a candidate collide only when the next
    skeleton copy silently receives a function the evaluator calls, which is a live failure
    rather than an invisible pass. Measured across the tree, no task is affected by the
    change either way: zero programs outside `frontier_eval/` and `runs/` bind an entrypoint
    through a module-level assignment, and one file text-matched inside a string literal
    while binding nothing (TransitTimingAttribution `verification/replay_probes.py`).
    """
    found = set()
    for path in sorted(task_dir.rglob("*.py")):
        relative = path.relative_to(task_dir)
        if relative.parts[0] == "frontier_eval" or "__pycache__" in relative.parts:
            continue
        try:
            source = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        try:
            tree = ast.parse(source)
        except (SyntaxError, ValueError):
            tree = None
        if tree is not None:
            if _binds_entrypoint(tree, entrypoint):
                found.add(path.resolve())
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
    excluded_scores = []
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
    # Excluded candidates are measured too. A listed reason buys an exclusion from the probe
    # ladder - this candidate is not the declared cheap shortcut - not from measurement: the
    # whole point of `excluded` is the program that is stronger than the declared probes but
    # was argued away instead of evaluated. Scoring them under the same reference means the
    # argument is checked against the same bar, and it is what keeps the escape hatch honest.
    # `reference`/`probes` dedup is validate_contract's job and already done above.
    for entry in contract.get("excluded", []):
        path = _candidate(spec.task_dir, entry["candidate"])
        observation = {"id": "excluded:" + entry["candidate"], "excluded": True,
                       "candidate": entry["candidate"], "reason": entry["reason"],
                       "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        try:
            metrics = evaluate(spec, path, timeout_s=timeout_s)
            repeat = evaluate(spec, path, timeout_s=timeout_s)
            score = metrics.get("combined_score")
            if metrics.get("infrastructure_failure") or repeat.get("infrastructure_failure"):
                raise ValueError("infrastructure failure is not a probe measurement")
            if metrics != repeat:
                raise ValueError("full probe metrics are nondeterministic")
            if metrics.get("valid") == 1 and _number(score):
                observation["measured_score"] = score
                excluded_scores.append(score)
            else:
                # Did not come back valid: infeasible by construction, which is exactly the
                # case `excluded` exists for (LyapunovDecayCertificate's constant_probe.py is
                # valid=0 on every instance). It cannot be a probe, because a probe must be a
                # valid finite-scoring candidate - so there is no bar for it to clear. The
                # evaluator's own message is kept so a reviewer can tell infeasibility from
                # a file that never loaded.
                observation["infeasible"] = str(
                    metrics.get("error_message")
                    or metrics.get("candidate_failure_kind") or "valid=0")
        except Exception as exc:
            observation["error"] = str(exc)
            errors.append(observation["id"] + ": " + str(exc))
        result["observations"].append(observation)
    result["excluded_scores"] = excluded_scores
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
        if result["passed"] and excluded_scores and max(excluded_scores) >= threshold:
            # Stronger than every declared probe and above the bar. Excluding it was a
            # review decision this measurement contradicts, not a cataloguing detail.
            result["excluded_best"] = max(excluded_scores)
            result["passed"] = False
            result.update(status="failed", detail=(
                "an excluded candidate scores %g, at or above the %g threshold: `excluded` "
                "records why a candidate is not the declared cheap shortcut, it does not "
                "exempt one from measurement" % (result["excluded_best"], threshold)))
        else:
            result.update(status="passed" if result["passed"] else "failed",
                          detail="best declared shortcut must be strictly below the reference margin")
    return result
