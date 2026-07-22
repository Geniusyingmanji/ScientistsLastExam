"""Active multi-regime laboratory for Arrhenius reaction-mechanism discovery.

Candidates choose batch-reactor temperatures, initial compositions and sample times under a
strict budget.  They return a sparse reaction support plus Arrhenius parameters, confidence or
an explicit refusal.  Prediction, rate-curve recovery, null/model-inadequacy refusal and
held-out transfer remain separate; a concentration fit is never treated as mechanism proof.
"""

from __future__ import annotations

import hashlib
import math

import numpy as np
from scipy.integrate import solve_ivp
from scipy.linalg import expm


R_GAS = 8.31446261815324
SPECIES_NAMES = ("A", "B", "C", "D")
N_SPECIES = len(SPECIES_NAMES)
REACTION_PAIRS = (
    (0, 1),  # A -> B
    (1, 2),  # B -> C
    (0, 2),  # A -> C
    (1, 3),  # B -> D
    (2, 3),  # C -> D
    (0, 3),  # A -> D
    (2, 1),  # C -> B
    (3, 2),  # D -> C
    (1, 0),  # B -> A
    (2, 0),  # C -> A
    (3, 0),  # D -> A
    (3, 1),  # D -> B
)
REACTION_NAMES = tuple(
    "%s->%s" % (SPECIES_NAMES[source], SPECIES_NAMES[target])
    for source, target in REACTION_PAIRS
)
N_REACTIONS = len(REACTION_PAIRS)

TEMPERATURE_BOUNDS_K = (330.0, 480.0)
MAX_EXPERIMENT_TIME_S = 20.0
MIN_SAMPLES = 6
MAX_SAMPLES = 24
MAX_OBSERVED_SPECIES = 2
BUDGET_UNITS = 12
LOG_A_BOUNDS = (5.0, 25.0)
ACTIVATION_ENERGY_BOUNDS = (15000.0, 90000.0)


# Each in-library template selects genuinely different reaction topology.  Parameter values
# produce observable transitions rather than the old oracle's all-complete regime.
TEMPLATE_SUPPORTS = (
    (0, 1, 4),
    (2, 3, 7),
    (0, 1, 4, 6),
    (1, 4, 5, 8),
    (2, 3, 7, 9),
    (0, 5, 6, 11),
)
BASE_LOG_A = np.asarray((
    13.0, 14.2, 15.2, 12.8, 12.4, 11.8, 13.5, 12.0,
    13.1, 14.6, 12.0, 13.8,
))
BASE_ENERGY = np.asarray((42000.0, 49000.0, 55000.0, 46000.0,
                          44000.0, 38000.0, 48000.0, 41000.0,
                          43000.0, 52000.0, 39000.0, 47000.0))


# (seed, template, observation noise, kind).  Order deliberately interleaves scientific
# regimes; split and kind never cross the candidate boundary.
DEVELOPMENT_SPECS = (
    (52021, 0, 0.0040, "in_library"),
    (52027, 1, 0.0045, "in_library"),
    (52051, 2, 0.0050, "in_library"),
    (52057, 3, 0.0045, "in_library"),
    (52067, 0, 0.0040, "null"),
    (52069, 0, 0.0050, "misspecified"),
)
HELDOUT_SPECS = (
    (62011, 4, 0.0060, "in_library"),
    (62017, 5, 0.0065, "in_library"),
    (62039, 0, 0.0070, "in_library"),
    (62047, 0, 0.0060, "null"),
    (62053, 0, 0.0070, "misspecified"),
)


def _make_parameters(seed, template):
    if not 0 <= int(template) < len(TEMPLATE_SUPPORTS):
        raise ValueError("unknown mechanism template")
    rng = np.random.default_rng(int(seed))
    support = np.zeros(N_REACTIONS, dtype=bool)
    support[list(TEMPLATE_SUPPORTS[int(template)])] = True
    log_a = np.zeros(N_REACTIONS, dtype=float)
    energy = np.zeros(N_REACTIONS, dtype=float)
    log_a[support] = BASE_LOG_A[support] + rng.uniform(
        -0.18, 0.18, size=int(np.sum(support))
    )
    energy[support] = BASE_ENERGY[support] + rng.uniform(
        -1100.0, 1100.0, size=int(np.sum(support))
    )
    return support, log_a, energy


def _world(spec):
    seed, template, noise, kind = spec
    if kind == "in_library":
        support, log_a, energy = _make_parameters(seed, template)
    else:
        support = np.zeros(N_REACTIONS, dtype=bool)
        log_a = np.zeros(N_REACTIONS, dtype=float)
        energy = np.zeros(N_REACTIONS, dtype=float)
    rng = np.random.default_rng(int(seed) + 1717)
    return {
        "seed": int(seed),
        "template": int(template),
        "noise": float(noise),
        "kind": str(kind),
        "support": support,
        "log_a": log_a,
        "activation_energy": energy,
        # The misspecified world uses saturating A -> B kinetics.  Its concentration-
        # dependent effective first-order rate cannot be represented by the public library.
        "misspecified_log_vmax": 11.55 + float(rng.uniform(-0.12, 0.12)),
        "misspecified_energy": 38000.0 + float(rng.uniform(-700.0, 700.0)),
        "misspecified_km": 0.16 + float(rng.uniform(-0.025, 0.025)),
    }


def _rate_constants(log_a, energy, support, temperature_k):
    rates = np.zeros(N_REACTIONS, dtype=float)
    active = np.asarray(support, dtype=bool)
    rates[active] = np.exp(
        np.asarray(log_a, dtype=float)[active]
        - np.asarray(energy, dtype=float)[active]
        / (R_GAS * float(temperature_k))
    )
    if np.any(~np.isfinite(rates)) or np.any(rates < 0.0):
        raise ValueError("invalid Arrhenius rate constants")
    return rates


def _generator(rates):
    generator = np.zeros((N_SPECIES, N_SPECIES), dtype=float)
    for rate, (source, target) in zip(np.asarray(rates, dtype=float), REACTION_PAIRS):
        generator[source, source] -= float(rate)
        generator[target, source] += float(rate)
    return generator


def _linear_simulate(rates, initial, sample_times):
    generator = _generator(rates)
    initial = np.asarray(initial, dtype=float)
    values = np.asarray([
        expm(generator * float(time)) @ initial for time in sample_times
    ], dtype=float)
    if np.any(~np.isfinite(values)):
        raise RuntimeError("linear reaction simulation became non-finite")
    return np.clip(values, 0.0, 1.0)


def _simulate(world, temperature_k, initial, sample_times):
    initial = np.asarray(initial, dtype=float)
    times = np.asarray(sample_times, dtype=float)
    if world["kind"] in {"in_library", "null"}:
        rates = _rate_constants(
            world["log_a"], world["activation_energy"], world["support"],
            temperature_k,
        )
        return _linear_simulate(rates, initial, times)

    vmax = math.exp(
        float(world["misspecified_log_vmax"])
        - float(world["misspecified_energy"]) / (R_GAS * float(temperature_k))
    )
    km = float(world["misspecified_km"])

    def derivative(_time, concentrations):
        a = max(float(concentrations[0]), 0.0)
        flux = vmax * a / (km + a)
        return np.asarray((-flux, flux, 0.0, 0.0), dtype=float)

    solution = solve_ivp(
        derivative, (0.0, float(times[-1])), initial, t_eval=times,
        method="Radau", rtol=2e-9, atol=2e-11,
    )
    if not solution.success or solution.y.shape != (N_SPECIES, len(times)):
        raise RuntimeError("misspecified reaction simulation failed")
    values = solution.y.T
    if np.any(~np.isfinite(values)):
        raise RuntimeError("misspecified reaction simulation became non-finite")
    return np.clip(values, 0.0, 1.0)


def _query_seed(
    world_seed, call_index, temperature, initial, sample_times, observed_species
):
    payload = np.concatenate((
        np.asarray((temperature,), dtype="<f8"),
        np.asarray(initial, dtype="<f8").ravel(),
        np.asarray(sample_times, dtype="<f8").ravel(),
        np.asarray(observed_species, dtype="<f8").ravel(),
    )).tobytes()
    digest = hashlib.sha256(payload).digest()
    words = np.frombuffer(digest[:16], dtype="<u4").astype(np.uint32)
    sequence = np.random.SeedSequence([
        int(world_seed), int(call_index), *[int(value) for value in words]
    ])
    return int(sequence.generate_state(1, dtype=np.uint32)[0])


class _Laboratory:
    def __init__(self, world):
        self.world = world
        self.used = 0
        self.calls = 0
        self.violated = False

    def experiment(
        self, temperature_k, initial_concentrations, sample_times_s,
        observed_species,
    ):
        temperature = float(temperature_k)
        if not math.isfinite(temperature) or not (
            TEMPERATURE_BOUNDS_K[0] <= temperature <= TEMPERATURE_BOUNDS_K[1]
        ):
            raise ValueError("temperature outside the public bounds")
        initial = np.asarray(initial_concentrations, dtype=float)
        if initial.shape != (N_SPECIES,) or np.any(~np.isfinite(initial)):
            raise ValueError("initial_concentrations must contain four finite values")
        if np.any(initial < 0.0) or np.any(initial > 1.0):
            raise ValueError("initial concentrations must lie in [0,1]")
        if abs(float(np.sum(initial)) - 1.0) > 1e-8:
            raise ValueError("initial concentrations must sum to one")
        times = np.asarray(sample_times_s, dtype=float)
        if times.ndim != 1 or not MIN_SAMPLES <= len(times) <= MAX_SAMPLES:
            raise ValueError("sample_times_s has an invalid length")
        if np.any(~np.isfinite(times)) or abs(float(times[0])) > 1e-12:
            raise ValueError("sample times must be finite and start at zero")
        if np.any(np.diff(times) <= 0.0) or float(times[-1]) > MAX_EXPERIMENT_TIME_S:
            raise ValueError("sample times must increase within the public horizon")
        observed_raw = np.asarray(observed_species)
        if observed_raw.ndim != 1 or not (
            1 <= len(observed_raw) <= MAX_OBSERVED_SPECIES
        ):
            raise ValueError("observed_species must select one or two species")
        try:
            observed_float = observed_raw.astype(float)
            observed = observed_raw.astype(int)
        except (TypeError, ValueError, OverflowError):
            raise ValueError("observed_species must contain finite integer indices")
        if np.any(~np.isfinite(observed_float)) or np.any(
            observed_float != observed
        ):
            raise ValueError("observed_species must contain finite integer indices")
        if np.any(observed < 0) or np.any(observed >= N_SPECIES):
            raise ValueError("observed species index outside the public list")
        if len(np.unique(observed)) != len(observed):
            raise ValueError("observed species indices must be unique")
        # A denser time series and every assayed species consume experimental budget.
        # This makes observability an explicit design choice: reconstructing all four
        # species requires two separately charged experiments under identical conditions.
        assay_blocks = max(2, int(math.ceil(len(times) / 8.0)))
        cost = 1 + len(observed) * assay_blocks
        if self.used + cost > BUDGET_UNITS:
            self.violated = True
            raise RuntimeError("experimental budget exceeded")
        self.used += cost
        self.calls += 1
        clean = _simulate(self.world, temperature, initial, times)
        rng = np.random.default_rng(_query_seed(
            self.world["seed"], self.calls, temperature, initial, times,
            observed,
        ))
        measured = clean[:, observed]
        measured = measured + rng.normal(
            scale=self.world["noise"], size=measured.shape
        )
        return {
            "temperature_k": temperature,
            "initial_concentrations": initial.copy(),
            "time_s": times.copy(),
            "observed_species": observed.copy(),
            "concentrations": np.clip(measured, 0.0, 1.05),
            "budget_cost": int(cost),
        }


def _validate_submission(submission):
    if not isinstance(submission, dict):
        raise ValueError("submission must be a dictionary")
    if not isinstance(submission.get("abstain"), (bool, np.bool_)):
        raise ValueError("abstain must be a boolean")
    confidence = float(submission.get("confidence"))
    if not math.isfinite(confidence) or not 0.0 <= confidence <= 1.0:
        raise ValueError("confidence must be finite and in [0,1]")
    log_a = np.asarray(submission.get("log_pre_exponential"), dtype=float)
    energy = np.asarray(submission.get("activation_energy_j_mol"), dtype=float)
    support_raw = np.asarray(submission.get("support"), dtype=float)
    for name, value in (
        ("log_pre_exponential", log_a),
        ("activation_energy_j_mol", energy),
        ("support", support_raw),
    ):
        if value.shape != (N_REACTIONS,) or np.any(~np.isfinite(value)):
            raise ValueError("%s must be a finite length-%d array" % (name, N_REACTIONS))
    if np.any(support_raw < 0.0) or np.any(support_raw > 1.0) or np.any(
        support_raw != np.rint(support_raw)
    ):
        raise ValueError("support must contain exact zero/one labels")
    support = support_raw.astype(bool)
    if bool(submission["abstain"]):
        if np.any(support):
            raise ValueError("abstention requires empty reaction support")
        return (
            np.zeros(N_REACTIONS), np.zeros(N_REACTIONS), support,
            confidence, True,
        )
    if not np.any(support):
        raise ValueError("a non-abstaining mechanism needs at least one reaction")
    if np.any(log_a[support] < LOG_A_BOUNDS[0]) or np.any(
        log_a[support] > LOG_A_BOUNDS[1]
    ):
        raise ValueError("active log pre-exponentials lie outside public bounds")
    if np.any(energy[support] < ACTIVATION_ENERGY_BOUNDS[0]) or np.any(
        energy[support] > ACTIVATION_ENERGY_BOUNDS[1]
    ):
        raise ValueError("active activation energies lie outside public bounds")
    log_a = np.where(support, log_a, 0.0)
    energy = np.where(support, energy, 0.0)
    return log_a, energy, support, confidence, False


def _mechanism_metrics(world, log_a, energy, predicted_support, abstain):
    if world["kind"] in {"null", "misspecified"}:
        correct = bool(abstain and not np.any(predicted_support))
        return {
            "support_f1": 1.0 if correct else 0.0,
            "rate_curve_score": 1.0 if correct else 0.0,
            "mechanism_score": 1.0 if correct else 0.0,
            "correct_refusal": correct,
            "false_discovery": not correct,
        }
    true_support = world["support"]
    if abstain:
        predicted_support = np.zeros_like(true_support)
    tp = int(np.sum(true_support & predicted_support))
    fp = int(np.sum(~true_support & predicted_support))
    fn = int(np.sum(true_support & ~predicted_support))
    if tp == 0:
        support_f1 = 0.0
    else:
        precision = tp / (tp + fp)
        recall = tp / (tp + fn)
        support_f1 = 2.0 * precision * recall / (precision + recall)
    temperatures = np.asarray((320.0, 345.0, 375.0, 410.0, 450.0, 485.0, 505.0))
    credits = []
    for index in np.flatnonzero(true_support):
        if not predicted_support[index]:
            credits.append(0.0)
            continue
        true_log_rates = (
            world["log_a"][index]
            - world["activation_energy"][index] / (R_GAS * temperatures)
        )
        predicted_log_rates = (
            log_a[index] - energy[index] / (R_GAS * temperatures)
        )
        error = np.asarray(predicted_log_rates - true_log_rates, dtype=float)
        credits.append(float(np.mean(np.exp(-0.5 * (error / 0.55) ** 2))))
    rate_curve = float(np.mean(credits))
    mechanism = 0.55 * support_f1 + 0.45 * rate_curve
    return {
        "support_f1": float(support_f1),
        "rate_curve_score": rate_curve,
        "mechanism_score": float(mechanism),
        "correct_refusal": False,
        "false_discovery": False,
    }


def _prediction_score(world, log_a, energy, support, extrapolation):
    temperatures = (
        (315.0, 505.0) if extrapolation else (345.0, 395.0, 455.0)
    )
    rng = np.random.default_rng(
        world["seed"] + (800003 if extrapolation else 700001)
    )
    squared_errors = []
    baseline_errors = []
    times = np.asarray((0.0, 0.015, 0.04, 0.10, 0.25, 0.60, 1.4, 3.5, 8.0))
    for temperature in temperatures:
        predicted_rates = _rate_constants(log_a, energy, support, temperature)
        for _ in range(3):
            initial = rng.dirichlet(np.asarray((0.7, 0.8, 0.9, 0.6)))
            truth = _simulate(world, temperature, initial, times)
            predicted = _linear_simulate(predicted_rates, initial, times)
            baseline = np.repeat(initial[None, :], len(times), axis=0)
            squared_errors.append(float(np.mean((predicted - truth) ** 2)))
            baseline_errors.append(float(np.mean((baseline - truth) ** 2)))
    rmse = math.sqrt(float(np.mean(squared_errors)))
    baseline_rmse = max(0.025, math.sqrt(float(np.mean(baseline_errors))))
    return float(np.clip(1.0 - rmse / baseline_rmse, 0.0, 1.0))


def _reference_submission(world):
    if world["kind"] != "in_library":
        return {
            "log_pre_exponential": np.zeros(N_REACTIONS),
            "activation_energy_j_mol": np.zeros(N_REACTIONS),
            "support": np.zeros(N_REACTIONS, dtype=int),
            "confidence": 0.0,
            "abstain": True,
        }
    return {
        "log_pre_exponential": world["log_a"].copy(),
        "activation_energy_j_mol": world["activation_energy"].copy(),
        "support": world["support"].astype(int),
        "confidence": 1.0,
        "abstain": False,
    }


def _evaluate_world(discover_mechanism, spec, split, index):
    world = _world(spec)
    laboratory = _Laboratory(world)
    try:
        submission = discover_mechanism(
            SPECIES_NAMES, REACTION_PAIRS, laboratory.experiment, BUDGET_UNITS
        )
        log_a, energy, support, confidence, abstain = _validate_submission(submission)
        if laboratory.violated:
            raise RuntimeError("experimental budget exceeded")
        mechanism = _mechanism_metrics(world, log_a, energy, support, abstain)
        interpolation = _prediction_score(
            world, log_a, energy, support, extrapolation=False
        )
        extrapolation = _prediction_score(
            world, log_a, energy, support, extrapolation=True
        )
        # Confidence is confidence in a positive in-library mechanism claim.  A
        # plausible but wrong mechanism must not receive perfect calibration merely
        # because the hidden world happens to be generated from the public library.
        target_confidence = (
            mechanism["mechanism_score"]
            if world["kind"] == "in_library" else 0.0
        )
        return {
            "split": split,
            "world_index": int(index),
            "kind": world["kind"],
            "valid": True,
            "support_f1": round(mechanism["support_f1"], 6),
            "rate_curve_score": round(mechanism["rate_curve_score"], 6),
            "mechanism_score": round(mechanism["mechanism_score"], 6),
            "interpolation_prediction_score": round(interpolation, 6),
            "extrapolation_prediction_score": round(extrapolation, 6),
            "confidence_calibration_score": round(
                1.0 - (confidence - target_confidence) ** 2, 6
            ),
            "correct_refusal": mechanism["correct_refusal"],
            "false_discovery": mechanism["false_discovery"],
            "abstained": abstain,
            "confidence": round(confidence, 6),
            "n_true_reactions": int(np.sum(world["support"])),
            "n_predicted_reactions": int(np.sum(support)),
            "experiment_calls": laboratory.calls,
            "experiment_budget_units": laboratory.used,
        }
    except Exception as exc:
        return {
            "split": split,
            "world_index": int(index),
            "kind": world["kind"],
            "valid": False,
            "reason": "%s: %s" % (type(exc).__name__, exc),
            "support_f1": 0.0,
            "rate_curve_score": 0.0,
            "mechanism_score": 0.0,
            "interpolation_prediction_score": 0.0,
            "extrapolation_prediction_score": 0.0,
            "confidence_calibration_score": 0.0,
            "correct_refusal": False,
            "false_discovery": False,
            "n_true_reactions": int(np.sum(world["support"])),
            "n_predicted_reactions": 0,
            "experiment_calls": laboratory.calls,
            "experiment_budget_units": laboratory.used,
        }


def _split_summary(records, exception_count):
    raw_mechanism = float(np.mean([row["mechanism_score"] for row in records]))
    always_abstain = exception_count / len(records)
    normalized = float(np.clip(
        (raw_mechanism - always_abstain) / (1.0 - always_abstain), 0.0, 1.0
    ))
    supported = [row for row in records if row["kind"] == "in_library"]
    unsupported = [row for row in records if row["kind"] != "in_library"]
    misspecified = [row for row in records if row["kind"] == "misspecified"]
    null = [row for row in records if row["kind"] == "null"]
    return {
        "normalized_mechanism": normalized,
        "raw_mechanism": raw_mechanism,
        "support_f1": float(np.mean([row["support_f1"] for row in supported])),
        "rate_curve": float(np.mean([
            row["rate_curve_score"] for row in supported
        ])),
        "interpolation_prediction": float(np.mean([
            row["interpolation_prediction_score"] for row in supported
        ])),
        "extrapolation_prediction": float(np.mean([
            row["extrapolation_prediction_score"] for row in supported
        ])),
        "misspecified_interpolation_prediction": float(np.mean([
            row["interpolation_prediction_score"] for row in misspecified
        ])),
        "misspecified_extrapolation_prediction": float(np.mean([
            row["extrapolation_prediction_score"] for row in misspecified
        ])),
        "null_prediction": float(np.mean([
            row["interpolation_prediction_score"] for row in null
        ])),
        "confidence_calibration": float(np.mean([
            row["confidence_calibration_score"] for row in records
        ])),
        "false_discovery_rate": float(np.mean([
            row["false_discovery"] for row in unsupported
        ])),
        "correct_refusal_rate": float(np.mean([
            row["correct_refusal"] for row in unsupported
        ])),
        "valid_count": sum(bool(row["valid"]) for row in records),
    }


def evaluate(discover_mechanism):
    development = [
        _evaluate_world(discover_mechanism, spec, "development", index)
        for index, spec in enumerate(DEVELOPMENT_SPECS)
    ]
    heldout = [
        _evaluate_world(discover_mechanism, spec, "heldout", index)
        for index, spec in enumerate(HELDOUT_SPECS)
    ]
    dev = _split_summary(
        development,
        sum(spec[3] != "in_library" for spec in DEVELOPMENT_SPECS),
    )
    hold = _split_summary(
        heldout, sum(spec[3] != "in_library" for spec in HELDOUT_SPECS)
    )
    all_records = development + heldout
    dev_all_valid = dev["valid_count"] == len(development)
    hold_all_valid = hold["valid_count"] == len(heldout)
    return {
        "combined_score": dev["normalized_mechanism"] if dev_all_valid else 0.0,
        "valid": 1.0 if dev_all_valid else 0.0,
        "feasibility_rate": dev["valid_count"] / len(development),
        "mechanism_score": dev["raw_mechanism"],
        "development_support_f1": dev["support_f1"],
        "development_rate_curve_score": dev["rate_curve"],
        "development_prediction_score": dev["interpolation_prediction"],
        "development_extrapolation_score": dev["extrapolation_prediction"],
        "development_misspecified_prediction_score": (
            dev["misspecified_interpolation_prediction"]
        ),
        "development_misspecified_extrapolation_score": (
            dev["misspecified_extrapolation_prediction"]
        ),
        "development_null_prediction_score": dev["null_prediction"],
        "development_confidence_calibration_score": dev["confidence_calibration"],
        "development_false_discovery_rate": dev["false_discovery_rate"],
        "development_correct_refusal_rate": dev["correct_refusal_rate"],
        "robustness_score": (
            hold["normalized_mechanism"] if hold_all_valid else 0.0
        ),
        "heldout_mechanism_score": hold["raw_mechanism"],
        "heldout_support_f1": hold["support_f1"],
        "heldout_rate_curve_score": hold["rate_curve"],
        "heldout_prediction_score": hold["interpolation_prediction"],
        "heldout_extrapolation_score": hold["extrapolation_prediction"],
        "heldout_misspecified_prediction_score": (
            hold["misspecified_interpolation_prediction"]
        ),
        "heldout_misspecified_extrapolation_score": (
            hold["misspecified_extrapolation_prediction"]
        ),
        "heldout_null_prediction_score": hold["null_prediction"],
        "heldout_confidence_calibration_score": hold["confidence_calibration"],
        "heldout_false_discovery_rate": hold["false_discovery_rate"],
        "heldout_correct_refusal_rate": hold["correct_refusal_rate"],
        "heldout_feasibility_rate": hold["valid_count"] / len(heldout),
        "mean_experiment_calls": float(np.mean([
            row["experiment_calls"] for row in all_records
        ])),
        "mean_experiment_budget_units": float(np.mean([
            row["experiment_budget_units"] for row in all_records
        ])),
        "per_world": all_records,
    }
