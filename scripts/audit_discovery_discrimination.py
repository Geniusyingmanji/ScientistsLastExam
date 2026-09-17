#!/usr/bin/env python3
"""What a discovery task scores when nobody discovers anything.

Every discovery task normalizes a named baseline to 0 and a reference witness to 1, and
reports mechanism recovery, false discovery and calibrated refusal as separate axes. None
of that establishes that the score is *out of reach* without doing the science.
`shortcut_probe` asks exactly that question, but only for candidates an author thought to
declare, and three of the forty-six discovery tasks declare any.

This asks it mechanically. Four policies run against the task's own reference program and
its own sealed oracle. None of them knows anything about the task's science:

    reference        the reference program, unmodified. The control.
    abstain_all      the reference's own answer, with `abstain` forced true on every world.
    claim_all        the same answer, with `abstain` forced false on every world.
    constant_answer  the reference's first-world answer, replayed verbatim on every world.

Every policy submits an answer of the reference's own shape, so a high score is never an
artifact of malformed output being scored generously. Each of the forty-six discovery
evaluators validates an `abstain` boolean in the submitted mapping, which is what lets the
first two be written once instead of forty-six times.

How to read a row:

    abstain_all near reference      Silence collects the false-discovery and calibrated-
                                    refusal axes, and nothing charges for the coverage it
                                    gives up. The refusal axis is a free ride.
    claim_all near reference        The worlds where no claim is recoverable are too few,
                                    or too lightly weighted, to punish overclaiming.
    constant_answer near reference  The worlds do not differ enough to require looking at
                                    them. One memorized answer covers the task.

A task where any policy lands near its reference does not separate discovery from the
absence of discovery, whatever its per-axis numbers say. The threshold is the same shape
the shortcut-probe contract already uses: a policy is a finding when it reaches
`reference * (1 - margin)`.

This is a measurement, not a gate. It runs a task's real oracle for real, so it is slow,
and it reports what it could not run rather than scoring those tasks zero.
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import yaml  # noqa: E402

from sle.registry import list_tasks  # noqa: E402
from sle.secure_eval import (  # noqa: E402
    CandidateProxy,
    load_oracle,
    read_candidate_packages,
    validate_metrics,
)

TAXONOMY = ROOT / "sle/conf/exam_taxonomy.yaml"
DEFAULT_MARGIN = 0.15

# Axes whose ceiling is 1.0 and whose floor is 0.0, plus the ones that inverted.
CEILING_AT_ONE = ("correct_refusal_rate", "discovery_coverage", "mechanism_score",
                  "mechanism_recovery", "coverage")
CEILING_AT_ZERO = ("false_discovery_rate",)


class Policy:
    """A stand-in for the candidate that the oracle cannot tell from the real one.

    The oracle calls the candidate once per world and may call `reset_session` between
    worlds; both are forwarded so the sandbox lifecycle is exactly the reference's.
    """

    name = "reference"

    def __init__(self, inner):
        self.inner = inner
        self.calls = 0
        self.notes: list[str] = []

    def reset_session(self):
        reset = getattr(self.inner, "reset_session", None)
        if reset is not None:
            reset()

    def __call__(self, *args, **kwargs):
        self.calls += 1
        return self.inner(*args, **kwargs)


MAX_REWRITE_DEPTH = 3


def _set_abstain(value, flag: bool, depth: int = 0) -> int:
    """Rewrite every `abstain` flag inside a submitted structure. Returns how many.

    A task may carry its claim in the returned mapping, or commit it through a callback and
    return something else, or do both. ProspectiveMetaAnalysis scores `commit["preconfirmation"]`
    -- the artifact handed to its `confirm` tool -- and the false-discovery and correct-refusal
    axes read that artifact, not the value the candidate finally returns. A probe that rewrites
    only the return value leaves those axes untouched and then looks like it proved them
    insensitive, which is a claim about the probe and not about the task.

    The walk is depth-bounded because a submission is a small record, and an unbounded walk
    over whatever an oracle hands back is a way to hang on a cycle.
    """
    if depth > MAX_REWRITE_DEPTH or not isinstance(value, dict):
        return 0
    count = 0
    for key, sub in value.items():
        if key == "abstain" and isinstance(sub, (bool, int)) and not isinstance(sub, float):
            value[key] = flag
            count += 1
        else:
            count += _set_abstain(sub, flag, depth + 1)
    if count and flag:
        # Declining and asserting at once is not a decline, and a task is entitled to reject
        # it: ProspectiveMetaAnalysis raises `an abstaining model cannot claim benefit`, which
        # would have scored this policy as a crash rather than as a refusal. Withdraw the
        # sibling assertions so the submission is the refusal it claims to be.
        for key, sub in value.items():
            if key.startswith("claim") and isinstance(sub, bool):
                value[key] = False
    return count


class AbstainAll(Policy):
    """The reference's own answer, with every abstain flag forced to one value.

    Both halves of the answer are rewritten: the arguments of every callback the oracle
    supplies, so a claim committed mid-run is committed with the flag flipped, and the value
    the candidate returns. `rewrites` records how many flags were actually moved, so an axis
    that did not respond can be told apart from an input that was never touched.
    """

    name = "abstain_all"
    flag = True

    def __init__(self, inner):
        super().__init__(inner)
        self.rewrites = 0
        self.callback_rewrites = 0

    def _rewritten(self, value, *, callback: bool):
        if not isinstance(value, dict):
            return value
        value = copy.deepcopy(value)
        moved = _set_abstain(value, self.flag)
        self.rewrites += moved
        if callback:
            self.callback_rewrites += moved
        return value

    def _wrap_callback(self, callback):
        def rewriting(*args, **kwargs):
            return callback(*[self._rewritten(a, callback=True) for a in args],
                            **{k: self._rewritten(v, callback=True)
                               for k, v in kwargs.items()})
        return rewriting

    def __call__(self, *args, **kwargs):
        self.calls += 1
        args = [self._wrap_callback(a) if callable(a) else a for a in args]
        answer = self._rewritten(self.inner(*args, **kwargs), callback=False)
        if self.rewrites == 0:
            raise NotApplicable("no abstain flag reached in submission or callbacks")
        return answer


class ClaimAll(AbstainAll):
    name = "claim_all"
    flag = False


class ConstantAnswer(Policy):
    """Answer the first world honestly, then hand the oracle that same answer every time.

    A deep copy goes out each call so that an oracle which consumes or mutates the
    submission cannot change what later worlds receive.
    """

    name = "constant_answer"

    def __init__(self, inner):
        super().__init__(inner)
        self.first = None

    def __call__(self, *args, **kwargs):
        self.calls += 1
        if self.first is None:
            self.first = copy.deepcopy(self.inner(*args, **kwargs))
        return copy.deepcopy(self.first)


POLICIES = {cls.name: cls for cls in (Policy, AbstainAll, ClaimAll, ConstantAnswer)}


class NotApplicable(Exception):
    """The policy cannot be built for this task; that is a result, not a failure."""


def discovery_tasks() -> dict[str, dict]:
    tasks = yaml.safe_load(TAXONOMY.read_text(encoding="utf-8"))["tasks"]
    return {tid: meta for tid, meta in tasks.items() if meta.get("form") == "discovery"}


# Names that mark a program as a deliberately weakened variant rather than the witness the
# task normalizes to. Three discovery packages ship several entrypoint programs, and picking
# the wrong one measures an ablation against its own degenerate policies, which is a number
# about nothing.
ABLATION_MARKERS = ("ablation", "probe", "_no_", "no_active", "baseline", "legacy")


def declared_reference(task_dir: Path, field: str = "candidate"):
    """What the task card says about its own reference, which is authoritative where it exists."""
    card = Path(task_dir) / "TASK_CARD.yaml"
    if not card.is_file():
        return None
    try:
        contract = (yaml.safe_load(card.read_text(encoding="utf-8")) or {}).get("shortcut_probe")
    except yaml.YAMLError:
        return None
    if not isinstance(contract, dict):
        return None
    reference = contract.get("reference")
    if isinstance(reference, dict):
        return reference.get(field)
    return None


def reference_program(spec) -> Path | None:
    """The program the task normalizes to 1, if the package ships one.

    The card's `shortcut_probe.reference` wins wherever it is declared: TransitTimingAttribution
    ships `reference_no_active_design.py` beside `reference_solver.py`, and only the card says
    which of the two is the witness and which is the ablation it is supposed to beat.

    Nine discovery tasks anchor on simulator truth and ship no reference program at all. They
    have no control to compare a policy against, so they are reported, not run.
    """
    import re

    entry = spec.entrypoint
    if not entry:
        return None
    task_dir = Path(spec.task_dir)
    declared = declared_reference(task_dir)
    if declared:
        candidate = task_dir / declared
        if candidate.is_file():
            return candidate
    found = []
    for path in sorted(task_dir.rglob("*.py")):
        rel = path.relative_to(task_dir)
        if rel.parts[0] in ("frontier_eval", "runs") or "__pycache__" in rel.parts:
            continue
        if rel.as_posix() == "solution.py":
            continue  # the baseline, by construction the 0 of the scale
        source = path.read_text(encoding="utf-8", errors="replace")
        if re.search(r"^\s*def\s+%s\s*\(" % re.escape(entry), source, re.M):
            found.append(path)
    if not found:
        return None
    witnesses = [p for p in found
                 if not any(marker in p.name.lower() for marker in ABLATION_MARKERS)]
    named = [p for p in (witnesses or found) if "reference" in p.name.lower()]
    return sorted(named or witnesses or found, key=lambda p: (len(p.parts), str(p)))[0]


def run_policy(spec, candidate: Path, policy_name: str, timeout_s: float,
               score_mode: str) -> dict:
    """One full oracle evaluation with the candidate wrapped in the named policy."""
    oracle = load_oracle(Path(spec.task_dir))
    factory = POLICIES[policy_name]
    started = time.monotonic()
    with CandidateProxy(candidate, spec.entrypoint, timeout_s,
                        packages=read_candidate_packages(Path(spec.task_dir))) as proxy:
        policy = factory(proxy)
        metrics = oracle(policy)
        if proxy.failure is not None:
            raise proxy.failure
    row = {
        "policy": policy_name,
        "metrics": validate_metrics(metrics, score_mode),
        "candidate_calls": policy.calls,
        "notes": policy.notes,
        "wall_seconds": time.monotonic() - started,
    }
    if hasattr(policy, "rewrites"):
        row["abstain_flags_rewritten"] = policy.rewrites
        row["abstain_flags_rewritten_in_callbacks"] = policy.callback_rewrites
    row["outcome"] = _outcome(row)
    return row


def _outcome(run: dict) -> str:
    """Why this policy's number is what it is. A zero has three very different causes.

    `scored`          the oracle accepted the submission and gave it this number. Only these
                      rows say anything about how well the task is defended.
    `not_applicable`  the probe found no abstain flag to move, so the policy was never really
                      built. Some oracles absorb the resulting candidate error into an invalid
                      world instead of propagating it, and the run then reports a clean 0.0
                      that reads exactly like a defended task. CacheReplacementPolicyID and
                      SparseVectorAudit both did this.
    `rejected`        the flip produced a submission the oracle refused as malformed. That is
                      the task declining to score the strategy, not the strategy scoring low,
                      and it must not be counted as either.
    """
    if run.get("abstain_flags_rewritten") == 0:
        return "not_applicable"
    metrics = run.get("metrics") or {}
    if float(metrics.get("valid", 0.0)) != 1.0:
        return "rejected"
    return "scored"


def saturated_axes(metrics: dict) -> list[str]:
    """Axes the reference already pins to their best value, so nothing above it can show."""
    out = []
    for key, value in metrics.items():
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            continue
        if any(key.endswith(s) for s in CEILING_AT_ONE) and float(value) == 1.0:
            out.append(key)
        elif any(key.endswith(s) for s in CEILING_AT_ZERO) and float(value) == 0.0:
            out.append(key)
    return sorted(out)


# Metrics that are constant across policies by construction, and say nothing when they are.
# Two separate reasons, kept apart because they are different claims:
#   structural - a property of the sealed world set, not of the answer. The number of worlds,
#                the denominator of a rate, a fixed anchor constant. These cannot move.
#   probe-bound - a property of how these policies are built. All three wrap the *same*
#                reference program, so they issue the same experiments and spend the same
#                budget. Their resource counters agree because the probe made them agree.
STRUCTURAL_SUFFIXES = ("_world_count", "_denominator", "_anchor", "_numerator")
PROBE_BOUND_MARKERS = ("mean_", "_used", "_calls", "budget", "feasibility", "valid")


def calibration_blind_axes(runs: dict) -> list[str]:
    """Axes that report the same number whether the candidate claims everywhere or refuses.

    `abstain_all` and `claim_all` are the two ends of the calibration decision. An axis whose
    stated job is to price that decision -- a false-discovery rate, a count of false claims --
    should move between them. Measured, most do not.

    On ComplexBoseLaw the refusal and coverage axes respond exactly as intended
    (`correct_refusal_rate` 1.0 -> 0.0, `discovery_coverage` 0.0 -> 1.0), while
    `false_discovery_rate` stays 0.0 for a candidate that asserts on every world including the
    ones where nothing is recoverable. Its false-discovery test fires on one specific wrong
    claim -- calling a non-Bose world Bose -- and forcing the flag off submits the reference's
    own, correct, family label. So a maximally over-claiming candidate publishes a perfect
    false-discovery rate.

    That is the finding, and it is narrower than "the axis is broken": over-claiming is priced
    once, through refusal, and the false-discovery number cannot be read on its own as "this
    candidate made no unsupported claims". Where the denominator is genuinely empty the result
    is worse -- ProspectiveMetaAnalysis returns `1.0` for `unsupported_refusal_rate` when no
    unsupported world exists, which is a test that never ran reported as a pass.

    Structural and probe-bound metrics are excluded: see the two lists above. All three runs
    must have been scored; an axis from a submission the oracle refused, or from a policy that
    moved no flag, says something about the probe rather than about the task.
    """
    needed = ("reference", "abstain_all", "claim_all")
    compared = [runs[name]["metrics"] for name in needed
                if name in runs and runs[name].get("outcome") == "scored"]
    if len(compared) < 3:
        return []
    shared = set.intersection(*(set(m) for m in compared))
    out = []
    for key in sorted(shared):
        if any(key.endswith(suffix) for suffix in STRUCTURAL_SUFFIXES):
            continue
        if any(marker in key for marker in PROBE_BOUND_MARKERS):
            continue
        values = [m[key] for m in compared]
        if not all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in values):
            continue
        if len(set(float(v) for v in values)) == 1:
            out.append(key)
    return out


def audit_task(spec, margin: float, timeout_s: float | None,
               policies: list[str]) -> dict:
    meta = spec.metadata
    score_mode = str(meta.get("score_mode", "clipped"))
    budget = float(timeout_s or meta.get("eval_time_seconds") or 600)
    row: dict = {"task": spec.task_id, "discipline": spec.discipline,
                 "score_mode": score_mode, "timeout_s": budget, "runs": {}}
    candidate = reference_program(spec)
    if candidate is None:
        row["status"] = "no_reference_program"
        return row
    row["reference_program"] = str(candidate.relative_to(spec.task_dir))
    for name in policies:
        try:
            row["runs"][name] = run_policy(spec, candidate, name, budget, score_mode)
        except NotApplicable as exc:
            row["runs"][name] = {"policy": name, "status": "not_applicable",
                                 "detail": str(exc)}
        except Exception as exc:  # noqa: BLE001 - a task that will not run is a result
            row["runs"][name] = {"policy": name, "status": "error",
                                 "detail": "%s: %s" % (type(exc).__name__, exc),
                                 "traceback": traceback.format_exc(limit=4)}
    control = row["runs"].get("reference", {}).get("metrics")
    if not control:
        row["status"] = "reference_did_not_run"
        return row
    row["status"] = "measured"
    reference_score = float(control["combined_score"])
    row["reference_score"] = reference_score
    # Where the card states what its reference scores, say whether this run agrees. Three
    # discovery packages ship an ablation named `reference_*` beside the real witness, and a
    # picker that chose wrong would otherwise report a whole row of ratios against the wrong
    # denominator without anything noticing.
    expected = declared_reference(Path(spec.task_dir), "expected_score")
    if isinstance(expected, (int, float)) and not isinstance(expected, bool):
        row["declared_reference_score"] = float(expected)
        row["matches_declared_reference"] = abs(reference_score - float(expected)) <= 1e-6
    row["reference_saturated_axes"] = saturated_axes(control)
    threshold = reference_score * (1.0 - margin)
    row["threshold"] = threshold
    findings = []
    for name, run in row["runs"].items():
        if name == "reference" or run.get("outcome") != "scored":
            continue
        score = float(run["metrics"]["combined_score"])
        run["ratio_to_reference"] = (score / reference_score) if reference_score else None
        run["reaches_threshold"] = bool(reference_score > 0 and score >= threshold)
        if run["reaches_threshold"]:
            findings.append(name)
    row["findings"] = findings
    row["calibration_blind_axes"] = calibration_blind_axes(row["runs"])
    # Only a task where every policy was actually scored, and none of them came near, has been
    # shown to separate discovery from its absence. One where a policy could not be built is
    # untested against that policy, which is not the same as passing.
    row["policy_outcomes"] = {name: run.get("outcome", run.get("status", "error"))
                              for name, run in row["runs"].items() if name != "reference"}
    row["discriminative"] = bool(
        reference_score > 0 and not findings
        and all(outcome == "scored" for outcome in row["policy_outcomes"].values()))
    return row


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--task", action="append", default=[],
                        help="task id; repeatable. Default: every discovery task.")
    parser.add_argument("--margin", type=float, default=DEFAULT_MARGIN,
                        help="a policy is a finding at reference * (1 - margin)")
    parser.add_argument("--timeout", type=float, default=None,
                        help="override the task's own eval_time_seconds")
    parser.add_argument("--policies", default=",".join(POLICIES),
                        help="comma-separated subset of: %s" % ", ".join(POLICIES))
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("--reanalyze", type=Path, default=None,
                        help="recompute the derived checks over a report's stored metrics "
                             "and write it to --output; runs no oracle")
    args = parser.parse_args()

    if args.reanalyze is not None:
        return _reanalyze(args)

    wanted = list(dict.fromkeys(args.policies.split(",")))
    unknown = [p for p in wanted if p not in POLICIES]
    if unknown:
        parser.error("unknown policies: %s" % ", ".join(unknown))
    if "reference" not in wanted:
        wanted.insert(0, "reference")

    discovery = discovery_tasks()
    specs = {s.task_id: s for s in list_tasks(None)}
    selected = args.task or sorted(discovery)
    missing = [t for t in selected if t not in discovery]
    if missing:
        parser.error("not discovery tasks: %s" % ", ".join(missing))

    rows = []
    for task_id in selected:
        spec = specs.get(task_id)
        if spec is None:
            rows.append({"task": task_id, "status": "not_in_registry"})
            continue
        row = audit_task(spec, args.margin, args.timeout, wanted)
        row["kind"] = discovery[task_id].get("kind")
        rows.append(row)
        if not args.quiet:
            _print_row(row)
            sys.stdout.flush()
        if args.output:
            # A full sweep is hours of real oracle time; write after every task so an
            # interrupted run still leaves the tasks it finished.
            _write(args, wanted, rows)

    if args.output:
        _write(args, wanted, rows)
    if not args.quiet:
        print("\n" + json.dumps(_summarize(rows), ensure_ascii=False, indent=1))
    return 0


def _reanalyze(args) -> int:
    """Apply the current derived checks to metrics a previous sweep already paid for."""
    report = json.loads(args.reanalyze.read_text(encoding="utf-8"))
    margin = args.margin if args.margin != DEFAULT_MARGIN else report.get("margin", DEFAULT_MARGIN)
    for row in report["tasks"]:
        if row.get("status") != "measured":
            continue
        control = row["runs"]["reference"]["metrics"]
        reference_score = float(control["combined_score"])
        row["reference_score"] = reference_score
        row["reference_saturated_axes"] = saturated_axes(control)
        row["threshold"] = reference_score * (1.0 - margin)
        findings = []
        for name, run in row["runs"].items():
            if "metrics" not in run:
                continue
            run["outcome"] = _outcome(run)
            if name == "reference":
                continue
            if run["outcome"] != "scored":
                run.pop("reaches_threshold", None)
                continue
            score = float(run["metrics"]["combined_score"])
            run["ratio_to_reference"] = (score / reference_score) if reference_score else None
            run["reaches_threshold"] = bool(reference_score > 0 and score >= row["threshold"])
            if run["reaches_threshold"]:
                findings.append(name)
        row["findings"] = findings
        row["calibration_blind_axes"] = calibration_blind_axes(row["runs"])
        row["policy_outcomes"] = {name: run.get("outcome", run.get("status", "error"))
                                  for name, run in row["runs"].items() if name != "reference"}
        row["discriminative"] = bool(
            reference_score > 0 and not findings
            and all(o == "scored" for o in row["policy_outcomes"].values()))
        if not args.quiet:
            _print_row(row)
    report["margin"] = margin
    report["summary"] = _summarize(report["tasks"])
    if args.output:
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=1),
                               encoding="utf-8")
    if not args.quiet:
        print("\n" + json.dumps(report["summary"], ensure_ascii=False, indent=1))
    return 0


def _write(args, policies: list[str], rows: list[dict]) -> None:
    args.output.write_text(json.dumps({
        "schema_version": 1,
        "margin": args.margin,
        "policies": policies,
        "tasks": rows,
        "summary": _summarize(rows),
    }, ensure_ascii=False, indent=1), encoding="utf-8")


def _print_row(row: dict) -> None:
    if row.get("status") != "measured":
        print("%-52s %s" % (row["task"], row.get("status")))
        return
    parts = []
    for name, run in row["runs"].items():
        if name == "reference":
            continue
        if "metrics" not in run:
            parts.append("%s=%s" % (name, run.get("status")))
            continue
        parts.append("%s=%.4f(%.0f%%)%s" % (
            name, run["metrics"]["combined_score"],
            100 * (run.get("ratio_to_reference") or 0),
            "!" if run["reaches_threshold"] else ""))
    print("%-52s ref=%.4f  %s%s" % (
        row["task"], row["reference_score"], "  ".join(parts),
        "   saturated:" + ",".join(row["reference_saturated_axes"])
        if row["reference_saturated_axes"] else ""))


def _summarize(rows: list[dict]) -> dict:
    measured = [r for r in rows if r.get("status") == "measured"]
    broken = [r for r in measured if r.get("findings")]
    by_policy: dict[str, list[str]] = {}
    for row in broken:
        for name in row["findings"]:
            by_policy.setdefault(name, []).append(row["task"])
    return {
        "selected": len(rows),
        "measured": len(measured),
        "not_measured": {r["task"]: r.get("status") for r in rows
                         if r.get("status") != "measured"},
        "discriminative": sorted(r["task"] for r in measured if r.get("discriminative")),
        "reached_by_a_policy": {k: sorted(v) for k, v in sorted(by_policy.items())},
        "reference_saturated": sorted(
            r["task"] for r in measured if r.get("reference_saturated_axes")),
        "calibration_blind_axes": {r["task"]: r["calibration_blind_axes"] for r in measured
                                  if r.get("calibration_blind_axes")},
        "policy_outcomes": {
            outcome: sorted("%s:%s" % (r["task"], name) for r in measured
                            for name, value in (r.get("policy_outcomes") or {}).items()
                            if value == outcome)
            for outcome in ("not_applicable", "rejected", "error")
        },
    }


if __name__ == "__main__":
    raise SystemExit(main())
