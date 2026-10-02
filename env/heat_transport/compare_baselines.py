"""Trusted offline comparison against an existing development calibration.

This harness alone reconstructs development worlds from operator metadata.
It passes only public records to strong_baseline, checks all original data
hashes, and never reads hidden parameters or any formal/model-evaluation result.
"""
import argparse
import hashlib
import json
import time
from pathlib import Path

import numpy as np

from env.registry import load_world
from env.scoring import canonical_hash, prediction_metrics
from .strong_baseline import VERSION, clear_fit_cache, fit_public_records, predict_fitted


_DEVELOPMENT_SEEDS = {7, 46, 1439, 8743}


def _summary(values):
    return {"count": len(values), "mean": float(np.mean(values)), "min": float(np.min(values)),
            "median": float(np.median(values)), "max": float(np.max(values))}


def compare(calibration):
    if calibration.get("protocol") != "sle-offline-calibration-0.2" or calibration.get("status") != "complete":
        raise ValueError("requires a completed offline development calibration")
    instances = [row for row in calibration["instances"] if row["environment"] == "heat_transport"]
    if len(instances) != 4 or {row["world_seed"] for row in instances} != _DEVELOPMENT_SEEDS:
        raise ValueError("comparison is restricted to the four reserved development seeds")
    outputs, start = [], time.perf_counter()
    for instance in instances:
        seed = instance["world_seed"]
        world, old_baseline = load_world("heat_transport", seed)
        if world.version != instance["world_version"]:
            raise ValueError("world version differs from original calibration")
        records = []
        for index, spec in enumerate(world.panel(instance["panel_seeds"]["development"], "development", 12)):
            noise_key = "%s:heat_transport:%d:training:%d" % (calibration["protocol"], seed, index)
            observation = world.run(spec, noise_key=noise_key)
            expected = instance["training_records"][index]
            if canonical_hash(spec) != expected["spec_sha256"] or canonical_hash(observation) != expected["observation_sha256"]:
                raise ValueError("public training data differ from original calibration")
            records.append({"spec": spec, "observation": observation})
        fits, queries = {}, []
        for count in (0, 4, 12):
            clear_fit_cache()
            fit_start = time.perf_counter()
            fitted = fit_public_records(records[:count])
            fits[str(count)] = dict(fitted, cold_fit_wall_seconds=time.perf_counter() - fit_start)
        prediction_seconds = {str(count): 0.0 for count in (0, 4, 12)}
        for original in instance["queries"]:
            spec = original["spec"]
            truth = world.run(spec)
            if canonical_hash(truth) != original["clean_truth_sha256"]:
                raise ValueError("held-out clean truth differs from original calibration")
            query = {"kind": original["kind"], "index": original["index"],
                     "spec_sha256": canonical_hash(spec), "methods": {}}
            for count in (0, 4, 12):
                old = prediction_metrics(old_baseline(records[:count], spec), truth, world.scales)
                original_metric = original["methods"]["public_%d" % count]
                if abs(old["score"] - original_metric["score"]) > 1e-9:
                    raise ValueError("original baseline/scorer changed; scores are not directly comparable")
                prediction_start = time.perf_counter()
                prediction = predict_fitted(fits[str(count)], spec)
                prediction_seconds[str(count)] += time.perf_counter() - prediction_start
                new = prediction_metrics(prediction, truth, world.scales)
                keep = np.asarray(truth["axis"]) > 0
                error = np.asarray(prediction)[keep] - np.asarray(truth["values"])[keep]
                new["channel_rmse_raw"] = np.sqrt(np.mean(error**2, axis=0)).tolist()
                query["methods"][str(count)] = {"original_interpolation": old, "public_pde_fit": new,
                                               "score_gain": new["score"] - old["score"]}
            queries.append(query)
        outputs.append({"development_world_seed": seed, "fits": fits, "queries": queries,
                        "prediction_wall_seconds": prediction_seconds})
    aggregate = {}
    for count in (0, 4, 12):
        row = {}
        for kind in ("all", "conditions", "interventions"):
            queries = [query["methods"][str(count)] for instance in outputs for query in instance["queries"]
                       if kind == "all" or query["kind"] == kind]
            row[kind] = {method: {"score": _summary([query[method]["score"] for query in queries]),
                                 "normalized_rmse": _summary([query[method]["normalized_rmse"] for query in queries])}
                         for method in ("original_interpolation", "public_pde_fit")}
        row["cold_fit_wall_seconds"] = _summary([instance["fits"][str(count)]["cold_fit_wall_seconds"] for instance in outputs])
        aggregate[str(count)] = row
    source = Path(__file__).with_name("strong_baseline.py")
    return {"protocol": "heat-public-baseline-comparison-0.1", "baseline_version": VERSION,
            "strong_baseline_source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            "original_calibration_source_sha256": calibration["source_sha256_before"],
            "original_training_and_truth_hashes_verified": True, "no_formal_or_model_results_used": True,
            "elapsed_seconds": time.perf_counter() - start, "instances": outputs, "summary": aggregate,
            "limits": [
                "Fitted parameter values are estimates only; no hidden parameter truth was inspected or compared.",
                "Local Jacobian/covariance diagnostics do not prove global or structural identifiability. Weak conductivity contrast cannot reliably locate an interface.",
                "The strong baseline fits a known public PDE family. Its score measures parameterized prediction, not novel scientific mechanism discovery.",
                "The existing interpolation baseline and all frozen formal scoring remain unchanged; this new baseline is an optional later integration."
            ]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--calibration", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    path = Path(args.output)
    if path.exists():
        raise ValueError("comparison output already exists")
    result = compare(json.loads(Path(args.calibration).read_text(encoding="utf-8")))
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, allow_nan=False, indent=2)
        stream.write("\n")
    print(json.dumps({"output": str(path), "elapsed_seconds": result["elapsed_seconds"],
                      "score_12": result["summary"]["12"]["all"]["public_pde_fit"]["score"]}))


if __name__ == "__main__":
    main()
