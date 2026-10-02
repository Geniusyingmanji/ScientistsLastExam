"""Reproducible, model-free development calibration of explicit world families.

Run with ``python -m env.calibration --environments heat_transport,ising_spin
--output /absolute/operator/path/calibration.json``. Outputs are operator-only.
The four default world seeds are reserved for development, never formal cohorts.
"""
import argparse
import copy
import hashlib
import json
import math
import time
from pathlib import Path

import numpy as np

from .registry import ENVIRONMENTS, load_world
from .runner import source_digest
from .scoring import canonical_hash, prediction_metrics


DEVELOPMENT_SEEDS = (7, 46, 1439, 8743)
RECORD_COUNTS = (0, 4, 12)
METHODS = ("zero", "initial", "public_0", "public_4", "public_12")
PROTOCOL = "sle-offline-calibration-0.2"


def _panel_seed(name, world_seed, purpose):
    data = json.dumps([PROTOCOL, name, world_seed, purpose], separators=(",", ":")).encode()
    return int.from_bytes(hashlib.sha256(data).digest()[:8], "big") % (2**63)


def _initial(name, spec, channels):
    """Only public initial conditions; never a first held-out observation."""
    if name == "heat_transport":
        return [spec["initial_temperature"]] * len(channels)
    if name in ("microecology", "microecology_causal"):
        values = [spec["initial"][key] for key in ("A", "B", "C", "nutrient")] + [0.0] * 3
        # The public adapter applies time-zero feeds before measurement.
        for event in spec.get("events", []):
            if event["time_h"] == 0 and "feed" in event:
                values[3] += event["feed"]
        return values
    if name == "reaction_kinetics":
        return list(spec["initial_mM"])
    if name == "coupled_oscillators":
        return list(spec["initial_position"]) + list(spec["initial_velocity"])
    if name == "orbital_dynamics":
        return list(spec["position"]) + list(spec["velocity"])
    if name == "pattern_formation":
        # Public sinusoidal assignment at the declared probe positions only.
        from .pattern_formation.protocol import initial_values
        return initial_values(spec).tolist()
    if name == "gene_regulation":
        return list(spec["initial_expression"])
    if name == "ising_spin":
        return None  # Temperature sweeps have no public time-zero state.
    if name == "hysteresis_material":
        return None  # Preparation fixes a field history, not the response value.
    if name == "electrical_impedance":
        return None  # Every frequency is a steady state; no initial value is assigned.
    raise ValueError("no declared initial-value semantics for this environment")


def _keep(observation):
    mask = np.ones(len(observation["axis"]), dtype=bool)
    if len(mask) > 1 and observation["axis"][0] == 0:
        mask[0] = False
    return mask


def _metrics(prediction, observation, scales):
    metric = prediction_metrics(prediction, observation, scales)
    error = (np.asarray(prediction, dtype=float) - np.asarray(observation["values"], dtype=float))[_keep(observation)]
    metric.update(valid=True, channel_rmse_raw=np.sqrt(np.mean(error**2, axis=0)).tolist(),
                  channel_bias_raw=np.mean(error, axis=0).tolist(),
                  prediction_sha256=canonical_hash(np.asarray(prediction, dtype=float).tolist()))
    return metric


def _distribution(values):
    values = np.asarray([value for value in values if value is not None], dtype=float)
    if not len(values):
        return {"count": 0, "mean": None, "std": None, "min": None, "q25": None,
                "median": None, "q75": None, "max": None}
    return {"count": int(len(values)), "mean": float(np.mean(values)), "std": float(np.std(values)),
            "min": float(np.min(values)), "q25": float(np.quantile(values, .25)),
            "median": float(np.median(values)), "q75": float(np.quantile(values, .75)),
            "max": float(np.max(values))}


def _method_summary(queries):
    result = {}
    for method in METHODS:
        entries = [query["methods"][method] for query in queries if method in query["methods"]]
        usable = [entry for entry in entries if entry.get("valid")]
        result[method] = {
            "requested_predictions": len(entries), "valid_predictions": len(usable),
            "invalid_predictions": len(entries) - len(usable),
            # Failed baseline calls count zero in score; undefined RMSE is kept
            # out of its distribution with a visible validity denominator.
            "score": _distribution([entry["score"] for entry in entries]),
            "normalized_rmse": _distribution([entry.get("normalized_rmse") for entry in usable]),
        }
    return result


def _summarize(instances, names):
    result = {}
    for name in names:
        rows = [row for row in instances if row["environment"] == name]
        queries = [query for row in rows for query in row["queries"]]
        flags = []
        methods = _method_summary(queries)
        if methods["public_0"]["score"]["mean"] is not None and methods["public_0"]["score"]["mean"] >= 70:
            flags.append("high_zero_data_public_baseline_score")
        if methods["zero"]["score"]["mean"] is not None and methods["zero"]["score"]["mean"] >= 50:
            flags.append("high_all_zero_predictor_score")
        if methods["initial"]["score"]["mean"] is not None and methods["initial"]["score"]["mean"] >= 50:
            flags.append("high_constant_initial_predictor_score")
        if any(item["invalid_predictions"] for item in methods.values()):
            flags.append("baseline_runtime_or_output_failure")
        paired = {"public_4_minus_0": [], "public_12_minus_4": []}
        for query in queries:
            metrics = query["methods"]
            paired["public_4_minus_0"].append(metrics["public_4"]["score"] - metrics["public_0"]["score"])
            paired["public_12_minus_4"].append(metrics["public_12"]["score"] - metrics["public_4"]["score"])
        delta = _distribution(paired["public_12_minus_4"])
        if delta["mean"] is not None and delta["mean"] < -2:
            flags.append("public_baseline_regresses_from_4_to_12_records")
        result[name] = {
            "worlds": len(rows), "queries": len(queries), "methods": methods,
            "by_panel": {kind: _method_summary([query for query in queries if query["kind"] == kind])
                         for kind in ("conditions", "interventions")},
            "paired_score_changes": {key: _distribution(values) for key, values in paired.items()},
            "active_signal_to_noise": _distribution([query["signal"]["active_signal_to_noise"]
                                                     for query in queries if query.get("signal")]),
            "active_normalized_rms": _distribution([query["signal"]["active_normalized_rms"]
                                                    for query in queries if query.get("signal")]),
            "flags": flags,
        }
    return result


def calibrate(names, *, seeds=DEVELOPMENT_SEEDS, panel_count=4, max_seconds=120):
    """Compare five baselines on disjoint development panels, without API calls.

    Work is bounded by the registered families, <=16 seeds, <=8 queries per panel,
    exactly 12 training calls per world and a wall-time stop checked between
    bounded kernel/baseline calls. No formal/test outcome is read or fitted.
    """
    if not isinstance(names, (list, tuple)) or not names or len(names) > len(ENVIRONMENTS) or any(not isinstance(name, str) for name in names) or len(set(names)) != len(names) or any(name not in ENVIRONMENTS for name in names):
        raise ValueError("select distinct registered environment names explicitly")
    if not isinstance(seeds, (list, tuple)) or not 1 <= len(seeds) <= 16 or any(type(seed) is not int or not 0 <= seed < 2**63 for seed in seeds) or len(set(seeds)) != len(seeds):
        raise ValueError("seeds must contain 1..16 distinct integers in [0, 2**63)")
    if type(panel_count) is not int or not 1 <= panel_count <= 8:
        raise ValueError("panel_count must be an integer in [1, 8]")
    if isinstance(max_seconds, bool) or not isinstance(max_seconds, (int, float)) or not 0 < max_seconds <= 3600 or not math.isfinite(max_seconds):
        raise ValueError("max_seconds must be finite in (0, 3600]")
    start, instances = time.monotonic(), []
    source_before = source_digest()
    exhausted = False

    def check_time():
        if time.monotonic() - start >= max_seconds:
            raise TimeoutError("calibration time budget exhausted")

    for name in names:
        if exhausted:
            break
        for seed in seeds:
            try:
                check_time()
                world, public_baseline = load_world(name, seed)
                panel_seeds = {kind: _panel_seed(name, seed, kind)
                               for kind in ("development", "conditions", "interventions")}
                training = world.panel(panel_seeds["development"], "development", max(RECORD_COUNTS))
                panels = {kind: world.panel(panel_seeds[kind], kind, panel_count)
                          for kind in ("conditions", "interventions")}
                training_hashes = {canonical_hash(spec) for spec in training}
                heldout_hashes = {canonical_hash(spec) for panel in panels.values() for spec in panel}
                if training_hashes & heldout_hashes:
                    raise ValueError("calibration training and evaluation panels overlap")
                if set(canonical_hash(spec) for spec in panels["conditions"]) & set(canonical_hash(spec) for spec in panels["interventions"]):
                    raise ValueError("calibration condition and intervention panels overlap")
                records = []
                for index, spec in enumerate(training):
                    check_time()
                    noise_key = "%s:%s:%d:training:%d" % (PROTOCOL, name, seed, index)
                    records.append({"id": "cal-%02d" % (index + 1), "spec": world.validate(spec),
                                    "observation": world.run(spec, noise_key=noise_key), "cost": world.cost(spec)})
                row = {"environment": name, "world_version": world.version, "world_seed": seed,
                       "panel_seeds": panel_seeds, "channels": list(world.channels), "scales": list(world.scales),
                       "noise_std": list(world.noise_std), "training_records": [
                           {"id": record["id"], "spec_sha256": canonical_hash(record["spec"]),
                            "observation_sha256": canonical_hash(record["observation"]), "cost": record["cost"]}
                           for record in records],
                       "training_cost_by_record_count": {str(count): sum(record["cost"] for record in records[:count]) for count in RECORD_COUNTS},
                       "queries": []}
                for kind, panel in panels.items():
                    for index, spec in enumerate(panel):
                        check_time()
                        observed = world.run(spec)
                        shape = np.asarray(observed["values"]).shape
                        query = {"kind": kind, "index": index, "spec": spec,
                                 "spec_sha256": canonical_hash(spec), "clean_truth_sha256": canonical_hash(observed),
                                 "methods": {}, "signal": None}
                        initial = _initial(name, spec, world.channels)
                        predictions = {"zero": np.zeros(shape).tolist()}
                        if initial is not None:
                            predictions["initial"] = np.tile(initial, (shape[0], 1)).tolist()
                        zero_data_prediction = None
                        for method in METHODS:
                            if method == "initial" and initial is None:
                                continue
                            check_time()
                            try:
                                predicted = predictions[method] if method in predictions else public_baseline(
                                    copy.deepcopy(records[:int(method.split("_")[1])]), copy.deepcopy(spec))
                                query["methods"][method] = _metrics(predicted, observed, world.scales)
                                if method == "public_0":
                                    zero_data_prediction = np.asarray(predicted, dtype=float)
                            except Exception as exc:
                                query["methods"][method] = {"valid": False, "score": 0.0,
                                                            "normalized_rmse": None, "error": type(exc).__name__}
                        if zero_data_prediction is not None:
                            residual = (np.asarray(observed["values"]) - zero_data_prediction)[_keep(observed)]
                            channel_rms = np.sqrt(np.mean(residual**2, axis=0))
                            noise = np.asarray(world.noise_std)
                            snr = [float(signal / sigma) if sigma > 0 else None for signal, sigma in zip(channel_rms, noise)]
                            positive = noise > 0
                            query["signal"] = {
                                "reference": "zero-data public baseline with known controls",
                                "active_normalized_rms": float(np.sqrt(np.mean((residual / np.asarray(world.scales))**2))),
                                "active_signal_to_noise": float(np.sqrt(np.mean((residual[:, positive] / noise[positive])**2))) if np.any(positive) else None,
                                "channel_active_rms_raw": channel_rms.tolist(), "channel_active_signal_to_noise": snr,
                            }
                        row["queries"].append(query)
                instances.append(row)
            except TimeoutError:
                exhausted = True
                break
    result = {
        "protocol": PROTOCOL, "status": "budget_exhausted" if exhausted else "complete",
        "selected_environments": list(names), "development_seeds": list(seeds), "panel_count_per_kind": panel_count,
        "record_counts": list(RECORD_COUNTS), "methods": list(METHODS),
        "initial_baseline_unavailable": {
            name: reason for name, reason in (
                ("ising_spin", "Equilibrium temperature sweeps have no public initial state."),
                ("electrical_impedance", "Independent frequency steady states have no assigned initial value."))
            if name in names},
        "source_sha256_before": source_before, "source_sha256_after": source_digest(),
        "elapsed_seconds": time.monotonic() - start, "max_seconds": max_seconds,
        "completed_instances": len(instances), "planned_instances": len(names) * len(seeds),
        "instances": instances, "summary": _summarize(instances, names),
        "interpretation": [
            "Development calibration only; reserve these world seeds from later formal cohorts.",
            "Training uses exactly the same nested noisy-record prefixes at 4 and 12; evaluation specifications are hash-disjoint from training and from the other evaluation panel.",
            "Scales and existing scoring are unchanged. Scores are prediction subscores, not the 50/30/20 episode score; no claims are generated.",
            "Each experiment is weighted equally; raw per-channel RMSE retains channel units. Initial-time rows are excluded exactly as in the shared scorer.",
            "Signal/noise is RMS clean departure from the zero-data public baseline divided by declared independent measurement noise; it is not a causal-effect SNR or an empirical clipped-noise variance estimate.",
            "Public baselines differ in sophistication across environments; their cross-family scores are not a model-capability ranking or a universal difficulty measure.",
            "Known-family parameter fitting can score highly without novel mechanism discovery; weak identifiability, semantic duplicate effects and physically predetermined observables need separate evidence review.",
            "Flag thresholds are descriptive fixed heuristics: zero-data public >=70, zero/initial >=50, mean 12-minus-4 score <-2. They are not acceptance thresholds and never tune normalization scales.",
            "The wall-time stop is checked between bounded calls; an in-progress kernel is not interrupted. Partial worlds are omitted and the completion denominator remains explicit."
        ],
    }
    result["source_stable"] = result["source_sha256_before"] == result["source_sha256_after"]
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--environments", required=True, help="Explicit comma-separated registered names")
    parser.add_argument("--seeds", default=",".join(str(seed) for seed in DEVELOPMENT_SEEDS))
    parser.add_argument("--panel-count", type=int, default=4)
    parser.add_argument("--max-seconds", type=float, default=120)
    parser.add_argument("--output", required=True, help="Operator artifact JSON path; existing outputs are not overwritten")
    args = parser.parse_args()
    path = Path(args.output)
    if path.exists():
        raise ValueError("calibration output already exists")
    result = calibrate(args.environments.split(","), seeds=tuple(int(seed) for seed in args.seeds.split(",")),
                       panel_count=args.panel_count, max_seconds=args.max_seconds)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, allow_nan=False, indent=2)
        stream.write("\n")
    print(json.dumps({"status": result["status"], "completed_instances": result["completed_instances"],
                      "elapsed_seconds": result["elapsed_seconds"], "source_stable": result["source_stable"],
                      "output": str(path)}))


if __name__ == "__main__":
    main()
