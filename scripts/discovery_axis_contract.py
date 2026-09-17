"""Static enforcement of the discovery-axis requirements a runtime check cannot see.

CONTRIBUTING.md requires a discovery task to report three axes separately plus a fourth
column for whether the candidate tried to discover at all, every rate beside the count
it is a rate of. Two of those requirements are prose only, and neither is visible in an
oracle's returned numbers:

*a missing fourth column*
    Five of the 46 discovery tasks publish no "did the agent even try" key, so on the
    report "every proposal refused every world" and "the science was too hard" are the
    same row.

*a mechanism axis bound to the raw value*
    Seven evaluators publish ``"mechanism_score": dev["raw_mechanism"]`` while
    ``combined_score`` correctly uses the normalized value. A blanket abstainer reports
    its free credit on the mechanism axis it earned nothing on. Every published rate is
    finite and the headline is right, so nothing about the returned metrics is malformed -
    only the *source* shows that the axis and the headline disagree.

Both are checked against the source, which is also the only form that runs under
``--skip-eval`` and on a host with no working candidate sandbox. The check reads the
verification source the same way the existing denominator inventory does - by the metric
keys the evaluator writes. One limit is worth stating: a key written anywhere in that
source counts, so an internal per-split summary that is never returned can satisfy it.
Resolving a dict spread back to the returned payload is the same problem as ``eval``, and
the eval-time check in the gate reads the real returned metrics for the tasks that can run.
The inventory therefore cannot shrink for a task whose keys only reach a summary, which is
the conservative direction: listed for review, never passed.

Following the shortcut-probe guard, a task that predates the requirement is listed in
``schemas/discovery_axis_contract_migration.json`` as pending rather than failed, and a
task that is neither listed nor compliant fails. Pending is never a pass.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "schemas" / "discovery_axis_contract_migration.json"

# Matched on the suffix so any split prefix ("development", "heldout", "confirmation")
# works: the tree names the same axis both ways and a prefix list would go stale slowly.
# Each rate suffix carries the spelling of its own count, because the prefix applies to the
# whole metric stem: a "development_mechanism_score" is counted by
# "development_mechanism_denominator", not by "development_denominator".
AXIS_SUFFIXES = {
    "mechanism": {"mechanism_score": "mechanism",
                  "body_support_f1": "body_support",
                  "supported_correct_model_rate": "supported_correct_model",
                  "hypothesis_score": "hypothesis"},
    "false_discovery": {"false_discovery_rate": "false_discovery"},
    "refusal": {"correct_refusal_rate": "correct_refusal",
                "unsupported_refusal_rate": "unsupported_refusal"},
    # The fourth column. Coverage counts: a coverage of zero over the worlds that admit a
    # claim is the same fact as never attempting one, and the tree publishes it that way.
    "attempted": {"attempted_discovery": "attempted_discovery",
                  "discovery_attempt": "discovery_attempt",
                  "discovery_coverage": "discovery",
                  "supported_claim_coverage": "supported_claim",
                  "attempt_rate": "attempt"},
}
RATE_AXES = ("mechanism", "false_discovery", "refusal")
ALL_AXES = RATE_AXES + ("attempted",)

# A rate is read against a count named the same way: the stem swapped for a counting word,
# and, since the quantity is the number of measured worlds, any of the tree's generic
# spellings of that. The prefix is peeled off the rate and reattached to this name, so a
# count at the wrong split does not satisfy a rate at this one.
COUNT_STEMS = ("{stem}_denominator", "{stem}_count", "{stem}_n",
               "n_{stem}", "{stem}_total")
GENERIC_COUNTS = ("world_count", "record_count", "n_worlds", "num_worlds", "n_records")

# Keys that name the pre- or post-normalization companion of the mechanism axis rather
# than the axis itself. Reading them as the axis would satisfy "separately published"
# with the raw number and the headline's own copy of it.
COMPANION_MARKERS = ("raw", "normalized", "always_abstain", "abstention_baseline")


def oracle_source(spec) -> str:
    """Every Python file the task's verification directory contributes to the oracle."""
    return "".join(path.read_text(encoding="utf-8", errors="replace")
                   for path in sorted((Path(spec.task_dir) / "verification").glob("*.py")))


def metric_keys(source: str) -> dict[str, list[str]]:
    """String keys the source writes into a dict, mapped to *every* source of their value.

    Key presence here is the same evidence the existing denominator inventory uses. Every
    occurrence is kept, not just the first: the same key is routinely reused for a per-world
    row before it is used in the returned payload, and ``mechanism_score`` is a literal zero
    in the row and ``dev["raw_mechanism"]`` in the return. Keeping only the first occurrence
    would read the row and miss the defect, which is a property of the returned assignment.
    """
    keys: dict[str, list[str]] = {}
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return keys
    for node in ast.walk(tree):
        if not isinstance(node, ast.Dict):
            continue
        for key, value in zip(node.keys, node.values):
            if isinstance(key, ast.Constant) and isinstance(key.value, str):
                keys.setdefault(key.value, []).append(ast.unparse(value))
    return keys


def _rate_parts(key: str) -> tuple[str, str, str] | None:
    """(axis, prefix, counting stem) for a rate key, or None if it is not one.

    A raw/normalized companion names the same axis but is not it, so it is rejected here
    rather than counted as a second publication of the rate.
    """
    if any(marker in key.lower() for marker in COMPANION_MARKERS):
        return None
    for axis, suffixes in AXIS_SUFFIXES.items():
        for suffix, stem in suffixes.items():
            if key == suffix:
                return axis, "", stem
            if key.endswith("_" + suffix):
                return axis, key[: -(len(suffix) + 1)], stem
    return None


def _count_names(prefix: str, stem: str) -> set[str]:
    names = {template.format(stem=stem) for template in COUNT_STEMS}
    names.update(GENERIC_COUNTS)
    if prefix:
        names = {prefix + "_" + name for name in names}
    return names


def _has_count(keys, prefix: str, stem: str) -> bool:
    return bool(_count_names(prefix, stem) & set(keys))


# A published value that is a bare literal says nothing about which axis it belongs to.
PLACEHOLDER_VALUES = ("0.0", "0", "1.0", "1", "True", "False", "None")


def axis_findings(source: str) -> dict:
    """Which parts of the four-column contract the verification source does not publish."""
    keys = metric_keys(source)
    rates: dict[str, list[str]] = {}
    parts: dict[str, tuple[str, str]] = {}
    for key in keys:
        decoded = _rate_parts(key)
        if decoded is None:
            continue
        axis, prefix, stem = decoded
        rates.setdefault(axis, []).append(key)
        parts[key] = (prefix, stem)
    for axis in rates:
        rates[axis].sort()

    findings: dict = {"rates": rates, "undocumented_rates": [], "problems": []}

    # Every published version of an axis needs its own denominator. A development rate and
    # a heldout rate read against one shared count is the same defect as no count at all:
    # the two splits have different world counts, and the tree publishes split-prefixed
    # rates precisely because the denominators differ.
    for axis in ALL_AXES:
        for key in rates.get(axis, ()):
            prefix, stem = parts[key]
            if not _has_count(keys, prefix, stem):
                findings["undocumented_rates"].append(key)

    if not rates.get("attempted"):
        findings["problems"].append(
            "no attempted-discovery or coverage rate is published, so refusing every world "
            "and discovering nothing render identically")
    for axis in RATE_AXES:
        if not rates.get(axis):
            findings["problems"].append("no %s rate is published" % axis.replace("_", " "))

    # The axes must be separably published, not one number under three names. A shared
    # literal is a placeholder rather than a collapse, so only a shared non-trivial
    # expression counts.
    seen: dict[str, str] = {}
    for axis in RATE_AXES:
        for key in rates.get(axis, ()):
            for expression in keys.get(key, ()):
                if expression in PLACEHOLDER_VALUES:
                    continue
                if expression in seen:
                    findings["problems"].append(
                        "%s and %s are published from the same expression, so the axes are "
                        "not separately recoverable" % (seen[expression], key))
                else:
                    seen[expression] = key

    # The reporting defect: a mechanism axis carrying the pre-normalization value while
    # the normalized one exists. `combined_score` uses the normalized value, so the axis
    # and the headline disagree by exactly the free credit for abstaining.
    for key, expressions in keys.items():
        decoded = _rate_parts(key)
        if decoded is None or decoded[0] != "mechanism":
            continue
        if any("raw_mechanism" in expression for expression in expressions):
            findings["problems"].append(
                "%s publishes the raw mechanism while combined_score uses the normalized "
                "value; a blanket abstainer earns credit on this axis" % key)
    return findings


def inspect_axes(spec) -> dict:
    """The discovery-axis contract verdict for one task, migration inventory included."""
    source = oracle_source(spec)
    if not source.strip():
        return {"status": "failed", "passed": False, "findings": {},
                "detail": "no verification source to read"}
    findings = axis_findings(source)
    if not findings["problems"] and not findings["undocumented_rates"]:
        return {"status": "passed", "passed": True, "findings": findings,
                "detail": "four columns published, each rate beside the count it is a rate of"}
    detail = "; ".join(findings["problems"] + [
        "%s has no count at its own prefix" % key for key in findings["undocumented_rates"]])
    record = _migration_record(spec.task_id)
    if record:
        # Pending, not passed and not failed: the task was admitted before the requirement
        # existed. `passed` stays False so a caller that reads only the boolean cannot
        # mistake a listed task for a compliant one.
        return {"status": "migration_pending", "passed": False, "findings": findings,
                "migration": record, "detail": str(record.get("reason") or detail)}
    return {"status": "failed", "passed": False, "findings": findings, "detail": detail}


def _migration_record(task_id: str):
    try:
        return json.loads(MIGRATION.read_text(encoding="utf-8")).get("tasks", {}).get(task_id)
    except (OSError, ValueError):
        return None


def discovery_task_ids() -> list[str]:
    """Registry tasks whose taxonomy form is discovery, in registry order."""
    import sys

    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    import yaml

    from sle.registry import list_tasks

    taxonomy = yaml.safe_load((ROOT / "sle" / "conf" / "exam_taxonomy.yaml").read_text(
        encoding="utf-8"))["tasks"]
    return [spec.task_id for spec in list_tasks(None)
            if taxonomy.get(spec.task_id, {}).get("form") == "discovery"]


def noncompliant_task_ids() -> list[str]:
    """Discovery tasks the static check does not pass, in registry order."""
    from sle.registry import find_task

    offenders = []
    for task_id in discovery_task_ids():
        spec = find_task(task_id, include_uncertified=True)
        if not inspect_axes(spec)["passed"]:
            offenders.append(task_id)
    return sorted(offenders)
