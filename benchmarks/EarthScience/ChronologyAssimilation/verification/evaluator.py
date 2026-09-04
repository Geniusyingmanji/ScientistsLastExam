"""Deterministic active pseudoproxy chronology-assimilation oracle."""

from __future__ import annotations

import hashlib
import math

import numpy as np
import xarray as xr

DIFFICULTY = 1

_DIFFICULTY_LADDER = {
    1: {"offset_bound_years": 150.0, "proxy_noise_multiplier": 1.00,
        "date_noise_multiplier": 1.00},
    2: {"offset_bound_years": 190.0, "proxy_noise_multiplier": 1.18,
        "date_noise_multiplier": 1.25},
    3: {"offset_bound_years": 230.0, "proxy_noise_multiplier": 1.38,
        "date_noise_multiplier": 1.55},
}

TIME_GRID = np.linspace(0.0, 2000.0, 81)
N_PROXY = 8
N_SAMPLE = 36
BUDGET_UNITS = 16
PROXY_TYPES = ("tree", "coral", "sediment", "ice")

DEVELOPMENT_SPECS = (
    (83011, "supported", 0), (83023, "supported", 1),
    (83047, "supported", 2), (83059, "supported", 3),
    (83071, "null", 0), (83077, "misspecified", 1),
)
HELDOUT_SPECS = (
    (93001, "supported", 4), (93019, "supported", 5),
    (93031, "supported", 6), (93047, "null", 0),
    (93059, "misspecified", 2),
)


def _difficulty_profile(level=None):
    level = DIFFICULTY if level is None else int(level)
    if level not in _DIFFICULTY_LADDER:
        raise ValueError("difficulty %d has no measured profile" % level)
    return _DIFFICULTY_LADDER[level]


def _climate(seed, variant):
    rng = np.random.default_rng(int(seed))
    phase = rng.uniform(0.0, 2.0 * np.pi)
    signal = (0.75 * np.sin(2.0 * np.pi * TIME_GRID / (620.0 + 25 * variant) + phase)
              + 0.35 * np.sin(2.0 * np.pi * TIME_GRID / 190.0 - 0.5 * phase)
              + 0.00045 * (TIME_GRID - 1000.0))
    innovations = rng.normal(0.0, 0.10, len(TIME_GRID))
    red = np.zeros_like(innovations)
    for index in range(1, len(red)):
        red[index] = 0.82 * red[index - 1] + innovations[index]
    return signal + red


def _world(spec):
    seed, kind, variant = spec
    rng = np.random.default_rng(int(seed) + 19)
    profile = _difficulty_profile()
    climate = _climate(seed, variant)
    offset_bound = profile["offset_bound_years"]
    offsets = rng.uniform(-offset_bound, offset_bound, N_PROXY)
    catalog = []
    true_ages = []
    for proxy_index in range(N_PROXY):
        nominal = np.linspace(30.0, 1970.0, N_SAMPLE)
        nominal += rng.normal(0.0, 8.0, N_SAMPLE)
        nominal.sort()
        actual = np.clip(nominal + offsets[proxy_index], 0.0, 2000.0)
        sensitivity = 0.65 + 0.12 * (proxy_index % 4)
        noise = ((0.16 + 0.025 * (proxy_index % 3))
                 * profile["proxy_noise_multiplier"])
        if kind == "null":
            values = rng.normal(0.0, 0.75, N_SAMPLE)
        else:
            temperature = np.interp(actual, TIME_GRID, climate)
            if kind == "misspecified":
                values = sensitivity * (temperature + 0.55 * temperature ** 2
                                          + 0.45 * np.sin(actual / 75.0))
            else:
                values = sensitivity * temperature
            values += rng.normal(0.0, noise, N_SAMPLE)
        catalog.append({
            "proxy_index": proxy_index, "proxy_type": PROXY_TYPES[proxy_index % 4],
            "nominal_age_years": nominal, "values": values, "noise_std": noise,
            "sensitivity": sensitivity, "site_weight": 0.8 + 0.05 * proxy_index,
        })
        true_ages.append(actual)
    return {"seed": seed, "kind": kind, "variant": variant, "climate": climate,
            "offsets": offsets, "catalog": catalog, "true_ages": true_ages,
            "date_noise": ((12.0 + 2.0 * (variant % 3))
                           * profile["date_noise_multiplier"])}


class _DatingLab:
    def __init__(self, world):
        self.world = world
        self.used = 0
        self.calls = 0
        self.violated = False

    def date_sample(self, proxy_index, sample_indices):
        try:
            proxy = int(proxy_index)
        except Exception as exc:
            self.violated = True
            raise ValueError("proxy_index must be integer") from exc
        indices = np.asarray(sample_indices)
        if proxy < 0 or proxy >= N_PROXY or indices.ndim != 1 or not 1 <= len(indices) <= 10:
            self.violated = True
            raise ValueError("invalid proxy or sample index vector")
        if np.any(indices != indices.astype(int)):
            self.violated = True
            raise ValueError("sample indices must be integers")
        indices = indices.astype(int)
        if len(np.unique(indices)) != len(indices) or np.any(indices < 0) or np.any(indices >= N_SAMPLE):
            self.violated = True
            raise ValueError("sample indices must be unique and in range")
        cost = 1 + int(math.ceil(len(indices) / 5.0))
        if self.used + cost > BUDGET_UNITS:
            self.violated = True
            raise RuntimeError("dating budget exceeded")
        self.used += cost
        self.calls += 1
        payload = np.asarray(indices, dtype="<i8").tobytes()
        digest = int.from_bytes(hashlib.sha256(payload).digest()[:4], "little")
        rng = np.random.default_rng(self.world["seed"] + 1009 * proxy + digest + self.calls)
        sigma = self.world["date_noise"]
        dated = self.world["true_ages"][proxy][indices] + rng.normal(0.0, sigma, len(indices))
        return {"proxy_index": proxy, "sample_indices": indices,
                "dated_age_years": dated, "date_noise_std_years": sigma,
                "budget_cost": cost}


def _public_catalog(world):
    output = []
    for row in world["catalog"]:
        output.append({key: (value.copy() if isinstance(value, np.ndarray) else value)
                       for key, value in row.items()})
    return output


def _validate(submission):
    if not isinstance(submission, dict):
        raise ValueError("submission must be a mapping")
    if not isinstance(submission.get("abstain"), (bool, np.bool_)):
        raise ValueError("abstain must be boolean")
    confidence = float(submission.get("confidence"))
    if not math.isfinite(confidence) or not 0.0 <= confidence <= 1.0:
        raise ValueError("confidence must be in [0,1]")
    abstain = bool(submission["abstain"])
    mean = np.asarray(submission.get("temperature_mean"), dtype=float)
    std = np.asarray(submission.get("temperature_std"), dtype=float)
    offsets = np.asarray(submission.get("age_offsets_years"), dtype=float)
    if abstain:
        if mean.size or std.size or offsets.size:
            raise ValueError("abstention requires empty reconstruction arrays")
        return None, None, None, confidence, True
    if mean.shape != TIME_GRID.shape or std.shape != TIME_GRID.shape or offsets.shape != (N_PROXY,):
        raise ValueError("reconstruction arrays have the wrong shape")
    if np.any(~np.isfinite(mean)) or np.any(~np.isfinite(std)) or np.any(std <= 0.0) or np.any(~np.isfinite(offsets)):
        raise ValueError("reconstruction arrays must be finite and uncertainty positive")
    if np.any(np.abs(offsets) > 300.0):
        raise ValueError("age offsets must lie in [-300,300] years")
    return mean, std, offsets, confidence, False


def _crps_normal(mean, std, truth):
    z = (truth - mean) / std
    phi = np.exp(-0.5 * z * z) / math.sqrt(2.0 * math.pi)
    cdf = 0.5 * (1.0 + np.asarray([
        math.erf(float(value) / math.sqrt(2.0)) for value in np.ravel(z)
    ]).reshape(np.shape(z)))
    return std * (z * (2.0 * cdf - 1.0) + 2.0 * phi - 1.0 / math.sqrt(math.pi))


def _climate_field_metrics(mean, truth):
    """Coordinate-aligned CE and RMSE through xarray's labeled time-series model."""
    coordinates = {"time_years": TIME_GRID}
    predicted = xr.DataArray(
        np.asarray(mean, dtype=float), dims=("time_years",), coords=coordinates
    )
    observed = xr.DataArray(
        np.asarray(truth, dtype=float), dims=("time_years",), coords=coordinates
    )
    predicted, observed = xr.align(predicted, observed, join="exact")
    residual = predicted - observed
    sse = float((residual ** 2).sum().item())
    anomalies = observed - observed.mean("time_years")
    sst = float((anomalies ** 2).sum().item())
    rmse = float(np.sqrt((residual ** 2).mean("time_years").item()))
    return 1.0 - sse / max(sst, 1e-12), rmse


def _empty(split, index):
    return {"split": split, "world_index": index, "valid": False, "abstained": False,
            "mechanism_score": 0.0, "coefficient_efficiency": -1e6, "rmse_c": 1e6,
            "age_mae_years": 1e6, "mean_crps_c": 1e6, "confidence_score": 0.0,
            "false_discovery": False, "correct_refusal": False, "dating_cost": 0}


def _evaluate_world(candidate, spec, split, index):
    row = _empty(split, index)
    world = _world(spec)
    lab = _DatingLab(world)
    try:
        submission = candidate(TIME_GRID.copy(), _public_catalog(world), lab.date_sample, BUDGET_UNITS)
        mean, std, offsets, confidence, abstain = _validate(submission)
        if lab.violated:
            raise ValueError("dating contract violated")
        supported = world["kind"] == "supported"
        if supported and not abstain:
            truth = world["climate"]
            ce, rmse = _climate_field_metrics(mean, truth)
            age_mae = float(np.mean(np.abs(offsets - world["offsets"])))
            crps = float(np.mean(_crps_normal(mean, std, truth)))
            ce_score = float(np.clip(ce, 0.0, 1.0))
            age_score = float(math.exp(-age_mae / 65.0))
            crps_score = float(math.exp(-crps / 0.45))
            mechanism = float((max(ce_score, 1e-12) * age_score * crps_score) ** (1.0 / 3.0))
        elif supported:
            mechanism, ce, rmse, age_mae, crps = 0.0, -1e6, 1e6, 1e6, 1e6
        else:
            correct = bool(abstain)
            mechanism = 1.0 if correct else 0.0
            ce, rmse, age_mae, crps = (0.0, 0.0, 0.0, 0.0) if correct else (-1e6, 1e6, 1e6, 1e6)
        target_confidence = 1.0 if supported and not abstain else 0.0
        row.update({"valid": True, "abstained": abstain, "mechanism_score": mechanism,
                    "coefficient_efficiency": ce, "rmse_c": rmse,
                    "age_mae_years": age_mae, "mean_crps_c": crps,
                    "confidence_score": 1.0 - (confidence - target_confidence) ** 2,
                    "false_discovery": bool(not supported and not abstain),
                    "correct_refusal": bool(not supported and abstain),
                    "dating_cost": lab.used})
    except Exception:
        pass
    return row


def _summary(rows, specs):
    supported = [r for r, s in zip(rows, specs) if s[1] == "supported"]
    unsupported = [r for r, s in zip(rows, specs) if s[1] != "supported"]
    raw = float(np.mean([r["mechanism_score"] for r in rows]))
    abstain_base = len(unsupported) / len(rows)
    return {"normalized": float(np.clip((raw - abstain_base) / (1.0 - abstain_base), 0.0, 1.0)),
            "raw": raw, "valid_count": sum(r["valid"] for r in rows),
            "ce": float(np.mean([r["coefficient_efficiency"] for r in supported])),
            "rmse": float(np.mean([r["rmse_c"] for r in supported])),
            "age_mae": float(np.mean([r["age_mae_years"] for r in supported])),
            "crps": float(np.mean([r["mean_crps_c"] for r in supported])),
            "confidence": float(np.mean([r["confidence_score"] for r in rows])),
            "false_count": sum(r["false_discovery"] for r in unsupported),
            "refusal_count": sum(r["correct_refusal"] for r in unsupported),
            "attempt_count": sum(not r["abstained"] for r in supported),
            "supported_count": len(supported), "unsupported_count": len(unsupported)}


def evaluate(reconstruct_climate):
    development = [_evaluate_world(reconstruct_climate, spec, "development", i)
                   for i, spec in enumerate(DEVELOPMENT_SPECS)]
    heldout = [_evaluate_world(reconstruct_climate, spec, "heldout", i)
               for i, spec in enumerate(HELDOUT_SPECS)]
    dev, hold = _summary(development, DEVELOPMENT_SPECS), _summary(heldout, HELDOUT_SPECS)
    dev_valid = dev["valid_count"] == len(development)
    hold_valid = hold["valid_count"] == len(heldout)
    return {
        "combined_score": dev["normalized"] if dev_valid else 0.0,
        "valid": 1.0 if dev_valid else 0.0,
        "feasibility_rate": dev["valid_count"] / len(development),
        "mechanism_score": dev["raw"],
        "development_coefficient_efficiency": dev["ce"],
        "development_rmse_c": dev["rmse"],
        "development_age_mae_years": dev["age_mae"],
        "development_mean_crps_c": dev["crps"],
        "development_confidence_calibration_score": dev["confidence"],
        "development_false_discovery_rate": dev["false_count"] / dev["unsupported_count"],
        "development_correct_refusal_rate": dev["refusal_count"] / dev["unsupported_count"],
        "development_discovery_coverage": dev["attempt_count"] / dev["supported_count"],
        "supported_world_count": dev["supported_count"], "unsupported_world_count": dev["unsupported_count"],
        "discovery_attempt_count": dev["attempt_count"], "false_discovery_count": dev["false_count"],
        "correct_refusal_count": dev["refusal_count"],
        "robustness_score": hold["normalized"] if hold_valid else 0.0,
        "heldout_feasibility_rate": hold["valid_count"] / len(heldout),
        "heldout_coefficient_efficiency": hold["ce"],
        "heldout_rmse_c": hold["rmse"], "heldout_age_mae_years": hold["age_mae"],
        "heldout_mean_crps_c": hold["crps"],
        "heldout_false_discovery_rate": hold["false_count"] / hold["unsupported_count"],
        "heldout_correct_refusal_rate": hold["refusal_count"] / hold["unsupported_count"],
        "heldout_discovery_coverage": hold["attempt_count"] / hold["supported_count"],
        "per_world": development + heldout,
    }
