#!/usr/bin/env python3
"""Is the reference already so high that nothing is left to win?

`run_canary_audit.py` asks the *bottom* question: can a degenerate candidate earn credit? This
asks the *top* question, which nothing else in the tree measures: does the declared reference
already sit at the ceiling the task's own scoring contract admits? If it does, the task cannot
separate a competent searcher from the reference at the top of its range, because the reference
witness is the maximum available and a strategy that ties it has won everything there is.

## Why reference-at-the-ceiling, and not "a trivial candidate ties"

Two measurable definitions were considered.

**A trivial candidate scores within tolerance of the reference.** This is what a maintainer
measures by hand, and it is the most direct statement of the defect. It is not used as the audit's
verdict because it is not generalisable: a "trivial candidate" is specific to a task's entrypoint
and problem schema - the trivial strategy for `Gravitation/PTAHellingsDowns` is a four-kernel
least-squares argmin, and for `Oceanography/AMOCTippingRefusal` it is a constant collapse year, and
neither is expressible for the other task or for the other 86.

The claim sometimes attached to this - "a generic probe is malformed, so it must score zero" -
does NOT hold as a general proposition, and the two zero-scoring examples below are examples of
those two strategies, not evidence for the general rule. The maintainer's `claim_all` /
`abstain_all` probes (#107) are equally generic - they flip the `abstain` boolean that every
discovery evaluator validates, so one implementation runs the whole tree - yet they submit the
reference's own shape of legal answer (`valid=1`) and are covered by no existing check:
`claim_all` scores 0.500 on QuinaryConvexHull and 0.833 on ProspectiveMetaAnalysis. The zero
below is a property of world-varying answers and malformed submissions, not of genericity.

Measured here: a generic replicate-everything policy on `MaterialsScience/QuinaryConvexHull`
scores 0.0 against a reference of 1.0, and a generic local-z threshold on
`ParticlePhysics/LookElsewhereAnomaly` scores 0.0 against 1.0. The two instances that *do*
reproduce (a no-margin argmin on `Gravitation/PTAHellingsDowns`, a zero-probe constant year on
`Oceanography/AMOCTippingRefusal`) are pinned as regression tests in
`tests/test_saturation_audit.py` rather than claimed as a general reader.

**The declared reference scores at the normalised ceiling.** Directly measurable for every clipped
task, needs no per-task strategy, and is why a trivial strategy *can* tie: the reference is already
the maximum, so tying it needs no more than being right once. This is the audit's verdict. It is
also exactly the prose standard the cards already use by hand: of the six references measured at
the ceiling on 2026-09-17, five say "The reference sits at the scoring ceiling this contract
admits" in their own `known_best.md` while their structured card says nothing.

## The two findings

`at_ceiling_undeclared` is the defect. The reference is at the ceiling and the structured card
does not say so. This observation alone does not establish task difficulty or model saturation.
`at_ceiling_declared` is not a defect: a task that documents its own saturation honestly is a
finished on-ramp, and the distinction between the two is the point of the split. Measured
2026-09-17: five undeclared, one declared.

## Why this is reported and not gated

A reference at the ceiling is not always wrong. When the ceiling *is* the scientific record - a
recovery task whose reference reconstructs the published value - there is nothing above it to win,
and that is a legitimate task shape. Only a reviewer can tell that case from a task that mistook
its own easy reference for a hard one, so the verdict is an observation. The undeclared set is
carried as a `pending` inventory in `schemas/saturation_migration.json`, the shape
`shortcut_probe_contract.py` and `check_task_contribution.py` already use: listing is never a
pass, a new task is not exempt, and a test pins the inventory to exactly the flagged set so a task
cannot be quietly added to it or quietly harden and be left in it.

Usage:
    python scripts/saturation_audit.py --output .research/saturation.json
    python scripts/saturation_audit.py --task Gravitation/PTAHellingsDowns
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import math
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from sle.registry import find_task, list_tasks  # noqa: E402
from sle.secure_eval import load_oracle  # noqa: E402

MIGRATION = ROOT / "schemas" / "saturation_migration.json"

# Within this distance of 1.0 the reference is treated as at the ceiling. The tree's other
# tolerances are looser - `shortcut_probe_contract` lets a probe sit 5% under the reference and
# `BASELINE_ZERO_TOLERANCE` is 0.05 - because those guard against a *rise*; this one is claiming a
# tie, so it is tighter. Scores arrive as means of per-world 0/1 mechanism values, so the smallest
# non-trivial gap is one world.
DEFAULT_TOLERANCE = 0.01

AT_CEILING_UNDECLARED = "at_ceiling_undeclared"
AT_CEILING_DECLARED = "at_ceiling_declared"
HEADROOM = "headroom"
NOT_MEASURED = "not_measured"


def _load(path: Path):
    module_spec = importlib.util.spec_from_file_location("sat_%s" % path.stem, str(path))
    if module_spec is None or module_spec.loader is None:
        raise ImportError("cannot load %s" % path.name)
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    return module


def _reference_candidates(spec) -> list[Path]:
    """Every `verification/reference*.py` that defines the entrypoint and imports on this host."""
    candidates = []
    for path in sorted((spec.task_dir / "verification").glob("*.py")):
        if path.name == "evaluator.py" or not path.name.startswith("reference"):
            continue
        try:
            module = _load(path)
        except Exception:  # noqa: BLE001 - an unimportable candidate is not the reference
            continue
        if callable(getattr(module, spec.entrypoint, None)):
            candidates.append(path)
    return candidates


def reference_path(spec) -> Path | None:
    """The shipped reference program, or None when the task does not ship exactly one.

    The name is a tree-wide convention rather than a contract field, so this matches the way
    `shortcut_probe_contract.py` enumerates candidates: a `verification/*.py` file whose name
    starts with `reference` and which defines the task's entrypoint. Thirty-nine of eighty-eight
    tasks instead keep the reference inside the evaluator as a private policy
    (`_reference_agent`, `_reference_policy`, ...), which is not a submission and cannot be
    scored from outside; they are reported as not measured, never as passing.

    When more than one file matches, the audit refuses to guess: picking an ablation would report
    the ablation's saturation as the task's.
    """
    candidates = _reference_candidates(spec)
    return candidates[0] if len(candidates) == 1 else None


def _no_reference_detail(spec) -> str:
    """Why no single reference could be resolved, without claiming more than was checked.

    A package that names `reference*.py` files but none of which import on this host is a host
    limitation, not a missing reference - saying "evaluator-internal" there would be false.
    """
    named = sorted(path.name for path in (spec.task_dir / "verification").glob("reference*.py"))
    if named:
        return ("reference-named files present but not exactly one resolved: %s"
                % ", ".join(named))
    return "no submitable reference file; the reference is evaluator-internal"


def declares_saturation(spec) -> str | None:
    """The card's own written-down verdict, so honesty can be told from an omission.

    Only structured, machine-readable declarations count. A prose sentence in `known_best.md` is
    not a field a reader can act on - the five tasks flagged below all carry that sentence while
    their `long_horizon.status` still reads `not_tested`, which is the whole reason this audit
    exists.
    """
    card_path = spec.task_dir / "TASK_CARD.yaml"
    try:
        card = yaml.safe_load(card_path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return None
    if not isinstance(card, dict):
        return None
    horizon = card.get("long_horizon")
    status = str(horizon.get("status") or "") if isinstance(horizon, dict) else ""
    if _declares(status):
        return "long_horizon.status=%s" % status
    health = card.get("measurement_health")
    if isinstance(health, dict) and _declares(str(health.get("status") or "")):
        return "measurement_health.status=%s" % health["status"]
    return None


# A declaration is an AFFIRMATION, and the previous word test was one substring away from reading
# a denial as one: adversarial review measured that "not_saturated", "unsaturated",
# "not_saturated_pending_review", "desaturated" and "saturation_unknown" all matched "saturat",
# which would move a task from at_ceiling_undeclared (the defect class) to at_ceiling_declared
# (not a defect) and drop it off the inventory. Only an affirmative status declares. An unseen
# wording resolves to not-declared - the safe direction, since a false "declared" hides a defect.
_SATURATION_DECLARED = (
    "saturated", "saturated_for_current_frontier", "saturated_for_the_current_frontier",
)


def _declares(status: str) -> bool:
    lowered = status.strip().lower()
    return lowered in _SATURATION_DECLARED


def audit_task(spec, tolerance: float = DEFAULT_TOLERANCE) -> dict:
    """Score the declared reference and classify it against the task's own ceiling.

    The evaluator and the reference are both frozen repository source, imported in process the
    same way `run_canary_audit.py` loads its oracles. The sandboxed path is deliberately not used:
    it needs a matching interpreter and pinned package set that a reporting audit should not
    depend on, and it would make the audit un-runnable exactly when a reviewer wants it.
    """
    if (isinstance(tolerance, bool) or not isinstance(tolerance, (int, float))
            or not math.isfinite(tolerance) or not 0 <= tolerance < 1):
        raise ValueError("tolerance must be finite and in [0, 1)")
    row = {"task": spec.task_id, "score_mode": spec.metadata.get("score_mode"),
           "declared": declares_saturation(spec)}
    reference = reference_path(spec)
    if reference is None:
        row.update(status=NOT_MEASURED, detail=_no_reference_detail(spec))
        return row
    row["reference"] = reference.relative_to(spec.task_dir).as_posix()
    try:
        oracle = load_oracle(spec.task_dir)
        entry = getattr(_load(reference), spec.entrypoint)
        metrics = oracle(entry)
    except Exception as exc:  # noqa: BLE001 - an oracle that will not run is not a pass
        row.update(status=NOT_MEASURED, detail="%s: %s" % (type(exc).__name__, str(exc)[:160]))
        return row
    score = metrics.get("combined_score") if isinstance(metrics, dict) else None
    valid = metrics.get("valid") if isinstance(metrics, dict) else None
    if (isinstance(score, bool) or not isinstance(score, (int, float))
            or not math.isfinite(score)):
        row.update(status=NOT_MEASURED, detail="oracle returned no finite combined_score")
        return row
    if (isinstance(valid, bool) or not isinstance(valid, (int, float)) or valid != 1
            or metrics.get("infrastructure_failure")):
        row.update(status=NOT_MEASURED, detail="reference evaluation was not scientifically valid")
        return row
    score = float(score)
    row.update(combined_score=score, valid=metrics.get("valid"))
    if row["score_mode"] != "clipped":
        # An uncapped task's ceiling is a number the task itself does not publish; the normalised
        # 1.0 that the clipped tasks share has no meaning here, so no verdict is offered.
        row.update(status=NOT_MEASURED, detail="uncapped task; no normalised ceiling to compare to")
        return row
    if not 0.0 <= score <= 1.0 + 1e-9:
        row.update(status=NOT_MEASURED, detail="score outside the clipped contract")
        return row
    if score < 1.0 - tolerance:
        row.update(status=HEADROOM)
        return row
    row["status"] = AT_CEILING_DECLARED if row["declared"] else AT_CEILING_UNDECLARED
    return row


def declares_ceiling(spec) -> bool:
    """A cheap word test for the task's own claim that the reference is at the ceiling.

    The measured audit costs one full oracle evaluation per task - minutes, dominated by the
    flagship contracts - so re-running all eighty-eight for every reviewer, or inside a test
    suite, is not affordable. This reads the card and the prose instead. It is deliberately
    broader than `declares_saturation`: it also matches the sentence five of the six tasks carry
    in `known_best.md` while their structured status still reads `not_tested`, which is exactly
    the gap this audit exists to close.

    Use it as a *trigger* - a task where it is true, or whose evaluator or reference changed
    since the last run, is one to re-measure with `--verify`. It over-approximates by design and
    is never a pass: a task it does not match may still be at the ceiling, and the measured audit
    remains the authority.
    """
    texts = []
    for path in (spec.task_dir / "TASK_CARD.yaml",
                 spec.task_dir / "references" / "known_best.md"):
        try:
            texts.append(path.read_text(encoding="utf-8"))
        except OSError:
            continue
    lowered = " ".join(texts).lower()
    return "saturat" in lowered or "at the scoring ceiling" in lowered


def build_report(specs, tolerance: float = DEFAULT_TOLERANCE) -> dict:
    rows = [audit_task(spec, tolerance) for spec in specs]
    undeclared = [row["task"] for row in rows if row["status"] == AT_CEILING_UNDECLARED]
    declared = [row["task"] for row in rows if row["status"] == AT_CEILING_DECLARED]
    return {
        "schema_version": 1,
        "tolerance": tolerance,
        "definition": (
            "reported when the declared reference's combined_score is within `tolerance` of the "
            "normalised ceiling of its own clipped contract, so a task-specific trivial strategy "
            "that ties the reference leaves nothing above it to win"),
        "not_a_gate": (
            "a reference at the ceiling is legitimate when the ceiling is the scientific record; "
            "the undeclared set is an inventory for review, and unmeasured tasks are never passes"),
        "task_count": len(rows),
        "at_ceiling_undeclared": undeclared,
        "at_ceiling_declared": declared,
        "rows": rows,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", required=True)
    ap.add_argument("--task", default=None, help="restrict to one task id")
    ap.add_argument("--verify", default=None,
                    help="comma-separated task ids to re-measure; the inventory is the default")
    ap.add_argument("--declared-only", action="store_true",
                    help="report the cheap declaration word test only; no oracle is evaluated")
    ap.add_argument("--tolerance", type=float, default=DEFAULT_TOLERANCE)
    args = ap.parse_args(argv)

    if args.declared_only:
        rows = [{"task": spec.task_id, "declared": declares_saturation(spec),
                 "word_test": declares_ceiling(spec)} for spec in list_tasks(None)]
        report = {"schema_version": 1, "word_test_only": True, "rows": rows,
                  "at_ceiling_or_undetermined": [
                      row["task"] for row in rows if not row["declared"]]}
        Path(args.output).write_text(json.dumps(report, indent=2, default=str, allow_nan=False), encoding="utf-8")
        print("saturation word test: %d tasks" % len(rows))
        print("report: %s" % args.output)
        return 0

    if args.verify:
        wanted = [name.strip() for name in args.verify.split(",") if name.strip()]
        specs = [find_task(name, include_uncertified=True) for name in wanted]
    else:
        specs = [spec for spec in list_tasks(None)
                 if args.task is None or spec.task_id == args.task]
    report = build_report(specs, args.tolerance)
    Path(args.output).write_text(json.dumps(report, indent=2, default=str, allow_nan=False), encoding="utf-8")

    measured = [row for row in report["rows"] if row["status"] != NOT_MEASURED]
    print("saturation audit: %d tasks, %d references scored at the ceiling, %d undeclared"
          % (len(report["rows"]), len(report["at_ceiling_declared"])
             + len(report["at_ceiling_undeclared"]), len(report["at_ceiling_undeclared"])))
    for row in report["rows"]:
        if row["status"] == AT_CEILING_UNDECLARED:
            print("  UNDECLARED %-46s combined=%.4f" % (row["task"], row["combined_score"]))
        elif row["status"] == AT_CEILING_DECLARED:
            print("  declared   %-46s combined=%.4f (%s)"
                  % (row["task"], row["combined_score"], row["declared"]))
    print("%d of %d references were measurable; unmeasured tasks are not passes"
          % (len(measured), len(report["rows"])))
    print("report: %s" % args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
