"""One fixed author batch: solver counts and parent World wrappers are separate."""

import time
_WALL_START = time.monotonic()

import argparse
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
from .protocol import assigned_initial
from .reference import neutral_moments, neutral_n2, uniformization
from .world import World

PLAN_SHA256 = "c92d13df356dcf002b45a4bab0f93bf9f8e6276fc1130f9d542b305bce434ac8"


def jsonable(value):
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, dict):
        return {str(k): jsonable(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [jsonable(v) for v in value]
    return value


def save(path, value):
    path.write_text(json.dumps(jsonable(value), indent=2, allow_nan=False)+"\n")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def cpu():
    value = resource.getrusage(resource.RUSAGE_SELF)
    return value.ru_utime+value.ru_stime


class BudgetExceeded(BaseException):
    pass


def kernel_output(operation, spec):
    values, diagnostics = operation(spec)
    return {"values": values, "diagnostics": diagnostics}


class Ledger:
    def __init__(self, output, limits):
        self.output, self.limits = output, limits
        self.records = []
        self.solvers, self.wrappers = 0, 0
        self.deadline = datetime.fromisoformat(limits["deadline_utc"].replace("Z", "+00:00")).timestamp()

    def usage(self):
        return {"CPU_seconds_process_total": cpu(), "wall_seconds_since_module_start": time.monotonic()-_WALL_START}

    def guard(self):
        current = self.usage()
        if current["CPU_seconds_process_total"] >= self.limits["CPU_seconds_process"]:
            raise BudgetExceeded("CPU budget exhausted")
        if current["wall_seconds_since_module_start"] >= self.limits["wall_seconds_process"] or time.time() >= self.deadline:
            raise BudgetExceeded("wall/deadline budget exhausted")

    def event(self, value):
        with (self.output/"attempt-ledger.jsonl").open("a") as f:
            f.write(json.dumps(jsonable(value), sort_keys=True, allow_nan=False)+"\n")
            f.flush()
            os.fsync(f.fileno())

    def call(self, role, kind, label, parameters, spec, operation, parent_id=None,
             expected_error=None, noise_key=None, propagate=False):
        self.guard()
        if role == "solver":
            if self.solvers >= self.limits["maximum_solver_evaluations"]:
                raise BudgetExceeded("solver evaluation cap exhausted")
            self.solvers += 1
            identifier = f"S{self.solvers:03d}"
        else:
            self.wrappers += 1
            identifier = f"W{self.wrappers:03d}"
        record = {"id": identifier, "parent_id": parent_id, "role": role, "kind": kind, "label": label,
                  "parameters": asdict(parameters), "spec": spec, "noise_key": noise_key,
                  "expected_error": expected_error, "status": "began",
                  "started_at": datetime.now(timezone.utc).isoformat(), "start_usage": self.usage()}
        self.records.append(record)
        self.event({"event": "began", **record})
        result, caught = None, None
        try:
            result = operation(identifier)
            stored = jsonable(result)
            json.dumps(stored, allow_nan=False)
            record.update(status="unexpected_success" if expected_error else "success", result=stored)
        except BaseException as exc:
            caught = exc
            expected = bool(expected_error and type(exc).__name__ == expected_error["type"] and
                            expected_error["message_contains"] in str(exc))
            record.update(status="expected_failure" if expected else "failure", error={
                "type": type(exc).__name__, "message": str(exc), "traceback": traceback.format_exc()})
        finally:
            record["end_usage"] = self.usage()
            self.event({"event": "ended", **record})
        if caught and (propagate or isinstance(caught, (BudgetExceeded, KeyboardInterrupt, SystemExit))):
            raise caught
        self.guard()
        return result

    def solver(self, kind, label, parameters, spec, operation, **kwargs):
        return self.call("solver", kind, label, parameters, spec, lambda _: operation(), **kwargs)

    def world(self, label, world, spec, noise_key=None, expected_error=None):
        """Log the wrapper and exactly one nested solver when validation reaches it."""
        parameters = world._kernel.parameters

        def run(parent_id):
            original = world._kernel.trajectory

            def observed(canonical):
                result = self.solver("kernel", label+"/kernel", parameters, canonical,
                    lambda: kernel_output(original, canonical), parent_id=parent_id, propagate=True)
                return result["values"], result["diagnostics"]

            world._kernel.trajectory = observed
            try:
                return world.run(spec, noise_key=noise_key)
            finally:
                world._kernel.trajectory = original

        return self.call("wrapper", "World.run", label, parameters, spec, run,
                         expected_error=expected_error, noise_key=noise_key)


def execute(plan, ledger, report):
    checks = report["checks"]
    thresholds = plan["thresholds"]
    parameters = {name: Parameters(**raw) for name, raw in plan["fixture_parameters"].items()}
    specs = plan["fixture_specs"]

    def check(label, passed, **details):
        checks.append({"label": label, "status": "pass" if passed else "fail", **jsonable(details)})

    def compare(label, a, b, tolerance, left_columns=None, exact=False):
        if a is None or b is None:
            checks.append({"label": label, "status": "unassessable", "reason": "required fixed attempt failed"})
            return
        x, y = np.asarray(a["values"]), np.asarray(b["values"])
        if left_columns is not None:
            x = x[:, left_columns]
        error = float(np.max(np.abs(x-y)))
        check(label, np.array_equal(x, y) if exact else error <= tolerance,
              maximum_absolute_error=error, tolerance=tolerance, exact_equality_required=exact)

    def kernel(label, p, s):
        return ledger.solver("kernel", label, p, s, lambda: kernel_output(Kernel(p).trajectory, s))

    def reference(label, p, s, function):
        return ledger.solver("reference", label, p, s, lambda: function(p, s))

    def distribution_compare(label, a, b):
        if a is not None and b is not None:
            compare(label, {"values": a["diagnostics"]["probabilities"]}, {"values": b["probabilities"]}, thresholds["uniformization_absolute"])

    p, s = parameters["neutral"], specs["neutral_moments"]
    a = kernel("F1/neutral/kernel", p, s)
    b = reference("F1/neutral/analytic", p, s, lambda pp, ss: neutral_moments(ss))
    compare("F1/neutral_moments", a, b, thresholds["analytic_absolute"], left_columns=[0, 1])
    s = specs["neutral_n2"]
    a = kernel("F2/N2/kernel", p, s)
    b = reference("F2/N2/analytic", p, s, lambda pp, ss: neutral_n2(ss))
    compare("F2/N2_full_observables", a, b, thresholds["analytic_absolute"])
    distribution_compare("F2/N2_full_distribution", a, b)
    for boundary in ("boundary_0", "boundary_N"):
        s = specs[boundary]
        a = kernel(f"F3/{boundary}", parameters["biased_no_mutation"], s)
        compare(f"F3/{boundary}/no_mutation_absorption", a,
                {"values": [assigned_initial(s)]*len(s["times"])}, thresholds["analytic_absolute"])
    p, s = parameters["mutator"], specs["mutation_symmetric"]
    a, b = kernel("F4/mutation/kernel", p, s), reference("F4/mutation/reference", p, s, uniformization)
    compare("F4/mutation_observables", a, b, thresholds["uniformization_absolute"])
    distribution_compare("F4/mutation_distribution", a, b)
    if a is not None:
        check("F4/mutation_mean_symmetry", np.max(np.abs(np.asarray(a["values"])[:, 0]-.5)) <= thresholds["analytic_absolute"])
    matrices = []
    p = parameters["mixed"]
    for t in (7, 11, 18):
        s = specs[f"semigroup_{t}"]
        matrices.append(ledger.solver("kernel_transition_matrix", f"F5/semigroup/{t}", p, s,
            lambda ss=s: kernel_output(Kernel(p).transition_matrices, ss)))
    if all(value is not None for value in matrices):
        compare("F5/semigroup", {"values": matrices[0]["values"][0] @ matrices[1]["values"][0]},
                {"values": matrices[2]["values"][0]}, thresholds["semigroup_absolute"])
    p, s = parameters["corner"], specs["legal_corner"]
    a, b = kernel("F6/corner/kernel", p, s), reference("F6/corner/reference", p, s, uniformization)
    compare("F6/legal_corner_observables", a, b, thresholds["uniformization_absolute"])
    distribution_compare("F6/legal_corner_distribution", a, b)
    if a is not None and b is not None:
        check("F6/work_and_tail_limits", a["diagnostics"]["matrix_exponentials"] <= 33 and
              b["diagnostics"]["terms"] <= 2500 and max(b["diagnostics"]["tail_chernoff_bounds"]) <= math.exp(-40),
              production=a["diagnostics"], reference=b["diagnostics"])
    p = parameters["mixed"]
    a, b = kernel("F7/dense", p, specs["dense"]), kernel("F7/subset", p, specs["subset"])
    if a is not None:
        a = {"values": [a["values"][specs["dense"]["times"].index(t)] for t in specs["subset"]["times"]]}
    compare("F7/exact_sample_invariance", a, b, 0, exact=True)
    injected = Kernel(p)
    injected.MAX_EXPONENTIALS = 0
    s = specs["injected"]
    ledger.solver("kernel", "F8/injected_zero_budget", p, s, lambda: kernel_output(injected.trajectory, s),
                  expected_error={"type": "RuntimeError", "message_contains": "budget exhausted"})
    world = World(41001, _operator_stratum="neutral_drift")
    ledger.world("F9/invalid_noise_key", world, s, noise_key=123,
                 expected_error={"type": "ValueError", "message_contains": "noise_key"})
    nonfinite = Kernel(p)
    nonfinite._rates = lambda ss: (np.full(ss["population_size"]+1, np.nan), np.zeros(ss["population_size"]+1))
    ledger.solver("kernel", "F10/injected_nonfinite", p, s, lambda: kernel_output(nonfinite.trajectory, s),
                  expected_error={"type": "RuntimeError", "message_contains": "generator"})

    for instance in plan["development_instances"]:
        seed, stratum = instance["seed"], instance["stratum"]
        world = World(seed, _operator_stratum=stratum)
        p = world._kernel.parameters
        entry = {**instance, "parameters": asdict(p), "baseline": []}
        report["development"].append(entry)
        sources = [ledger.world(f"D/{seed}/source/{i}", world, s, noise_key=f"source-{i}")
                   for i, s in enumerate(plan["source_specs"])]
        queries = [ledger.world(f"D/{seed}/query/{i}", world, s) for i, s in enumerate(plan["query_specs"])]
        ref = reference(f"D/{seed}/query0/reference", p, plan["query_specs"][0], uniformization)
        compare(f"D/{seed}/independent_reference", queries[0], ref, thresholds["uniformization_absolute"])
        replay = ledger.world(f"D/{seed}/source0_same_key", world, plan["source_specs"][0], noise_key="source-0")
        fresh = ledger.world(f"D/{seed}/source0_fresh_key", world, plan["source_specs"][0], noise_key="source-0-fresh")
        clean = ledger.world(f"D/{seed}/source0_clean", world, plan["source_specs"][0])
        compare(f"D/{seed}/same_key_exact", sources[0], replay, 0, exact=True)
        if sources[0] is not None and fresh is not None:
            check(f"D/{seed}/fresh_noise_different", sources[0] != fresh)
        if all(v is not None for v in (sources[0], fresh, clean)):
            residual = np.r_[np.asarray(sources[0]["values"])-np.asarray(clean["values"]),
                             np.asarray(fresh["values"])-np.asarray(clean["values"])]
            entry["noise"] = {"component_means": residual.mean(axis=0), "component_sample_stds": residual.std(axis=0, ddof=1),
                              "rows": len(residual), "interpretation": "sensor residual descriptive statistics only; internal drift is already integrated"}
        for prefix in (0, 1, 2):
            if any(source is None for source in sources[:prefix]):
                entry["baseline"].append({"records": prefix, "status": "unassessable_source_failure"})
                continue
            records = [{"spec": s, "observation": observation} for s, observation in zip(plan["source_specs"][:prefix], sources[:prefix])]
            for i, s in enumerate(plan["query_specs"]):
                if queries[i] is None:
                    entry["baseline"].append({"records": prefix, "query": i, "status": "unassessable_target_failure"})
                    continue
                try:
                    predicted, target = np.asarray(baseline(records, s)), np.asarray(queries[i]["values"])
                    positive = np.asarray(s["times"]) > 0
                    errors = predicted[positive]-target[positive]
                    entry["baseline"].append({"records": prefix, "query": i, "status": "computed", "prediction": predicted,
                        "rmse": float(np.sqrt(np.mean(errors**2))), "mae": float(np.mean(np.abs(errors))),
                        "component_rmse": np.sqrt(np.mean(errors**2, axis=0)), "positive_time_rows": int(positive.sum()),
                        "near_zero_clean_coordinates_included": int(np.count_nonzero(np.abs(target[positive]) <= 1e-12))})
                except Exception as exc:
                    entry["baseline"].append({"records": prefix, "query": i, "status": "failure", "error": str(exc)})
        entry["panels"] = {kind: {"specs": world.panel(57001, kind, count=8)} for kind in ("development", "conditions", "interventions")}
        for value in entry["panels"].values():
            value["costs"] = [world.cost(s) for s in value["specs"]]
        save(ledger.output/f"development-{seed}.json", entry)

    contrast_results = []
    for item in plan["contrasts"]["calls"]:
        p = parameters[item["parameters"]] if isinstance(item["parameters"], str) else Parameters(**item["parameters"])
        contrast_results.append(kernel(item["id"], p, item["spec"]))
    report["contrasts"] = []
    for title, first, second in (("neutral_size", 0, 1), ("matched_initial_bias_x.75", 2, 3), ("changed_initial_x.25", 4, 5)):
        a, b = contrast_results[first], contrast_results[second]
        if a is not None and b is not None:
            difference = np.asarray(a["values"])-np.asarray(b["values"])
            report["contrasts"].append({"name": title, "difference": difference,
                "maximum_absolute_component_difference": float(np.max(np.abs(difference))),
                "component_maxima": np.max(np.abs(difference), axis=0),
                "maximum_difference_over_single_sensor_SD": float(np.max(np.abs(difference))/.002),
                "scope": "Fixed constructed descriptive contrast; no finite-window indistinguishability or unique mechanism claim"})
    check("fixed_solver_count", ledger.solvers == 95, observed=ledger.solvers, expected=95)
    check("fixed_wrapper_count", ledger.wrappers == 65, observed=ledger.wrappers, expected=65)
    check("all_eight_fixed_instances", len(report["development"]) == 8)
    neutral = [d["parameters"] for d in report["development"] if d["stratum"] == "neutral_drift"]
    check("neutral_seeds_same_hidden_dynamics", len(neutral) == 2 and neutral[0] == neutral[1],
          interpretation="noise replicas, not independent neutral mechanisms")
    for kind in ("development", "conditions", "interventions"):
        panels = [d["panels"][kind]["specs"] for d in report["development"]]
        check(f"panels/{kind}/parameter_blind", all(panels[0] == value for value in panels))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if sha(args.plan) != PLAN_SHA256:
        raise ValueError("frozen plan hash mismatch")
    plan = json.loads(args.plan.read_text())
    args.output.mkdir(parents=False, exist_ok=False)
    with (args.plan.parent/"CALIBRATION_STARTED.json").open("x") as stream:
        json.dump({"started_at": datetime.now(timezone.utc).isoformat(), "output": str(args.output.resolve()),
                   "policy": "one scientific batch only; no retry after outcomes"}, stream, indent=2)
    ledger = Ledger(args.output, plan["budget"])
    files = sorted(path for path in Path(__file__).parent.rglob("*") if path.is_file() and "__pycache__" not in path.parts)
    before = {str(path.relative_to(Path(__file__).parent)): sha(path) for path in files}
    save(args.output/"source-hashes-before.json", before)
    report = {"schema": "population_drift_author_diagnostics_v1", "status": "started", "plan_sha256": PLAN_SHA256,
        "checks": [], "development": [], "model_API_calls": 0,
        "counting": "95 planned solver evaluations, including64 children of65 World wrapper attempts; parent-child IDs explicit, wrappers not counted twice as solvers. Invalid-key wrapper has no solver child.",
        "error_convention": "All four coordinates at positive times; assigned t0 excluded. Low-information coordinates retained, no shared score or eligibility policy.",
        "scientific_scope": "Numerical author diagnostics only; ensemble expectations plus sensor noise, not random-path or wet-lab data; independent review pending."}
    save(args.output/"report.json", report)

    def timeout(signum, frame):
        raise BudgetExceeded(f"signal CPU/deadline limit: {signum}")

    signal.signal(signal.SIGALRM, timeout)
    signal.signal(signal.SIGXCPU, timeout)
    previous = resource.getrlimit(resource.RLIMIT_CPU)
    soft = min(30, previous[1]) if previous[1] != resource.RLIM_INFINITY else 30
    resource.setrlimit(resource.RLIMIT_CPU, (soft, previous[1]))
    remaining = min(120-(time.monotonic()-_WALL_START), ledger.deadline-time.time())
    if remaining > 0:
        signal.setitimer(signal.ITIMER_REAL, remaining)
    try:
        ledger.guard()
        execute(plan, ledger, report)
        unexpected = [a for a in ledger.records if a["status"] not in ("success", "expected_failure")]
        bad_checks = [c for c in report["checks"] if c["status"] != "pass"]
        bad_baseline = [b for d in report["development"] for b in d["baseline"] if b["status"] != "computed"]
        report["status"] = "completed_with_failures" if unexpected or bad_checks or bad_baseline else "completed"
    except BaseException as exc:
        report.update(status="partial_budget_exit" if isinstance(exc, BudgetExceeded) else "partial_exception",
                      fatal_error={"type": type(exc).__name__, "message": str(exc), "traceback": traceback.format_exc()})
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        resource.setrlimit(resource.RLIMIT_CPU, previous)
        report["usage"] = {**ledger.usage(), "solver_evaluations": ledger.solvers, "World_wrapper_attempts": ledger.wrappers,
            "ledger_attempt_records": len(ledger.records), "solver_cap": 100, "CPU_limit_seconds": 30, "wall_limit_seconds": 120,
            "role_status_counts": {role: {status: sum(a["role"] == role and a["status"] == status for a in ledger.records)
                for status in sorted(set(a["status"] for a in ledger.records if a["role"] == role))} for role in ("solver", "wrapper")},
            "solver_kind_counts": {kind: sum(a["role"] == "solver" and a["kind"] == kind for a in ledger.records)
                                   for kind in sorted(set(a["kind"] for a in ledger.records if a["role"] == "solver"))}}
        report["attempts"] = ledger.records
        after = {str(path.relative_to(Path(__file__).parent)): sha(path) for path in files}
        report["hash_verification"] = {"source_unchanged": before == after, "plan_unchanged": sha(args.plan) == PLAN_SHA256}
        save(args.output/"source-hashes-after.json", after)
        save(args.output/"report.json", report)
        print(json.dumps({key: report[key] for key in ("status", "usage", "hash_verification")}, indent=2))
    return 0 if report["status"] == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
