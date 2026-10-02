"""Operator-only null-effect calibration of the unchanged claim verifier.

No model API, threshold tuning or formal-cohort access. Each independent
replication uses eight exploratory pairs, freezes two reference intervals, then
calls the existing verify_claims separately with independent confirmation keys.
Null controls are fixed by public operations, never selected from hidden edges.
"""

import argparse
from copy import deepcopy
import hashlib
import json
import math
import multiprocessing
import os
from pathlib import Path
import resource
import sys
import time

import numpy as np
import scipy
from scipy.stats import norm, t

from .claim_semantics import claim_eligibility
from .registry import load_world
from .scoring import CONFIRMATION_REPLICATES, PROTOCOL as VERIFIER_PROTOCOL, canonical_hash, validate_submission, verify_claims


PROTOCOL = "sle-null-claim-calibration-0.1"
DEVELOPMENT_SEEDS = (7, 46, 1439, 8743)
NULL_ENVIRONMENTS = (
    "microecology", "coupled_oscillators", "reaction_kinetics", "heat_transport",
    "gene_regulation", "ising_spin", "hysteresis_material",
)
STRATEGIES = ("fixed_zero_normal", "exploration_student_prediction")
EXPLORATION_PAIRS = 8
CLEAN_TOLERANCE_SIGMA = 1e-4


def null_cases(environment):
    """Return predetermined public-operation nulls, with eligible readouts."""
    if environment not in NULL_ENVIRONMENTS:
        raise ValueError("no audited null contrast for the requested environment")
    if environment == "microecology":
        cases = []
        for case, inoculum, channel in (("clipped_boundary", 0.0, "A"), ("positive_signal", 0.08, "A")):
            control = {"initial": {"A": inoculum, "B": 0.06, "C": 0.08, "nutrient": 3.0}, "temperature_c": 30, "times_h": [0, 1, 2], "events": []}
            treatment = dict(control, events=[{"time_h": 1, "feed": 0}])
            cases.append({"id": case, "control": control, "treatment": treatment,
                          "readout": {"row": 2, "channel": channel},
                          "rationale": "A zero-amount nutrient feed changes no material; both arms use the same observation breakpoints. Readout is 1 h after the event. " + ("A has zero inoculum and remains absent, exposing the clipped-sensor boundary." if inoculum == 0 else "Positive A biomass supplies an interior-signal comparison to the clipped boundary.")})
        return deepcopy(cases)
    if environment == "coupled_oscillators":
        control = {"times": [1.0], "initial_position": [0, 0, 0.6, -0.2], "clamp": ["A", "B"]}
        treatment = dict(control, cut_edges=[["A", "B"]])
        readout, rationale = {"row": 0, "channel": "x_C"}, "A and B are both held at zero; their mutual connector carries no relative displacement. Removing it leaves free C's dynamics unchanged regardless of whether the hidden connector exists. C is not clamped; readout is after the 0.25 s eligibility lag."
    elif environment == "reaction_kinetics":
        control = {"temperature_k": 325, "initial_mM": [0.8, 0.2, 0.1, 0.1], "times_s": [0, 1, 2], "interventions": []}
        treatment = dict(control, interventions=[{"time_s": 1, "kind": "temperature", "temperature_k": 325}])
        readout, rationale = {"row": 2, "channel": "C"}, "Reasserting the existing temperature does not change the physical temperature history. Shared observation breakpoints prevent segmentation from confounding the comparison; readout is 1 s after the redundant event."
    elif environment == "heat_transport":
        control = {"times": [1.0], "probes": [0.2, 0.5, 0.8], "initial_temperature": 25, "boundary_temperatures": [20, 30], "ambient_temperature": 10, "flow": 0, "cooling": 0, "heaters": [{"position": 0.3, "power": 4, "width": 0.08}]}
        treatment = dict(control, ambient_temperature=35)
        readout, rationale = {"row": 0, "channel": "probe_2_temperature"}, "With cooling disabled and zero flow, changing ambient temperature cannot change the interior temperature history. Heating and unequal boundary temperatures retain a nontrivial signal; the readout is after 0.5 s."
    elif environment == "gene_regulation":
        control = {"initial_expression": [0.3, 0.4, 0.35, 0.45], "initial_drive": [0.4, 0, 0, 0], "times_h": [0, 0.5, 1], "interventions": []}
        treatment = dict(control, interventions=[{"time_h": 0.5, "kind": "set_drive", "drive": [0.4, 0, 0, 0]}])
        readout, rationale = {"row": 2, "channel": "G3"}, "Reassert the unchanged drive vector at an existing observation breakpoint. The drive history is identical; the readout is 0.5 h later, satisfying the event-lag boundary."
    elif environment == "ising_spin":
        control = {"temperatures": [1.1], "clamp": {"A": 1, "B": -1}}
        treatment = dict(control, suppress_bonds=[{"nodes": ["A", "B"], "fraction": 1}])
        readout, rationale = {"row": 0, "channel": "m_C"}, "A and B are fixed, so their mutual bond contributes only a constant energy. Removing that possible bond changes no free-site distribution, whether or not the hidden bond exists. C is not clamped."
    else:
        control = {"reset": "negative", "preparation": [], "protocol": [{"time": 0, "field": 0.2}], "times": [2.0]}
        treatment = dict(control, protocol=[{"time": 0, "field": 0.2}, {"time": 1, "field": 0.2}])
        readout, rationale = {"row": 0, "channel": "response"}, "Insert a redundant constant-field knot: both histories remain at field 0.2 over 0..2 s after the same reset. This applies to either hidden material response class; the readout is after the 0.5 s preparation lag."
    return deepcopy([{"id": "public_null", "control": control, "treatment": treatment, "readout": readout, "rationale": rationale}])


def wilson_interval(successes, total, confidence=0.95):
    """Two-sided Wilson interval; undefined denominators remain null."""
    if type(total) is not int or type(successes) is not int or not 0 <= successes <= total:
        raise ValueError("counts must satisfy 0 <= successes <= total")
    if isinstance(confidence, bool) or not isinstance(confidence, (int, float)) or not 0 < confidence < 1:
        raise ValueError("confidence must lie in (0,1)")
    if total == 0:
        return None
    z = float(norm.ppf((1 + confidence) / 2))
    p, denominator = successes / total, 1 + z * z / total
    center = (p + z * z / (2 * total)) / denominator
    radius = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denominator
    return [max(0.0, center - radius), min(1.0, center + radius)]


def reference_intervals(differences, declared_sigma):
    """Two prespecified reference strategies; no confirmation data or clean truth."""
    values = np.asarray(differences, dtype=float)
    if values.shape != (EXPLORATION_PAIRS,) or not np.isfinite(values).all():
        raise ValueError("exactly eight finite exploratory paired differences are required")
    if isinstance(declared_sigma, bool) or not isinstance(declared_sigma, (int, float)) or not math.isfinite(declared_sigma) or declared_sigma <= 0:
        raise ValueError("declared_sigma must be positive and finite")
    fixed_radius = float(norm.ppf(0.95)) * declared_sigma * math.sqrt(2 / CONFIRMATION_REPLICATES)
    center = float(np.mean(values))
    sample_sd = float(np.std(values, ddof=1))
    predicted_radius = float(t.ppf(0.95, EXPLORATION_PAIRS - 1)) * sample_sd * math.sqrt(1 / EXPLORATION_PAIRS + 1 / CONFIRMATION_REPLICATES)
    return {
        "fixed_zero_normal": [-fixed_radius, fixed_radius],
        "exploration_student_prediction": [center - predicted_radius, center + predicted_radius],
    }


class CalibrationBudgetExceeded(RuntimeError):
    pass


class _TrackedWorld:
    def __init__(self, world, seed, emit, deadline, cpu_deadline):
        self.world, self.emit = world, emit
        self.world_seed = seed
        self.deadline, self.cpu_deadline = deadline, cpu_deadline
        self.phase, self.query = "clean_preflight", 0

    def __getattr__(self, name):
        return getattr(self.world, name)

    def run(self, spec, *, noise_key=None):
        if time.monotonic() >= self.deadline or time.process_time() >= self.cpu_deadline:
            raise CalibrationBudgetExceeded("worker wall or CPU allowance exhausted")
        self.query += 1
        event = {"kind": "query", "state": "started", "query": self.query,
                 "world_seed": self.world_seed, "phase": self.phase, "noise_key": noise_key,
                 "spec_sha256": canonical_hash(spec)}
        self.emit(event)
        try:
            result = self.world.run(spec, noise_key=noise_key)
        except Exception as error:
            self.emit(dict(event, state="failed", error_type=type(error).__name__, error=str(error)[:600]))
            raise
        self.emit(dict(event, state="completed"))
        return result


def _check_null(world, case, seed):
    control, treatment = (world.validate(case[arm]) for arm in ("control", "treatment"))
    if canonical_hash(control) == canonical_hash(treatment):
        raise ValueError("null contrast collapsed to identical canonical specs")
    eligibility = claim_eligibility(world.name, control, treatment, case["readout"], world.axis_field)
    if not eligibility["eligible"]:
        raise ValueError("null contrast is ineligible: " + eligibility["reason"])
    row, channel = case["readout"]["row"], world.channels.index(case["readout"]["channel"])
    clean = [world.run(spec)["values"][row][channel] for spec in (control, treatment)]
    difference = float(clean[1] - clean[0])
    tolerance = CLEAN_TOLERANCE_SIGMA * world.noise_std[channel]
    result = {"world_seed": seed, "case": case["id"], "control": control, "treatment": treatment,
              "readout": case["readout"], "rationale": case["rationale"], "eligibility": eligibility,
              "clean_arm_values": clean, "clean_difference": difference,
              "declared_sigma": world.noise_std[channel], "tolerance": tolerance,
              "null_confirmed": abs(difference) <= tolerance}
    return result


def _key(environment, seed, case, repetition, purpose):
    return "%s:%s:%d:%s:%d:%s" % (PROTOCOL, environment, seed, case, repetition, purpose)


def _replication(world, case, seed, repetition, emit):
    records, differences, failures = [], [], 0
    row, column = case["readout"]["row"], world.channels.index(case["readout"]["channel"])
    world.phase = "exploration"
    for replica in range(EXPLORATION_PAIRS):
        pair = []
        for arm in ("control", "treatment"):
            key = _key(world.name, seed, case["id"], repetition, "explore:%s:%d" % (arm, replica))
            observation = world.run(case[arm], noise_key=key)
            records.append({"id": "cal-%s-%d" % (arm, replica), "spec": case[arm], "observation": observation})
            pair.append(observation["values"][row][column])
        differences.append(float(pair[1] - pair[0]))
    intervals = reference_intervals(differences, float(world.noise_std[column]))
    # Freeze BOTH intervals before either confirmation dataset is obtained.
    frozen = {}
    for strategy in STRATEGIES:
        claim = {"id": "null-reference", "statement": "Prespecified null control: treatment-minus-control at the stated readout.",
                 "control": case["control"], "treatment": case["treatment"], "readout": case["readout"],
                 "interval": intervals[strategy], "evidence_ids": [r["id"] for r in records],
                 "scope": case["rationale"] + " Operator calibration of an expected null, not a discovery submission."}
        # Existing submission validation checks timing, distinct arms, evidence
        # IDs and schema. The zero predictor is valid-shaped but never scored.
        code = "def predict(spec):\n    return [[0.0] * %d for _ in spec[%r]]\n" % (len(world.channels), world.axis_field)
        frozen[strategy] = validate_submission({"predictor_code": code, "claims": [claim], "explanation": "Operator-only null reference interval calibration."}, world, records)["claims"][0]
    emit({"kind": "frozen", "repetition": repetition, "world_seed": seed, "case": case["id"],
          "intervals": intervals, "claims_sha256": canonical_hash(frozen)})
    for strategy in STRATEGIES:
        world.phase = "verification:" + strategy
        confirmation_key = _key(world.name, seed, case["id"], repetition, "confirm:" + strategy)
        started_wall, started_cpu = time.monotonic(), time.process_time()
        emit({"kind": "batch_started", "strategy": strategy, "world_seed": seed,
              "case": case["id"], "repetition": repetition, "confirmation_key": confirmation_key})
        try:
            report = verify_claims(world, [deepcopy(frozen[strategy])], confirmation_key)
            result = report["claims"][0]
            if result["duplicate"] or not result["eligibility"]["eligible"]:
                raise ValueError("verifier rejected the single prespecified eligible null slot")
            result.update(three_se_exceeded=abs(result["mean_difference"]) > max(3 * result["standard_error"], 1e-12))
            emit({"kind": "batch", "status": "complete", "strategy": strategy,
                  "world_seed": seed, "case": case["id"], "repetition": repetition,
                  "confirmation_key": confirmation_key, "frozen_claim_sha256": canonical_hash(frozen[strategy]),
                  "exploration_differences": differences, "interval": intervals[strategy],
                  "verification": result, "wall_seconds": time.monotonic() - started_wall,
                  "cpu_seconds": time.process_time() - started_cpu})
        except Exception as error:
            failures += 1
            emit({"kind": "batch", "status": "failed", "strategy": strategy,
                  "world_seed": seed, "case": case["id"], "repetition": repetition,
                  "error_type": type(error).__name__, "error": str(error)[:600]})
            if isinstance(error, CalibrationBudgetExceeded):
                raise
    return failures


def _worker(environment, repetitions, seconds, cpu_seconds, connection):
    start, cpu_start = time.monotonic(), time.process_time()
    status = "complete"
    emit = connection.send
    try:
        # Hard OS limit supplements cooperative checks; the supervisor also
        # terminates an in-flight process at the overall wall deadline.
        hard_cpu = int(math.ceil(cpu_start + cpu_seconds))
        resource.setrlimit(resource.RLIMIT_CPU, (hard_cpu, hard_cpu + 1))
        cases, worlds, preflight = null_cases(environment), {}, []
        for seed in DEVELOPMENT_SEEDS:
            raw, _ = load_world(environment, seed)
            tracked = _TrackedWorld(raw, seed, emit, start + seconds, cpu_start + cpu_seconds)
            worlds[seed] = tracked
            for case in cases:
                checked = _check_null(tracked, case, seed)
                preflight.append(checked)
                emit({"kind": "preflight", "result": checked})
                if not checked["null_confirmed"]:
                    raise ValueError("prespecified public null failed the clean tolerance check")
        # No confirmation begins until every case passes all four reserved seeds.
        emit({"kind": "preflight_complete", "count": len(preflight)})
        for repetition in range(repetitions):
            seed = DEVELOPMENT_SEEDS[repetition % len(DEVELOPMENT_SEEDS)]
            case_index = (repetition // len(DEVELOPMENT_SEEDS)) % len(cases)
            case = deepcopy(cases[case_index])
            world = worlds[seed]
            case.update({arm: world.validate(case[arm]) for arm in ("control", "treatment")})
            if _replication(world, case, seed, repetition, emit):
                status = "completed_with_failures"
    except Exception as error:
        status = "budget_exhausted" if isinstance(error, CalibrationBudgetExceeded) else "failed"
        emit({"kind": "failure", "error_type": type(error).__name__, "error": str(error)[:600]})
    finally:
        emit({"kind": "done", "status": status, "elapsed_seconds": time.monotonic() - start,
              "cpu_seconds": time.process_time() - cpu_start})
        connection.close()


def _rate(successes, total):
    return {"events": successes, "denominator": total,
            "rate": successes / total if total else None,
            "wilson_95": wilson_interval(successes, total)}


def _summarize(batches, planned, attempts=None):
    complete = [row for row in batches if row["status"] == "complete"]
    result = {"planned": planned, "attempted": len(batches) if attempts is None else len(attempts),
              "completed": len(complete),
              "failed": sum(row["status"] == "failed" for row in batches),
              "not_completed": planned - len(complete)}
    for key, field in (("empirical_coverage", "covered"), ("verified_nonzero_false_positive", "verified_nonzero_effect"), ("three_se_exceedance", "three_se_exceeded")):
        result[key] = _rate(sum(row["verification"][field] for row in complete), len(complete))
    result["mean_interval_width"] = float(np.mean([row["interval"][1] - row["interval"][0] for row in complete])) if complete else None
    false_positive = result["verified_nonzero_false_positive"]
    result["conditional_three_slot_union_bound"] = {
        "episode_rate_measured": False,
        "plug_in_upper_bound": min(1.0, 3 * false_positive["rate"]) if complete else None,
        "wilson_upper_endpoint_times_three": min(1.0, 3 * false_positive["wilson_95"][1]) if complete else None,
        "scope": "Union bound requires each of three eligible, nonduplicated slots to have marginal false-positive rate bounded by the calibrated slot rate. The plug-in value is an estimate, not a proved bound. The Wilson transformation inherits its sampling approximation. Neither is an empirical episode rate or a bound for adaptive claim selection.",
    }
    return result


def _source_hash():
    root = Path(__file__).resolve().parent
    digest = hashlib.sha256()
    # Include the exact kernels, public schema and verifier, excluding unrelated
    # live runner/reporting edits that cannot change this calibration.
    paths = [root / name for name in ("claim_calibration.py", "scoring.py", "claim_semantics.py", "registry.py")]
    for name in NULL_ENVIRONMENTS:
        paths.extend((root / name).rglob("*.py"))
    for path in sorted(paths):
        if "tests" not in path.parts and "examples" not in path.parts:
            digest.update(str(path.relative_to(root)).encode() + b"\0" + path.read_bytes() + b"\0")
    return digest.hexdigest()


def calibrate(names, *, repetitions=200, max_seconds=300, cpu_seconds_per_world=120, workers=2, progress=None):
    """Run 1..300 paired replications/world in 1..4 supervised processes.

    Every query emits start/completion before the worker proceeds. The parent
    counts attempts, incomplete in-flight calls, verifier batches and failures.
    Four fixed development seeds are always clean-checked before replication.
    """
    if not isinstance(names, (list, tuple)) or not names or any(not isinstance(name, str) or name not in NULL_ENVIRONMENTS for name in names) or len(set(names)) != len(names):
        raise ValueError("select distinct audited environments explicitly")
    for value, label, upper in ((repetitions, "repetitions", 300), (workers, "workers", 4)):
        if type(value) is not int or not 1 <= value <= upper:
            raise ValueError(label + " is outside its allowed integer range")
    for value, label in ((max_seconds, "max_seconds"), (cpu_seconds_per_world, "cpu_seconds_per_world")):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 < value <= 3600:
            raise ValueError(label + " must be finite in (0,3600]")
    if CONFIRMATION_REPLICATES != 8:
        raise ValueError("this calibration protocol requires the audited eight-replica verifier")
    start, source_before = time.monotonic(), _source_hash()
    child_usage_before = resource.getrusage(resource.RUSAGE_CHILDREN)
    context = multiprocessing.get_context("spawn")
    rows = {name: {"environment": name, "status": "not_started", "preflight": [], "batches": [],
                   "batch_attempts": [], "frozen_intervals": [], "failures": [], "query_counts": {}, "pending_queries": {}}
            for name in names}
    active, waiting = {}, list(names)

    def consume(name, event):
        row = rows[name]
        kind = event["kind"]
        if kind == "query":
            phase = event["phase"]
            count = row["query_counts"].setdefault(phase, {"attempted": 0, "completed": 0, "failed": 0})
            if event["state"] == "started":
                count["attempted"] += 1
                # Per-instance counters restart; noise keys identify noisy calls.
                row["pending_queries"][phase] = event
            else:
                count[event["state"]] += 1
                row["pending_queries"].pop(phase, None)
                if event["state"] == "failed":
                    row["failures"].append(event)
        elif kind == "preflight":
            row["preflight"].append(event["result"])
        elif kind == "batch":
            row["batches"].append(event)
            if event["status"] != "complete":
                row["failures"].append(event)
        elif kind == "batch_started":
            row["batch_attempts"].append(event)
        elif kind == "frozen":
            row["frozen_intervals"].append(event)
        elif kind == "failure":
            row["failures"].append(event)
        elif kind == "done":
            row.update({key: event[key] for key in ("status", "elapsed_seconds", "cpu_seconds")})
        elif kind == "preflight_complete":
            row["preflight_complete"] = True

    def drain(name, connection, limit=None):
        count = 0
        while (limit is None or count < limit) and connection.poll():
            try:
                consume(name, connection.recv())
            except (EOFError, OSError):
                break
            count += 1

    try:
        while waiting or active:
            elapsed = time.monotonic() - start
            if elapsed >= max_seconds:
                break
            while waiting and len(active) < workers:
                name = waiting.pop(0)
                parent, child = context.Pipe(duplex=False)
                process = context.Process(target=_worker, args=(name, repetitions, max_seconds - elapsed, cpu_seconds_per_world, child))
                process.start()
                child.close()
                rows[name]["status"] = "running"
                active[name] = (process, parent)
            for name, (process, connection) in list(active.items()):
                # Bound each drain so one fast worker cannot starve the deadline.
                drain(name, connection, limit=256)
                if not process.is_alive():
                    process.join(timeout=0.1)
                    # A completed producer can leave more than one drain's
                    # worth of buffered events, including its final status.
                    drain(name, connection)
                    if rows[name]["status"] == "running":
                        rows[name]["status"] = "worker_failed"
                        rows[name]["failures"].append({"kind": "worker_exit", "exitcode": process.exitcode})
                    connection.close()
                    del active[name]
                    if progress is not None:
                        progress({"environment": name, "status": rows[name]["status"], "completed_batches": sum(batch["status"] == "complete" for batch in rows[name]["batches"])})
            if active:
                time.sleep(0.002)
    finally:
        for name, (process, connection) in active.items():
            # Stop the producer before an unbounded final drain. This prevents
            # a fast producer from keeping the supervisor past its deadline.
            if process.is_alive():
                process.terminate()
            process.join(timeout=1)
            if process.is_alive():
                process.kill()
                process.join(timeout=1)
            drain(name, connection)
            connection.close()
            if rows[name]["status"] == "running":
                rows[name]["status"] = "wall_budget_exhausted"
                rows[name]["failures"].append({"kind": "wall_budget_exhausted", "max_seconds": max_seconds})
    for name, row in rows.items():
        if row["status"] == "not_started":
            row["failures"].append({"kind": "not_started_before_wall_deadline"})
        for query in row["pending_queries"].values():
            row["failures"].append(dict(query, state="incomplete_at_worker_exit"))
        cases = null_cases(name)
        row["planned_query_counts"] = {"clean_preflight": 2 * len(DEVELOPMENT_SEEDS) * len(cases), "exploration": 2 * EXPLORATION_PAIRS * repetitions}
        row["planned_query_counts"].update({"verification:" + strategy: 2 * CONFIRMATION_REPLICATES * repetitions for strategy in STRATEGIES})
        row["total_query_counts"] = {field: sum(count[field] for count in row["query_counts"].values()) for field in ("attempted", "completed", "failed")}
        row["total_query_counts"]["incomplete"] = len(row["pending_queries"])
        row["summary"] = {strategy: _summarize([b for b in row["batches"] if b["strategy"] == strategy], repetitions, [b for b in row["batch_attempts"] if b["strategy"] == strategy]) for strategy in STRATEGIES}
        row["by_case"] = {}
        for case_index, case in enumerate(cases):
            planned = sum((i // len(DEVELOPMENT_SEEDS)) % len(cases) == case_index for i in range(repetitions))
            row["by_case"][case["id"]] = {strategy: _summarize([b for b in row["batches"] if b["strategy"] == strategy and b["case"] == case["id"]], planned, [b for b in row["batch_attempts"] if b["strategy"] == strategy and b["case"] == case["id"]]) for strategy in STRATEGIES}
        row["by_seed"] = {str(seed): {strategy: _summarize([b for b in row["batches"] if b["strategy"] == strategy and b["world_seed"] == seed], sum(DEVELOPMENT_SEEDS[i % len(DEVELOPMENT_SEEDS)] == seed for i in range(repetitions)), [b for b in row["batch_attempts"] if b["strategy"] == strategy and b["world_seed"] == seed]) for strategy in STRATEGIES} for seed in DEVELOPMENT_SEEDS}
    source_after = _source_hash()
    child_usage_after = resource.getrusage(resource.RUSAGE_CHILDREN)
    return {
        "protocol": PROTOCOL, "verifier_protocol": VERIFIER_PROTOCOL, "operator_only": True,
        "runtime": {"python": sys.version, "numpy": np.__version__, "scipy": scipy.__version__},
        "status": "complete" if all(row["status"] == "complete" for row in rows.values()) else "partial_or_failed",
        "selected_environments": list(names), "development_seeds": list(DEVELOPMENT_SEEDS),
        "paired_replications_per_world": repetitions, "verification_batches_per_world": 2 * repetitions,
        "exploration_pairs_per_replication": 8, "confirmation_pairs_per_strategy": 8,
        "max_seconds": max_seconds, "cpu_seconds_per_world": cpu_seconds_per_world,
        "nominal_total_worker_cpu_allowance": cpu_seconds_per_world * len(names), "workers": workers,
        "cpu_limit_rounding": "Cooperative process_time limits are supplemented by a whole-second OS soft limit and hard kill one second later. Startup and at most two seconds of rounding/grace per worker are outside the nominal allowance.",
        "completed_worker_cpu_seconds": sum(row.get("cpu_seconds", 0) for row in rows.values()),
        "child_cpu_seconds_including_startup_and_failed_workers": child_usage_after.ru_utime + child_usage_after.ru_stime - child_usage_before.ru_utime - child_usage_before.ru_stime,
        "elapsed_seconds": time.monotonic() - start,
        "source_sha256_before": source_before, "source_sha256_after": source_after,
        "source_stable": source_before == source_after, "worlds": list(rows.values()),
        "reference_formulas": {
            "fixed_zero_normal": "0 +/- z_0.95 * declared_raw_sigma * sqrt(2/8). Center is fixed at the prespecified null and ignores exploration values.",
            "exploration_student_prediction": "mean(D_explore) +/- t_0.95,7 * sd(D_explore,ddof=1) * sqrt(1/8 + 1/8), using eight independent exploratory paired differences and a future mean of eight pairs.",
            "gaussian_three_se_reference_only": float(2 * t.sf(3, 7)),
            "gaussian_three_slot_gate_union_bound_reference_only": min(1.0, 3 * float(2 * t.sf(3, 7))),
        },
        "interpretation": [
            "All intervals are frozen before either strategy's confirmation. Confirmation keys are independent of exploration and of the other strategy. Two strategies share exploration data only.",
            "One claim is passed per verifier call; there are no duplicated slots. Only the claim-level flags and intervals are calibrated, not the three-slot aggregate score.",
            "The conditional three-slot union bounds are explicitly derived from slot rates, not measured episode rates. They need the same null marginal distribution for each slot; they make no claim about adaptive agent-selected episodes.",
            "Empirical coverage concerns the realized fresh mean, not coverage of the clean mean. A verified_nonzero flag on a confirmed structural null is a false positive.",
            "The fixed interval is a normal-reference policy using declared pre-clipping sensor sigma. The Student interval is an exact Gaussian paired-mean reference only under its assumptions; it is not asserted exact for clipped sensors.",
            "Microecology clips each arm at zero, changing its mean and variance. Equal-arm clipping bias cancels in the paired null mean, but the eight-pair difference distribution need not be Gaussian. Boundary and positive-signal cases are reported separately.",
            "The verifier's 3*sample-SE gate is not a universal p-value. The reported Gaussian t7 tail is a diagnostic reference for that gate alone, before coverage/width/eligibility conditions.",
            "Wilson intervals describe observed rates over independent noise replications on these four fixed development seeds. They do not quantify generalization to all worlds, scientific claims or adaptive claim selection.",
            "Scientific relevance of these deliberately redundant controls is not a discovery claim. No verifier thresholds, scales, formal results or null definitions are tuned using the outcomes.",
            "Query attempts include starts without completion; those are explicitly reported as incomplete at worker exit. Process CPU limits and the supervising wall deadline bound work, with shutdown overhead recorded in elapsed time.",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--environments", required=True)
    parser.add_argument("--repetitions", type=int, default=200)
    parser.add_argument("--max-seconds", type=float, default=300)
    parser.add_argument("--cpu-seconds-per-world", type=float, default=120)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--output", required=True, help="New private operator JSON path; never overwritten")
    args = parser.parse_args()
    path = Path(args.output).expanduser().resolve()
    if path.exists():
        raise ValueError("calibration output already exists")
    result = calibrate(args.environments.split(","), repetitions=args.repetitions,
                       max_seconds=args.max_seconds, cpu_seconds_per_world=args.cpu_seconds_per_world,
                       workers=args.workers, progress=lambda row: print(json.dumps(row), flush=True))
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write("\n")
    print(json.dumps({"status": result["status"], "elapsed_seconds": result["elapsed_seconds"], "source_stable": result["source_stable"], "output": str(path)}), flush=True)


if __name__ == "__main__":
    main()
