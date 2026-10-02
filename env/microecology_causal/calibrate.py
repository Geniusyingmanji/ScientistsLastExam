"""Trusted, development-only mechanism diagnostics. No APIs or formal seeds."""

import argparse
import copy
import hashlib
import itertools
import json
import time
from dataclasses import fields
from pathlib import Path

import numpy as np

from ..scoring import canonical_hash, prediction_metrics
from .baseline import baseline
from .kernel import STRUCTURES, X, Y, Z, Parameters
from .world import World


DEVELOPMENT_SEEDS = (7, 46, 1439, 8743)
TIMES = [0.0, 0.25, 3.0, 6.0, 9.0, 12.0, 15.0, 18.0, 24.0, 36.0, 48.0, 72.0]


def culture(a=0.05, b=0.05, c=0.05, times=None, events=None):
    return {"initial": {"A": a, "B": b, "C": c, "nutrient": 5.0}, "temperature_c": 30.0,
            "times_h": list(TIMES if times is None else times), "events": list(events or [])}


def _panel_seed(seed, purpose):
    value = hashlib.sha256(("microecology-causal-development-v1:%d:%s" % (seed, purpose)).encode()).digest()
    return int.from_bytes(value[:8], "big") % (2**63)


def _distribution(values):
    values = np.asarray(values, dtype=float)
    return {"count": len(values), "mean": float(values.mean()), "min": float(values.min()),
            "median": float(np.median(values)), "max": float(values.max())}


def matched_structure_diagnostics(seed=46):
    """Hold nuisance parameters/peak mapping fixed; alter only private edges."""
    base = World(seed)
    early = culture(times=[0.0, 0.05, 0.1, 0.25])
    equivalent = culture(b=0.0, events=[{"time_h": 12, "deplete": {"channel": "peak-01", "fraction": 0.8}},
                                       {"time_h": 24, "temperature_c": 36}, {"time_h": 36, "feed": 2},
                                       {"time_h": 48, "deplete": {"channel": "peak-03", "fraction": 0.7}}])
    arms = []
    for structure in STRUCTURES:
        world = copy.deepcopy(base)
        world._structure = world._kernel.structure = structure
        arms.append({"private_structure": structure, "early": world.run(early),
                     "B_absent": world.run(equivalent), "ABC": world.run(culture())})
    distances = []
    for left in range(3):
        for right in range(left + 1, 3):
            delta = np.asarray(arms[left]["early"]["values"]) - np.asarray(arms[right]["early"]["values"])
            distances.append({"pair": [STRUCTURES[left], STRUCTURES[right]],
                              "early_max_abs_difference_in_paired_noise_sd": float(np.max(np.abs(delta) / (np.sqrt(2) * np.asarray(base.noise_std))))})
    equivalence_error = float(np.max(np.abs(np.asarray(arms[0]["B_absent"]["values"]) - np.asarray(arms[1]["B_absent"]["values"]))))
    return {"development_parameter_seed": seed, "early_spec": early, "B_absent_spec": equivalent,
            "arms": arms, "early_pair_distances": distances,
            "feedback_vs_cut_B_absent_max_abs_difference": equivalence_error,
            "interpretation": "Exact B-absent equivalence concerns only inhibitory_feedback versus feedback_cut with matched nuisance parameters and peak mapping, initially zero fractions, and this apparatus's feeds/depletions/temperature events. It does not assert equivalence to direct_toxin_detox or under B inoculation."}


def boundary_diagnostics():
    """Eight grouped parameter corners per structure, not all 2**11 corners."""
    base = Parameters()
    rows = []
    stress = culture(a=1, b=1, c=1, times=np.linspace(0, 72, 32).tolist(), events=[
        {"time_h": 0, "feed": 3}, {"time_h": 12, "feed": 3}, {"time_h": 36, "feed": 3}, {"time_h": 72, "feed": 3}])
    stress["initial"]["nutrient"] = 10
    stress["temperature_c"] = 40
    for structure in STRUCTURES:
        for uptake_factor, half_inhibition_factor, loss_factor in itertools.product((.88, 1.12), repeat=3):
            world = World(46)
            world._structure = world._kernel.structure = structure
            factors = {field.name: (uptake_factor if field.name.startswith("uptake") else
                                    loss_factor if field.name.startswith("death") or field.name.startswith("decay") else
                                    half_inhibition_factor) for field in fields(base)}
            world._kernel.parameters = Parameters(**{field.name: getattr(base, field.name) * factors[field.name] for field in fields(base)})
            before = time.perf_counter()
            states, added, removed = world._trajectory(world.validate(stress))
            elapsed = time.perf_counter() - before
            abc = np.asarray(world.run(culture())["values"])
            ac = np.asarray(world.run(culture(b=0))["values"])
            rows.append({"private_structure": structure, "parameter_multipliers": factors,
                         "stress_kernel_seconds": elapsed, "minimum_state": float(states.min()),
                         "maximum_state": float(states.max()),
                         "maximum_carbon_residual": float(np.max(np.abs(states.sum(axis=1) + removed - added - 13.0))),
                         "B_addition_delta_C_at_15h": float((abc - ac)[6, 2])})
    return {"scope": "8 grouped corners per structure, using development seed 46 only for the fixed peak mapping; this is not an exhaustive 2**11 corner sweep.",
            "stress_spec": stress, "rows": rows}


def calibrate():
    start, instances = time.perf_counter(), []
    for seed in DEVELOPMENT_SEEDS:
        world = World(seed)
        experiments = {}
        for name, spec in (("ABC", culture()), ("AC", culture(b=0)), ("AB", culture(c=0)), ("A", culture(b=0, c=0))):
            experiments[name] = {"spec": spec, "clean": world.run(spec), "noisy": world.run(spec, noise_key="dev-" + name)}
        for background, c, event_time in (("ABC", 0.05, 12.0), ("AB", 0.0, 9.0)):
            for peak in world.channels[4:]:
                name = background + "-deplete-" + peak
                spec = culture(c=c, events=[{"time_h": event_time, "deplete": {"channel": peak, "fraction": 0.9}}])
                clean = world.run(spec)
                contrast = np.asarray(clean["values"]) - np.asarray(experiments[background]["clean"]["values"])
                experiments[name] = {"spec": spec, "clean": clean, "noisy": world.run(spec, noise_key="dev-" + name),
                                     "difference_from_background": contrast.tolist(),
                                     "biomass_difference_in_paired_noise_sd": (contrast[:, :3] / (np.sqrt(2) * np.asarray(world.noise_std[:3]))).tolist()}
        b_contrast = np.asarray(experiments["ABC"]["clean"]["values"]) - np.asarray(experiments["AC"]["clean"]["values"])
        training = [{"spec": spec, "observation": world.run(spec, noise_key="train-%d" % index)}
                    for index, spec in enumerate(world.panel(_panel_seed(seed, "train"), "development", 12))]
        training_hashes = {canonical_hash(record["spec"]) for record in training}
        queries = []
        kernel_seconds = []
        maximum_residual, minimum_state = 0.0, float("inf")
        for kind in ("conditions", "interventions"):
            for spec in world.panel(_panel_seed(seed, kind), kind, 8):
                assert canonical_hash(spec) not in training_hashes
                before = time.perf_counter()
                truth = world.run(spec)
                kernel_seconds.append(time.perf_counter() - before)
                states, imported, exported = world._trajectory(spec)
                initial_carbon = sum(spec["initial"].values())
                maximum_residual = max(maximum_residual, float(np.max(np.abs(states.sum(axis=1) + exported - imported - initial_carbon))))
                minimum_state = min(minimum_state, float(states.min()))
                methods = {str(count): prediction_metrics(baseline(training[:count], spec), truth, world.scales) for count in (0, 4, 12)}
                queries.append({"kind": kind, "spec": spec, "clean": truth, "methods": methods})
        instances.append({"development_seed": seed, "private_structure": world.operator_stratum(),
                          "private_peak_roles": {world.channels[4 + index]: {X: "X", Y: "Y", Z: "Z"}[internal] for index, internal in enumerate(world._indices[4:])},
                          "experiments": experiments, "B_addition_difference_ABC_minus_AC": b_contrast.tolist(),
                          "training_records": training, "queries": queries, "kernel_seconds": kernel_seconds,
                          "maximum_carbon_residual": maximum_residual, "minimum_state": minimum_state})
    queries = [query for instance in instances for query in instance["queries"]]
    summary = {str(count): {key: _distribution([query["methods"][str(count)][key] for query in queries])
                            for key in ("score", "normalized_rmse")} for count in (0, 4, 12)}
    return {"protocol": "microecology-causal-development-v1", "world_version": World.version,
            "scope": "Experimental development evidence only; no formal seeds, model requests, or required discovery labels.",
            "instances": instances, "matched_structures": matched_structure_diagnostics(), "boundaries": boundary_diagnostics(), "baseline_summary": summary,
            "elapsed_seconds": time.perf_counter() - start,
            "limitations": ["Constructed structural alternatives do not establish unrestricted novelty or contamination resistance.",
                            "The empirical baseline knows no equations and is a weak comparator, not an expert performance ceiling.",
                            "Finite-rate effects can change sign over time; a terminal contrast is not a timeless mechanism statement.",
                            "Absence of an effect within an inoculum/measurement regime cannot establish absence of a causal edge globally."]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = calibrate()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "elapsed_seconds": result["elapsed_seconds"], "baseline_summary": result["baseline_summary"],
                      "early_ambiguity": result["matched_structures"]["early_pair_distances"],
                      "restricted_equivalence_error": result["matched_structures"]["feedback_vs_cut_B_absent_max_abs_difference"]}, indent=2))


if __name__ == "__main__":
    main()
