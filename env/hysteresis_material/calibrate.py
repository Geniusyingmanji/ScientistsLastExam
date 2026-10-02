"""Trusted, API-free development diagnostics; never expose reports to agents."""

import argparse
import hashlib
import json
import time
from pathlib import Path

import numpy as np

from ..scoring import canonical_hash, prediction_metrics
from .baseline import baseline
from .protocol import integer
from .world import World


DEVELOPMENT_SEEDS = (7, 46, 1439, 8743)


def loop_spec(leg_seconds, amplitude=1.4):
    return {"reset": "negative", "preparation": [{"field": -amplitude, "duration": 120.0}],
            "protocol": [{"time": 0.0, "field": -amplitude},
                         {"time": float(leg_seconds), "field": amplitude},
                         {"time": float(2 * leg_seconds), "field": -amplitude}],
            "times": np.linspace(0.0, 2 * leg_seconds, 129).tolist()}


def memory_spec(reset):
    return {"reset": reset, "preparation": [], "protocol": [{"time": 0.0, "field": 0.0}],
            "times": [0.0, 0.5, 5.0, 15.0, 30.0, 60.0, 120.0, 300.0]}


def loop_area(spec, observation):
    times = np.asarray(observation["axis"])
    fields = np.interp(times, [k["time"] for k in spec["protocol"]], [k["field"] for k in spec["protocol"]])
    response = np.asarray(observation["values"])[:, 0]
    return float(abs(np.sum(0.5 * (response[:-1] + response[1:]) * np.diff(fields))))


def _seed(seed, purpose):
    payload = json.dumps(["hysteresis-development-v1", seed, purpose]).encode()
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big") % (2**63)


def _distribution(values):
    array = np.asarray(values, dtype=float)
    return {"count": len(array), "mean": float(array.mean()), "min": float(array.min()),
            "median": float(np.median(array)), "max": float(array.max())}


def calibrate(seeds=DEVELOPMENT_SEEDS):
    if not isinstance(seeds, (list, tuple)) or not 1 <= len(seeds) <= 16:
        raise ValueError("seeds must contain 1 to 16 distinct integers")
    seeds = [integer(seed, "development seed", 0, 2**63 - 1) for seed in seeds]
    if len(set(seeds)) != len(seeds):
        raise ValueError("development seeds must be distinct")
    started = time.perf_counter()
    instances = []
    for seed in seeds:
        world = World(seed)
        instance = {"development_seed": seed, "private_family": world._family,
                    "noise_std": list(world.noise_std), "scales": list(world.scales),
                    "diagnostics": {}, "training_records": [], "queries": []}
        loops = []
        for leg in (20.0, 120.0, 1200.0):
            spec = loop_spec(leg)
            before = time.perf_counter()
            clean = world.run(spec)
            seconds = time.perf_counter() - before
            noisy = world.run(spec, noise_key="development-loop-%g" % leg)
            loops.append({"leg_seconds": leg, "spec": spec, "clean": clean, "noisy": noisy,
                          "clean_area": loop_area(spec, clean), "noisy_area": loop_area(spec, noisy),
                          "kernel_seconds": seconds})
        memory = {}
        for reset in ("negative", "positive"):
            spec = memory_spec(reset)
            memory[reset] = {"spec": spec, "clean": world.run(spec),
                             "noisy": world.run(spec, noise_key="development-memory-%s" % reset)}
        difference = (np.asarray(memory["positive"]["clean"]["values"]) -
                      np.asarray(memory["negative"]["clean"]["values"]))[:, 0]
        instance["diagnostics"] = {
            "loops": loops, "memory": memory, "memory_difference": difference.tolist(),
            "memory_difference_snr": (np.abs(difference) / (np.sqrt(2.0) * world.noise_std[0])).tolist(),
            "slow_fast_area_ratio": loops[-1]["clean_area"] / loops[0]["clean_area"],
            "quasistatic_loop_area_operator_reference": (1.5 * world._gain * world._a**2 / world._coupling
                                                         if world._family == "bistable" else 0.0),
            "diagnostic_interpretation": "Two finite-rate loops do not uniquely identify a mechanism; compare the long-dwell preparation contrast and the sweep-rate trend."
        }
        train_specs = world.panel(_seed(seed, "train"), "development", 12)
        records = [{"spec": spec, "observation": world.run(spec, noise_key="development-train-%d" % index)}
                   for index, spec in enumerate(train_specs)]
        instance["training_records"] = records
        train_hashes = {canonical_hash(spec) for spec in train_specs}
        for kind in ("conditions", "interventions"):
            for spec in world.panel(_seed(seed, "evaluation-" + kind), kind, 8):
                if canonical_hash(spec) in train_hashes:
                    raise RuntimeError("development evaluation overlaps training")
                clean = world.run(spec)
                query = {"kind": kind, "spec": spec, "clean": clean, "methods": {}}
                values = np.asarray(clean["values"])[1:, 0]
                query["response_rms_to_noise"] = float(np.sqrt(np.mean(values**2)) / world.noise_std[0])
                query["within_run_std_to_noise"] = float(np.std(values) / world.noise_std[0])
                for count in (0, 4, 12):
                    before = time.perf_counter()
                    prediction = baseline(records[:count], spec)
                    seconds = time.perf_counter() - before
                    query["methods"][str(count)] = dict(prediction_metrics(prediction, clean, world.scales),
                                                        prediction=prediction, baseline_seconds=seconds)
                instance["queries"].append(query)
        instances.append(instance)
    queries = [query for instance in instances for query in instance["queries"]]
    summary = {}
    for count in (0, 4, 12):
        metrics = [query["methods"][str(count)] for query in queries]
        summary[str(count)] = {key: _distribution([metric[key] for metric in metrics])
                               for key in ("normalized_rmse", "score", "baseline_seconds")}
    return {"protocol": "hysteresis-development-diagnostics-v1", "world_version": World.version,
            "scope": "Development-only, no API calls, no formal predictions or outcome tuning. Includes private operator annotations.",
            "seeds": seeds, "instances": instances, "baseline_summary": summary,
            "baseline_information": "Nearest public history/trajectory transfer. No hidden equations, class menu, parameters, world seed, or held-out target are supplied to the baseline.",
            "limitations": ["Two constructed mechanism classes are a bounded identification task, not unrestricted mechanism discovery.",
                            "Finite observations cannot prove a strictly zero asymptotic loop area.",
                            "The empirical baseline is a weak comparator; its failure is not evidence of intrinsic scientific difficulty.",
                            "The mean score depends on the chosen mixture of preparation, dwell and sweep protocols.",
                            "The four development seeds are diagnostic evidence, not a formal generalization sample."],
            "elapsed_seconds": time.perf_counter() - started}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    report = calibrate()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "elapsed_seconds": report["elapsed_seconds"],
                      "baseline_summary": report["baseline_summary"]}, indent=2))


if __name__ == "__main__":
    main()
