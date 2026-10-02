"""Fresh experimental checks of agent-chosen numerical contrasts, without answer matching.

Only paired effects are executable claims in v1. Free text is NOT certified by
these checks. Replicates vary sensor noise, not biological dynamics.
"""
from __future__ import annotations

import math

import numpy as np
from scipy.stats import t as student_t

from .lab import CHANNELS, SPECIES, validate_initial
from .protocol import InvalidAction, clone, identifier, keys, number


def claim_schema():
    return {
        "kind": "paired_effect", "max_claims": 6,
        "fields": {
            "id": "unique identifier", "statement": "description; not automatically verified",
            "initial": "create arguments, same preparation in both arms",
            "control": "list of scheduled operations", "treatment": "list of scheduled operations",
            "readout": {"species": list(SPECIES), "time_h": "(0,96]"},
            "expected_difference": "[lower, upper] for treatment minus control biomass, mmol_C/L",
            "replicates": "integer 4..12; independent sensor noise only",
            "evidence_ids": "optional list of exploration observation IDs",
            "forecast": {"optional": True, "coverage": "must be 0.9",
                         "interval": "[lower, upper]: central 90% predictive interval for the MEAN treatment-control difference across the declared replicates, including sensor noise; frozen before confirmation"},
        },
        "scheduled_operation": {"at_h": "nondecreasing, 0..readout.time_h",
                                "operation": ["feed", "deplete", "set_temperature"],
                                "arguments": "public tool arguments except vessel_id"},
        "confirmation": "Fresh vessels, identical mechanism/parameters/channel IDs; no answer list. Approximate t intervals with per-batch Bonferroni alpha allocation. Clipped readings and small samples limit calibration; this is not a formal FDR guarantee.",
        "scope": "Only the declared paired numerical prediction is checked. Causal mechanism, scientific novelty and Discovery Depth remain unassessed.",
    }


def interval_score(low, high, observed, alpha=0.1):
    """Central predictive interval score (lower is better), in observable units."""
    return float(high - low + 2 / alpha * max(low - observed, observed - high, 0))


def validate_claims(claims, known_evidence=()):
    if not isinstance(claims, list) or not 1 <= len(claims) <= 6:
        raise InvalidAction("invalid_claim_count")
    identifiers = set()
    total_cost = 0
    for claim in claims:
        keys(claim, ("id", "statement", "initial", "control", "treatment", "readout", "expected_difference", "replicates"), ("evidence_ids", "forecast"))
        cid = identifier(claim["id"])
        if cid in identifiers:
            raise InvalidAction("duplicate_claim_id")
        identifiers.add(cid)
        if not isinstance(claim["statement"], str) or not 1 <= len(claim["statement"]) <= 4000:
            raise InvalidAction("invalid_statement")
        validate_initial(claim["initial"])
        keys(claim["readout"], ("species", "time_h"))
        if not isinstance(claim["readout"]["species"], str) or claim["readout"]["species"] not in SPECIES:
            raise InvalidAction("invalid_readout")
        end = number(claim["readout"]["time_h"], 1e-6, 96, "readout_time")
        interval = claim["expected_difference"]
        if not isinstance(interval, list) or len(interval) != 2:
            raise InvalidAction("invalid_prediction_interval")
        low, high = [number(x, -100, 100, "prediction") for x in interval]
        if low >= high:
            raise InvalidAction("empty_prediction_interval")
        if "forecast" in claim:
            forecast = claim["forecast"]
            keys(forecast, ("coverage", "interval"))
            number(forecast["coverage"], 0.9, 0.9, "forecast_coverage")
            bounds = forecast["interval"]
            if not isinstance(bounds, list) or len(bounds) != 2:
                raise InvalidAction("invalid_forecast_interval")
            lower, upper = [number(x, -100, 100, "forecast_bound") for x in bounds]
            if lower >= upper:
                raise InvalidAction("empty_forecast_interval")
        n = claim["replicates"]
        if type(n) is not int or not 4 <= n <= 12:
            raise InvalidAction("invalid_replicates")
        evidence = claim.get("evidence_ids", [])
        if (not isinstance(evidence, list) or len(evidence) > 100 or any(not isinstance(e, str) for e in evidence)
                or len(set(evidence)) != len(evidence) or not set(evidence) <= set(known_evidence)):
            raise InvalidAction("unknown_evidence")
        for arm in ("control", "treatment"):
            schedule = claim[arm]
            if not isinstance(schedule, list) or len(schedule) > 16:
                raise InvalidAction("invalid_schedule")
            previous = 0.0
            cost = 12  # fresh preparation + endpoint measurement
            cumulative_feed = 0.0
            for item in schedule:
                keys(item, ("at_h", "operation", "arguments"))
                at = number(item["at_h"], previous, end, "scheduled_time")
                cost += math.ceil((at - previous) / 6)
                previous = at
                args = item["arguments"]
                if item["operation"] == "feed":
                    keys(args, ("amount_mmol",))
                    amount = number(args["amount_mmol"], 1e-9, 5 * claim["initial"]["volume_ml"] / 1000, "amount_mmol")
                    cumulative_feed += amount * 1000 / claim["initial"]["volume_ml"]
                    if claim["initial"]["nutrient"] + cumulative_feed > 50:
                        raise InvalidAction("confirmation_nutrient_capacity")
                    cost += 2
                elif item["operation"] == "deplete":
                    keys(args, ("channel", "fraction"))
                    if args["channel"] not in CHANNELS:
                        raise InvalidAction("unknown_channel")
                    number(args["fraction"], 0, 1, "fraction")
                    cost += 3
                elif item["operation"] == "set_temperature":
                    keys(args, ("temperature_c",))
                    number(args["temperature_c"], 20, 40, "temperature_c")
                    cost += 1
                else:
                    raise InvalidAction("unsupported_confirmation_operation")
            cost += math.ceil((end - previous) / 6)
            total_cost += n * cost
    return clone(claims), total_cost


def verify_claims(lab, claims, log):
    results, spent = [], 0
    for index, claim in enumerate(claims):
        differences, measurements = [], []
        for replicate in range(claim["replicates"]):
            pair = {}
            for arm in ("control", "treatment"):
                fresh = lab.fresh("confirmation:%d:%d:%s" % (index, replicate, arm))
                scope = {"claim_id": claim["id"], "replicate": replicate, "arm": arm}

                def execute(operation, args):
                    nonlocal spent
                    cost = fresh.validate(operation, args)
                    value = fresh.execute(operation, args)
                    spent += cost
                    log.append("confirmation_operation", {**scope, "operation": operation, "arguments": args,
                                                          "observation": value, "charged_units": cost})
                    return value

                vessel = execute("create", claim["initial"])["vessel_id"]

                def advance_to(at):
                    while at - fresh.time_h > 1e-9:
                        execute("advance", {"hours": min(48.0, at - fresh.time_h)})

                for item in claim[arm]:
                    advance_to(item["at_h"])
                    execute(item["operation"], {"vessel_id": vessel, **item["arguments"]})
                advance_to(claim["readout"]["time_h"])
                observation = execute("measure", {"vessel_id": vessel, "instrument": "counts"})
                pair[arm] = observation["values"][claim["readout"]["species"]]
            measurements.append({"replicate": replicate, **pair})
            differences.append(pair["treatment"] - pair["control"])
        alpha = 0.05 / len(claims)
        mean = float(np.mean(differences))
        sem = float(np.std(differences, ddof=1) / math.sqrt(len(differences)))
        half = float(student_t.ppf(1 - alpha / 2, len(differences) - 1)) * sem
        interval = [mean - half, mean + half]
        low, high = claim["expected_difference"]
        status = ("prediction_supported" if low <= interval[0] and interval[1] <= high
                  else "prediction_refuted" if interval[1] < low or interval[0] > high else "inconclusive")
        result = {"claim_id": claim["id"], "status": status, "mean_difference": mean,
                  "confidence_interval": interval, "interval_method": "approximate_t",
                  "alpha": alpha, "expected_difference": [low, high], "replicate_measurements": measurements,
                  "replication_scope": "new_preparations_identical_deterministic_dynamics_independent_sensor_noise",
                  "semantic_review": "unassessed", "discovery_depth": None}
        result["effect_band_width"] = high - low
        if "forecast" in claim:
            lower, upper = claim["forecast"]["interval"]
            result["forecast_evaluation"] = {
                "target": "mean_treatment_minus_control_across_declared_sensor_replicates",
                "coverage": 0.9, "interval": [lower, upper], "observed": mean,
                "width": upper - lower, "covered": lower <= mean <= upper,
                "interval_score": interval_score(lower, upper, mean), "lower_is_better": True,
                "units": "mmol_C/L", "calibration": "not_established_by_one_confirmation_batch"}
        log.append("claim_verification", result)
        results.append(result)
    return {"results": results, "charged_units": spent, "answer_matching": False,
            "scope": "Declared numerical contrasts only; free-text explanation and mechanisms are not certified."}
