"""Operator-only, API-free development diagnostics on four reserved seeds."""

import argparse
import hashlib
import json
from pathlib import Path
import time

import numpy as np

from .baseline import baseline
from .kernel import Kernel, Parameters, MAX_EVALUATIONS
from .protocol import NOISE_STD, SCALES, integer, validate_spec
from .reference import energy, polar_reference
from .world import World


DEVELOPMENT_SEEDS = (7, 46, 1439, 8743)


def _hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def _panel_seed(seed, label):
    return int(_hash(["orbital-development-v1", seed, label])[:15], 16)


def _metrics(prediction, truth, spec):
    residual = (np.asarray(prediction) - np.asarray(truth)) / SCALES
    selected = np.asarray(spec["times"]) > 0
    residual = residual[selected]
    normalized = float(np.sqrt(np.mean(residual**2)))
    return {"normalized_rmse": normalized, "score": float(100*np.exp(-normalized/.1)),
            "cells": int(residual.size), "zero_time_excluded": True}


def matched_law_diagnostics():
    """Explicit counterexample to identifying a radial law from one circle."""
    radius, reference_power, mu = 1.2, 2.0, 1.0
    q = radius**2 + .25**2
    speed = radius * np.sqrt(mu / q**((reference_power + 1)/2))
    powers = (1.5, 2., 2.5)
    parameters = [Parameters(mu=float(mu*q**((power-reference_power)/2)), exponent=power) for power in powers]
    circle = validate_spec({"position": [radius, 0], "velocity": [0, float(speed)], "times": np.linspace(0, 10, 41).tolist()})
    radial_excitation = dict(circle, impulses=[{"time": 2., "delta_v": [.23, .05]}])
    other_radius = dict(circle, position=[1.7, 0])
    protocols = {"single_circle": circle, "impulse_probe": radial_excitation, "new_radius": other_radius}
    arms = []
    for p in parameters:
        outputs = {name: Kernel(p).trajectory(spec)[0].tolist() for name, spec in protocols.items()}
        arms.append({"private_parameters": {"mu": p.mu, "exponent": p.exponent}, "outputs": outputs})
    differences = {}
    for name in protocols:
        reference = np.asarray(arms[1]["outputs"][name])
        differences[name] = [{"exponent": powers[i], "max_abs_normalized_difference": float(np.max(np.abs(np.asarray(arm["outputs"][name]) - reference)/SCALES))}
                             for i, arm in enumerate(arms) if i != 1]
    drag = Parameters(mu=1, drag=.07)
    short = dict(circle, times=[0., .01, .03])
    conservative = Kernel(parameters[1]).trajectory(short)[0]
    damped = Kernel(drag).trajectory(short)[0]
    long_damped = Kernel(drag).trajectory(circle)[0]
    long_reference = np.asarray(arms[1]["outputs"]["single_circle"])
    return {"purpose": "Matched circular acceleration, private development-only construction; not a candidate menu or scoring key.",
            "specs": protocols, "arms": arms, "differences": differences,
            "drag_short_arc_max_difference_in_paired_noise_sd": float(np.max(np.abs(damped-conservative)/(np.sqrt(2)*np.asarray(NOISE_STD)))),
            "drag_long_arc_max_difference_in_paired_noise_sd": float(np.max(np.abs(long_damped-long_reference)/(np.sqrt(2)*np.asarray(NOISE_STD)))),
            "interpretation": "The three conservative laws share the same circular orbit. Radius changes or radial excitation distinguish these particular laws. Short noisy arcs can hide weak drag; these contrasts do not prove unique identification among arbitrary alternatives."}


def _distribution(values):
    values = np.asarray(values, dtype=float)
    return {"count": len(values), "mean": float(values.mean()), "median": float(np.median(values)),
            "min": float(values.min()), "max": float(values.max())}


def calibrate(seeds=DEVELOPMENT_SEEDS):
    if not isinstance(seeds, (list, tuple)) or not 1 <= len(seeds) <= 16:
        raise ValueError("seeds must contain 1..16 unique development integers")
    seeds = [integer(seed, "development seed") for seed in seeds]
    if len(set(seeds)) != len(seeds):
        raise ValueError("development seeds must be unique")
    started, instances = time.perf_counter(), []
    for seed in seeds:
        world = World(seed)
        training = world.panel(_panel_seed(seed, "training"), "development", 12)
        records, seconds, rhs, cost = [], [], [], 0
        for index, spec in enumerate(training):
            before = time.perf_counter()
            observation = world.run(spec, noise_key="development-training-%d" % index)
            seconds.append(time.perf_counter() - before)
            cost += world.cost(spec)
            records.append({"spec": spec, "observation": observation})
        training_hashes = {_hash(s) for s in training}
        queries = []
        for kind in ("conditions", "interventions"):
            for spec in world.panel(_panel_seed(seed, kind), kind, 6):
                if _hash(spec) in training_hashes:
                    raise RuntimeError("development training and query overlap")
                before = time.perf_counter()
                truth, work = world._kernel.trajectory(spec)
                seconds.append(time.perf_counter() - before)
                rhs.append(work["rhs_evaluations"])
                methods = {}
                for count in (0, 4, 12):
                    began = time.perf_counter()
                    prediction = baseline(records[:count], spec)
                    methods[str(count)] = dict(_metrics(prediction, truth, spec), baseline_seconds=time.perf_counter()-began)
                queries.append({"kind": kind, "spec": spec, "private_truth": truth.tolist(), "numerical_work": work, "methods": methods})
        reference_spec = validate_spec({"position": [1.4, 0], "velocity": [.03, .83],
                                        "times": [0, .1, .5, 1, 2, 3, 4], "impulses": []})
        cartesian, reference_work = world._kernel.trajectory(reference_spec)
        polar, drag_work, reference_nfev = polar_reference(reference_spec, world._kernel.parameters)
        error = cartesian - polar
        momentum = cartesian[:, 0]*cartesian[:, 3] - cartesian[:, 1]*cartesian[:, 2]
        p = world._kernel.parameters
        invariant_error = momentum - momentum[0]*np.exp(-p.drag*np.asarray(reference_spec["times"]))
        energies = energy(cartesian, p)
        instances.append({"development_seed": seed, "private_stratum": world.operator_stratum(),
                          "training_records": records, "queries": queries,
                          "training_experiments": len(records), "training_public_cost": cost,
                          "diagnostic_query_experiments": len(queries), "reference_experiments": 1,
                          "kernel_seconds": _distribution(seconds), "query_rhs_evaluations": _distribution(rhs),
                          "reference": {"spec": reference_spec, "independent_method": "polar_Radau_with_drag_work_coordinate",
                                        "max_abs_error": float(np.max(np.abs(error))),
                                        "max_error_in_noise_sd": float(np.max(np.abs(error)/NOISE_STD)),
                                        "angular_momentum_decay_max_abs_error": float(np.max(np.abs(invariant_error))),
                                        "energy_work_balance_max_abs_error": float(np.max(np.abs(energies - energies[0] - drag_work))),
                                        "production_work": reference_work, "independent_rhs_evaluations": reference_nfev}})
    queries = [query for instance in instances for query in instance["queries"]]
    summary = {str(count): {name: _distribution([query["methods"][str(count)][name] for query in queries])
                            for name in ("normalized_rmse", "score", "baseline_seconds")} for count in (0, 4, 12)}
    return {"protocol": "orbital-development-diagnostics-v1", "world_version": World.version,
            "scope": "Private, development-only, zero API. Not formal outcomes, target selection or intrinsic difficulty certification.",
            "reserved_development_seeds": seeds, "instances": instances,
            "development_stratum_counts": {label: sum(row["private_stratum"] == label for row in instances) for label in World.operator_strata},
            "baseline_summary": summary, "matched_law_diagnostics": matched_law_diagnostics(),
            "baseline_information": "Rotation-aligned nearest public trajectory residual transfer; empty history uses inertial drift plus specified impulses. No force family, private parameters, seed or clean query outcome is supplied to baseline.",
            "metric": "Development diagnostic only: remove t=0 cells, fixed public scales, NRMSE, 100*exp(-NRMSE/0.1). No claims component or official score is produced.",
            "maximum_rhs_evaluations_per_production_experiment": MAX_EVALUATIONS,
            "limitations": ["Four seeds are development checks, not a representative generalization sample.",
                            "Poor nearest-trajectory scores establish neither scientific difficulty nor superiority of a learned law.",
                            "Matched-law contrasts concern these constructions; flexible alternative laws may remain observationally equivalent.",
                            "Impulse jumps and time-zero coordinates are publicly assigned; reproducing them alone is not scientific evidence.",
                            "No celestial accuracy, contamination resistance, depth or automatic mechanism identity is certified."],
            "elapsed_seconds": time.perf_counter() - started}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    report = calibrate()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"world_version": World.version, "output": str(args.output),
                      "elapsed_seconds": report["elapsed_seconds"], "baseline_summary": report["baseline_summary"]}, indent=2))


if __name__ == "__main__":
    main()
