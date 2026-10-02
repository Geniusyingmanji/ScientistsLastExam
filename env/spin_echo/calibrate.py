"""Operator-only, fixed one-batch author diagnostics with complete call ledger.

Run as a module with --plan and a new --output directory. Every production
trajectory, independent ODE, analytic reference and injected failure is charged.
This is numerical author verification, not an independent scientific review.
"""

import time
_PROCESS_WALL_START = time.monotonic()

import argparse
import copy
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import resource
import signal
import traceback

import numpy as np

from .baseline import baseline
from .kernel import Kernel, Parameters
from .protocol import validate_spec
from .reference import free_induction, ode_trajectory, single_echo
from .world import World

PLAN_SHA256 = "a0285e0e8242ebeb8b699226c01aaddc7ae6521b1f34a5f580bee1d05c0bce4c"
CLARIFICATION_SHA256 = "66a4667108a2c093cab2ff5e972d29459f6651788d81fa6b170d3bdb6c0d3645"


def jsonable(value):
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, dict):
        return {str(k): jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(v) for v in value]
    return value


def save(path, value):
    path.write_text(json.dumps(jsonable(value), indent=2, allow_nan=False)+"\n")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def cpu():
    usage = resource.getrusage(resource.RUSAGE_SELF)
    return usage.ru_utime + usage.ru_stime


class BudgetExceeded(BaseException):
    pass


class Budget:
    def __init__(self, output, limits):
        self.output, self.limits = output, limits
        self.attempts = []
        self.deadline = datetime.fromisoformat(limits["deadline_utc"].replace("Z", "+00:00")).timestamp()

    def elapsed(self):
        return {"cpu_seconds_process_total": cpu(), "wall_seconds_since_module_start": time.monotonic()-_PROCESS_WALL_START}

    def guard(self):
        now = self.elapsed()
        if now["cpu_seconds_process_total"] >= self.limits["cpu_seconds"]:
            raise BudgetExceeded("CPU budget exhausted")
        if now["wall_seconds_since_module_start"] >= self.limits["wall_seconds"] or time.time() >= self.deadline:
            raise BudgetExceeded("wall/deadline budget exhausted")

    def event(self, value):
        with (self.output/"attempt-ledger.jsonl").open("a") as stream:
            stream.write(json.dumps(jsonable(value), sort_keys=True, allow_nan=False)+"\n")
            stream.flush()
            os.fsync(stream.fileno())

    def attempt(self, label, kind, parameters, spec, operation, expected_error=None, noise_key=None):
        self.guard()
        if len(self.attempts) >= self.limits["maximum_top_level_trajectory_attempts"]:
            raise BudgetExceeded("attempt cap exhausted")
        record = {"attempt": len(self.attempts)+1, "label": label, "kind": kind,
                  "parameters": asdict(parameters), "spec": spec, "noise_key": noise_key,
                  "expected_error": expected_error, "started_at": datetime.now(timezone.utc).isoformat(),
                  "start_usage": self.elapsed(), "status": "began"}
        self.attempts.append(record)
        self.event({"event": "began", **record})
        result = None
        try:
            result = jsonable(operation())
            # Reject malformed or nonfinite outputs before recording success.
            json.dumps(result, allow_nan=False)
            record.update(status="unexpected_success" if expected_error else "success", result=result)
        except BaseException as exc:
            expected = bool(expected_error and type(exc).__name__ == expected_error["type"] and
                            expected_error["message_contains"] in str(exc))
            record.update(status="expected_failure" if expected else "failure", error={
                "type": type(exc).__name__, "message": str(exc), "traceback": traceback.format_exc()})
            if isinstance(exc, (BudgetExceeded, KeyboardInterrupt, SystemExit)):
                raise
        finally:
            record["end_usage"] = self.elapsed()
            self.event({"event": "ended", **record})
        self.guard()
        return result


def kernel_output(parameters, spec):
    values, diagnostics = Kernel(parameters).trajectory(spec)
    return {"values": values, "diagnostics": diagnostics}


def ode_output(parameters, spec):
    values, diagnostics = ode_trajectory(parameters, spec)
    return {"values": values, "diagnostics": diagnostics}


def execute(plan, budget, report):
    checks = report["checks"]

    def k(label, p, s):
        return budget.attempt(label, "kernel", p, s, lambda: kernel_output(p, s))

    def ref(label, p, s, fn):
        return budget.attempt(label, "reference", p, s, lambda: fn(p, s))

    def w(label, world, s, key=None):
        return budget.attempt(label, "world", world._kernel.parameters, s,
                              lambda: world.run(s, noise_key=key), noise_key=key)

    def check(label, result, **details):
        checks.append({"label": label, "status": "pass" if result else "fail", **jsonable(details)})

    def compare(label, a, b, tolerance, exact=False):
        if a is None or b is None:
            checks.append({"label": label, "status": "unassessable", "reason": "required fixed attempt failed"})
            return
        x, y = np.asarray(a["values"]), np.asarray(b["values"])
        error = float(np.max(np.abs(x-y)))
        check(label, np.array_equal(x, y) if exact else error <= tolerance,
              max_absolute_error=error, tolerance=tolerance, exact_equality_required=exact)

    fixtures = {item["name"]: Parameters(tuple(item["offsets_hz"]), tuple(item["weights"]), item["r2_per_s"])
                for item in plan["fixture_parameters"]}
    analytic_tol, ode_tol = plan["thresholds"]["analytic_absolute_error"], plan["thresholds"]["ODE_absolute_error"]
    norm_tol = plan["thresholds"]["norm_tolerance"]
    for fid, source, function in (("F1", "fixture_fid_spec", free_induction),
                                   ("F2", "fixture_echo_spec", single_echo),
                                   ("F3", "fixture_general_spec", None)):
        s = plan[source]
        for name, p in fixtures.items():
            a = k(f"{fid}/{name}/kernel", p, s)
            b = ref(f"{fid}/{name}/reference", p, s, ode_output if function is None else
                    lambda pp, ss, fn=function: {"values": fn(pp, ss)})
            compare(f"{fid}/{name}/reference_agreement", a, b, ode_tol if function is None else analytic_tol)
            if fid == "F3" and a is not None:
                maximum = float(np.linalg.norm(np.asarray(a["values"]), axis=1).max())
                initial_norm = float(np.linalg.norm(s["initial_magnetization"]))
                check(f"{fid}/{name}/norm", maximum <= initial_norm+norm_tol,
                      maximum_norm=maximum, initial_norm=initial_norm, tolerance=norm_tol)

    mixed, general = fixtures["mixed"], plan["fixture_general_spec"]
    dense = copy.deepcopy(general)
    dense["times_ms"] = sorted(set(np.linspace(0, 225, 81).tolist()+general["times_ms"]))
    a, b = k("F4/dense", mixed, dense), k("F4/subset", mixed, general)
    if a is not None:
        a = {"values": [a["values"][dense["times_ms"].index(t)] for t in general["times_ms"]]}
    compare("F4/exact_sample_invariance", a, b, 0, exact=True)

    corner = Parameters(tuple(np.linspace(-120, 120, 9).tolist()), tuple([1/9]*9), 40.)
    maximum_spec = validate_spec({"initial_magnetization": [.3, .4, .5], "detuning_hz": 40.,
        "times_ms": np.linspace(0, 250, 129).tolist(), "pulses": [
            {"time_ms": 1.+20*i, "angle_rad": [math.pi/2, -math.pi/3][i%2], "phase_rad": .2*i}
            for i in range(12)]})
    a, b = k("F5/legal_corner/kernel", corner, maximum_spec), ref("F5/legal_corner/reference", corner, maximum_spec, ode_output)
    compare("F5/legal_corner_reference", a, b, ode_tol)
    if a is not None:
        check("F5/finite_work", a["diagnostics"]["free_propagations"] <= 141 and a["diagnostics"]["rotations"] == 12,
              diagnostics=a["diagnostics"])

    pure = Parameters((0.,), (1.,), 0.)
    s = validate_spec({"initial_magnetization": [.3, .4, .5], "times_ms": [80.], "pulses": [
        {"time_ms": 20., "angle_rad": .3, "phase_rad": .7}, {"time_ms": 40., "angle_rad": .4, "phase_rad": .7}]})
    combined = copy.deepcopy(s)
    combined["pulses"] = [{"time_ms": 40., "angle_rad": .7, "phase_rad": .7}]
    compare("F6/same_axis_rotation_composition", k("F6/two_rotations", pure, s), k("F6/combined_rotation", pure, combined), analytic_tol)
    s = copy.deepcopy(plan["fixture_fid_spec"])
    s["times_ms"] = [80.]
    split = copy.deepcopy(s)
    split["pulses"] = [{"time_ms": 40., "angle_rad": 0., "phase_rad": 0.}]
    compare("F7/free_semigroup", k("F7/direct", mixed, s), k("F7/zero_angle_split", mixed, split), analytic_tol)
    zero = copy.deepcopy(maximum_spec)
    zero["initial_magnetization"] = [0., 0., 0.]
    a = k("F8/zero_state", corner, zero)
    if a is not None:
        check("F8/assigned_zero_state_invariance", np.count_nonzero(a["values"]) == 0,
              information="Assigned homogeneous model fact, no identification value")
    injected = Kernel(mixed)
    injected.MAX_FREE_PROPAGATIONS = 0
    budget.attempt("F9/injected_zero_budget", "kernel", mixed, general, lambda: injected.trajectory(general),
                   expected_error={"type": "RuntimeError", "message_contains": "propagation budget exhausted"})
    world = World(31001, _operator_stratum="static_frequency_spread")
    budget.attempt("F10/invalid_noise_key", "world", world._kernel.parameters, general,
                   lambda: world.run(general, noise_key=123),
                   expected_error={"type": "ValueError", "message_contains": "noise_key"}, noise_key=123)
    injected_nonfinite = Kernel(mixed)
    injected_nonfinite._free = lambda state, dt, detuning: np.full_like(state, np.nan)
    budget.attempt("F11/injected_nonfinite", "kernel", mixed, general,
                   lambda: injected_nonfinite.trajectory(general),
                   expected_error={"type": "RuntimeError", "message_contains": "became nonfinite"})

    for instance in plan["development_instances"]:
        seed, stratum = instance["seed"], instance["stratum"]
        world = World(seed, _operator_stratum=stratum)
        entry = {**instance, "parameters": asdict(world._kernel.parameters), "baseline": []}
        report["development"].append(entry)
        sources = [w(f"D/{seed}/source/{i}", world, s, f"development-source-{i}")
                   for i, s in enumerate(plan["source_specs"])]
        queries = [w(f"D/{seed}/query/{i}", world, s) for i, s in enumerate(plan["query_specs"])]
        p = world._kernel.parameters
        fid_reference = ref(f"D/{seed}/query0_FID_reference", p, plan["query_specs"][0],
                            lambda pp, ss: {"values": free_induction(pp, ss)})
        ode_reference = ref(f"D/{seed}/query3_ODE_reference", p, plan["query_specs"][3], ode_output)
        compare(f"D/{seed}/FID_reference", queries[0], fid_reference, analytic_tol)
        compare(f"D/{seed}/ODE_reference", queries[3], ode_reference, ode_tol)
        replay = w(f"D/{seed}/source0_same_key_replay", world, plan["source_specs"][0], "development-source-0")
        fresh = w(f"D/{seed}/source0_fresh_noise", world, plan["source_specs"][0], "development-source-0-fresh")
        clean = w(f"D/{seed}/source0_clean", world, plan["source_specs"][0])
        compare(f"D/{seed}/same_key_exact", sources[0], replay, 0, exact=True)
        if fresh is not None and sources[0] is not None:
            check(f"D/{seed}/fresh_noise_different", fresh != sources[0])
        if all(value is not None for value in (sources[0], fresh, clean)):
            residual = np.r_[np.asarray(sources[0]["values"])-np.asarray(clean["values"]),
                             np.asarray(fresh["values"])-np.asarray(clean["values"])]
            entry["noise_diagnostic"] = {"component_means": residual.mean(axis=0),
                                          "component_sample_stds": residual.std(axis=0, ddof=1),
                                          "residual_rows": len(residual), "assertion": "descriptive only; no tuned statistical threshold"}
        for prefix in (0, 1, 3):
            if any(source is None for source in sources[:prefix]):
                entry["baseline"].append({"records": prefix, "status": "unassessable_source_failure"})
                continue
            records = [{"spec": s, "observation": o} for s, o in zip(plan["source_specs"][:prefix], sources[:prefix])]
            for i, s in enumerate(plan["query_specs"]):
                if queries[i] is None:
                    entry["baseline"].append({"records": prefix, "query": i, "status": "unassessable_target_failure"})
                    continue
                try:
                    predicted = np.asarray(baseline(records, s))
                    target = np.asarray(queries[i]["values"])
                    positive = np.asarray(s["times_ms"]) > 0
                    error = predicted[positive]-target[positive]
                    entry["baseline"].append({"records": prefix, "query": i, "status": "computed",
                        "prediction": predicted, "rmse": float(np.sqrt(np.mean(error**2))),
                        "mae": float(np.mean(np.abs(error))), "component_rmse": np.sqrt(np.mean(error**2, axis=0)),
                        "positive_time_rows": int(positive.sum()),
                        "near_zero_clean_coordinates_included": int(np.count_nonzero(np.abs(target[positive]) <= 1e-12))})
                except Exception as exc:
                    entry["baseline"].append({"records": prefix, "query": i, "status": "failure", "error": str(exc)})
        # Parameter-blind panels are inspected without executing extra dynamics.
        entry["panel_checks"] = {}
        for kind in ("development", "conditions", "interventions"):
            panels = world.panel(47001, kind, count=8)
            entry["panel_checks"][kind] = {"specs": panels, "costs": [world.cost(s) for s in panels]}
        save(budget.output/f"development-{seed}.json", entry)

    settings = plan["ambiguity"]
    frequency = math.acos(math.exp(-8*.020))/(2*math.pi*.020)
    static = Parameters((-frequency, frequency), (.5, .5), 0.)
    decaying = Parameters((0.,), (1.,), 8.)
    ambiguity = {"frequency_hz": frequency,
                 "scope": "Broader kernel domain, outside generated static 5/7/9-member and SD8..20Hz ranges; not generated-strata calibration",
                 "contrasts": []}
    report["ambiguity"] = ambiguity
    serial = 1
    for name in ("restricted", "broad", "echo"):
        s = validate_spec({"initial_magnetization": [1., 0., 0.], "times_ms": settings[f"{name}_times_ms"],
            "pulses": [{"time_ms": 10., "angle_rad": math.pi, "phase_rad": 0.}] if name == "echo" else []})
        a, b = k(f"A{serial}/{name}/static", static, s), k(f"A{serial+1}/{name}/decay", decaying, s)
        serial += 2
        if a is not None and b is not None:
            difference = np.asarray(a["values"])-np.asarray(b["values"])
            maximum = float(np.max(np.abs(difference)))
            ambiguity["contrasts"].append({"protocol": name, "times_ms": s["times_ms"], "difference": difference,
                "max_absolute_component_difference": maximum, "max_difference_over_single_readout_std": maximum/.002,
                "max_difference_over_two_readout_difference_std": maximum/(math.sqrt(2)*.002),
                "interpretation": "Descriptive constructed contrast; no inferential p value or unique mechanism claim"})
    split = Parameters((mixed.offsets_hz[0],)+mixed.offsets_hz,
                       (mixed.weights[0]/2, mixed.weights[0]/2)+mixed.weights[1:], mixed.r2_per_s)
    for i in (2, 3):
        s = plan["query_specs"][i]
        a, b = k(f"A{serial}/equivalent/query{i}/original", mixed, s), k(f"A{serial+1}/equivalent/query{i}/split", split, s)
        serial += 2
        compare(f"A/equivalent/query{i}", a, b, analytic_tol)
    check("fixed_attempt_count", len(budget.attempts) == 112, observed=len(budget.attempts), expected=112)
    check("six_fixed_instances", len(report["development"]) == 6)
    for kind in ("development", "conditions", "interventions"):
        panels = [entry["panel_checks"][kind]["specs"] for entry in report["development"]]
        check(f"panels/{kind}/parameter_blind", all(value == panels[0] for value in panels))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    clarification = args.plan.parent/"clarification-001.json"
    if sha(args.plan) != PLAN_SHA256 or sha(clarification) != CLARIFICATION_SHA256:
        raise ValueError("immutable plan or pre-execution clarification hash mismatch")
    plan = json.loads(args.plan.read_text())
    # Unique output and campaign-level run guard prevent accidental batch retry.
    args.output.mkdir(parents=False, exist_ok=False)
    with (args.plan.parent/"CALIBRATION_STARTED.json").open("x") as stream:
        json.dump({"output": str(args.output.resolve()), "started_at": datetime.now(timezone.utc).isoformat(),
                   "policy": "one batch only; no retry after scientific outcomes"}, stream, indent=2)
    budget = Budget(args.output, plan["budget"])
    files = sorted(path for path in Path(__file__).parent.rglob("*") if path.is_file() and "__pycache__" not in path.parts)
    sources_before = {str(path.relative_to(Path(__file__).parent)): sha(path) for path in files}
    save(args.output/"source-hashes-before.json", sources_before)
    report = {"schema": "spin_echo_author_diagnostics_v1", "status": "started", "plan_sha256": PLAN_SHA256,
              "clarification_sha256": CLARIFICATION_SHA256, "checks": [], "development": [],
              "model_API_calls": 0, "planned_attempts": 112, "assessment": "author numerical diagnostics; independent review pending",
              "error_convention": "RMSE/MAE use every x/y/z coordinate at positive times, excluding assigned t=0. Waiting-constant z and known pulse responses remain included. This is not a shared task score or claim eligibility rule.",
              "baseline_policy": "0/1/3 public record prefixes; known-control algebra plus nearest empirical residual, no hidden parameter access or refitting; all 72 predictions reported without an improvement threshold"}
    save(args.output/"report.json", report)

    def timeout(signum, frame):
        raise BudgetExceeded("signal deadline or CPU limit: %s" % signum)

    signal.signal(signal.SIGALRM, timeout)
    signal.signal(signal.SIGXCPU, timeout)
    previous_limit = resource.getrlimit(resource.RLIMIT_CPU)
    soft = min(45, previous_limit[1]) if previous_limit[1] != resource.RLIM_INFINITY else 45
    resource.setrlimit(resource.RLIMIT_CPU, (soft, previous_limit[1]))
    remaining = min(180-(time.monotonic()-_PROCESS_WALL_START), budget.deadline-time.time())
    if remaining > 0:
        signal.setitimer(signal.ITIMER_REAL, remaining)
    try:
        budget.guard()
        execute(plan, budget, report)
        unexpected = [a for a in budget.attempts if a["status"] not in ("success", "expected_failure")]
        bad_checks = [c for c in report["checks"] if c["status"] != "pass"]
        bad_baselines = [b for d in report["development"] for b in d["baseline"] if b["status"] != "computed"]
        report["status"] = "completed_with_failures" if unexpected or bad_checks or bad_baselines else "completed"
    except BaseException as exc:
        report.update(status="partial_budget_exit" if isinstance(exc, BudgetExceeded) else "partial_exception",
                      fatal_error={"type": type(exc).__name__, "message": str(exc), "traceback": traceback.format_exc()})
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        resource.setrlimit(resource.RLIMIT_CPU, previous_limit)
        report["usage"] = {**budget.elapsed(), "attempts": len(budget.attempts), "maximum_attempts": 120,
                           "CPU_limit_seconds": 45, "wall_limit_seconds": 180,
                           "status_counts": {status: sum(a["status"] == status for a in budget.attempts)
                                             for status in sorted(set(a["status"] for a in budget.attempts))},
                           "kind_counts": {kind: sum(a["kind"] == kind for a in budget.attempts)
                                           for kind in sorted(set(a["kind"] for a in budget.attempts))}}
        report["attempts"] = budget.attempts
        after = {str(path.relative_to(Path(__file__).parent)): sha(path) for path in files}
        report["hash_verification"] = {"source_hashes_unchanged": sources_before == after,
                                       "plan_unchanged": sha(args.plan) == PLAN_SHA256,
                                       "clarification_unchanged": sha(clarification) == CLARIFICATION_SHA256}
        save(args.output/"source-hashes-after.json", after)
        save(args.output/"report.json", report)
        print(json.dumps({key: report[key] for key in ("status", "usage", "hash_verification")}, indent=2))
    return 0 if report["status"] == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
