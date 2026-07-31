"""Raw-signal quartz-crystal-microbalance laboratory, version 1.

Candidates receive quantized I/Q calibration records and admittance sweeps.  A
supported world contains a rigid, linearly deposited film governed by the
public Butterworth--Van Dyke and Sauerbrey models.  Physical model mismatch or
an instrument fault must be refused.  This deterministic reduced-order task is
not a physical QCM experiment or autonomous materials discovery evidence.
"""

from __future__ import annotations

import hashlib
import math

import numpy as np
from scipy.optimize import least_squares


QCM_RAW_PIPELINE_V1 = True

HARMONICS = (1, 3, 5)
DEPOSITION_TIMES_S = (0.0, 20.0, 40.0)
PREDICTION_TIME_S = 60.0
ADC_LIMIT = 32767
SAUERBREY_HZ_PER_UG_CM2 = 56.6
NOMINAL_FUNDAMENTAL_HZ = 5_000_000.0
SHUNT_CAPACITANCE_F = 5.0e-12

MASS_BOUNDS = (0.0, 4.0)
RATE_BOUNDS = (0.0, 0.08)
ADDITIONAL_TIME_BOUNDS = (0.0, 90.0)
QUALITY_FACTOR_BOUNDS = (2000.0, 100000.0)

DEVELOPMENT_SPECS = (
    (31801, "rigid_linear", 2.2),
    (31813, "rigid_missing", 2.8),
    (31827, "rigid_linear", 3.2),
    (31837, "viscoelastic", 2.5),
    (31849, "rate_change", 2.6),
    (31859, "iq_conjugated", 2.4),
)
HELDOUT_SPECS = (
    (41809, "rigid_missing", 3.3),
    (41821, "rigid_linear", 3.6),
    (41833, "viscoelastic", 3.0),
    (41843, "clipped", 2.8),
)

SUPPORTED_KINDS = {"rigid_linear", "rigid_missing"}
PHYSICAL_ANOMALY_KINDS = {"viscoelastic", "rate_change"}
INSTRUMENT_FAULT_KINDS = {"iq_conjugated", "clipped"}
DIAGNOSES = {
    "supported", "physical_anomaly", "instrument_fault", "undetermined"
}

SUBMISSION_KEYS = {
    "calibration",
    "resonance_frequency_hz_by_sweep",
    "quality_factor_by_sweep",
    "mass_loading_ug_cm2",
    "deposition_rate_ug_cm2_s",
    "predicted_mass_ug_cm2",
    "additional_deposition_time_s",
    "diagnosis",
    "confidence",
    "abstain",
    "evidence_ids",
}
CALIBRATION_KEYS = {
    "start_offset_counts",
    "end_offset_counts",
    "start_complex_gain_counts_per_siemens",
    "end_complex_gain_counts_per_siemens",
}


def _token(prefix, *values):
    payload = "|".join(str(value) for value in values).encode("utf-8")
    return prefix + hashlib.sha256(payload).hexdigest()[:16]


def _finite_scalar(value, name):
    if isinstance(value, (bool, np.bool_)) or np.iscomplexobj(value):
        raise ValueError(name + " must be real-valued and non-boolean")
    try:
        scalar = float(value)
    except Exception as exc:
        raise ValueError(name + " must be numeric") from exc
    if not math.isfinite(scalar):
        raise ValueError(name + " must be finite")
    return scalar


def _bounded(value, bounds, name):
    scalar = _finite_scalar(value, name)
    if scalar < bounds[0] or scalar > bounds[1]:
        raise ValueError(name + " outside public bounds")
    return scalar


def _strict_bool(value, name):
    if not isinstance(value, (bool, np.bool_)):
        raise ValueError(name + " must be boolean")
    return bool(value)


def _complex_pair(value, name, component_bound=2.0e6):
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValueError(name + " must be a real/imaginary pair")
    real = _bounded(value[0], (-component_bound, component_bound), name + "[0]")
    imag = _bounded(value[1], (-component_bound, component_bound), name + "[1]")
    return complex(real, imag)


def _quality(estimate, truth, tolerance):
    return float(math.exp(-abs(float(estimate) - float(truth)) / float(tolerance)))


def _complex_quality(estimate, truth, tolerance):
    return float(math.exp(-abs(complex(estimate) - complex(truth)) / float(tolerance)))


def _geometric(values):
    values = [float(np.clip(value, 0.0, 1.0)) for value in values]
    if not values or any(value <= 0.0 for value in values):
        return 0.0
    return float(math.exp(sum(math.log(value) for value in values) / len(values)))


def _noise(seed, key, standard_deviation):
    digest = hashlib.sha256((str(seed) + "|" + str(key)).encode("utf-8")).digest()
    words = np.frombuffer(digest[:16], dtype="<u4")
    child = np.random.SeedSequence([int(value) for value in words]).generate_state(1)[0]
    return float(np.random.default_rng(int(child)).normal(0.0, standard_deviation))


def _make_world(spec):
    seed, kind, noise_counts = int(spec[0]), str(spec[1]), float(spec[2])
    rng = np.random.default_rng(seed)
    base_scale = float(rng.uniform(680000.0, 820000.0))
    start_phase = float(rng.uniform(-0.42, 0.42))
    end_phase = start_phase + float(rng.uniform(-0.10, 0.10))
    start_gain = base_scale * complex(math.cos(start_phase), math.sin(start_phase))
    end_scale = base_scale * float(rng.uniform(0.94, 1.06))
    end_gain = end_scale * complex(math.cos(end_phase), math.sin(end_phase))
    if kind == "clipped":
        start_gain *= 1.72
        end_gain *= 1.78
    world = {
        "seed": seed,
        "kind": kind,
        "noise_counts": noise_counts,
        "fundamental_hz": NOMINAL_FUNDAMENTAL_HZ + float(rng.uniform(-38.0, 38.0)),
        "q0": {
            1: float(rng.uniform(28500.0, 35000.0)),
            3: float(rng.uniform(22500.0, 29000.0)),
            5: float(rng.uniform(17500.0, 23500.0)),
        },
        "motional_capacitance": {
            1: float(rng.uniform(27.0e-15, 34.0e-15)),
            3: float(rng.uniform(8.0e-15, 11.0e-15)),
            5: float(rng.uniform(4.8e-15, 7.0e-15)),
        },
        "rate": float(rng.uniform(0.019, 0.031)),
        "rate_after_20": None,
        "target_mass": float(rng.uniform(1.35, 1.75)),
        "start_offset": complex(
            float(rng.uniform(-2200.0, 2200.0)),
            float(rng.uniform(-2200.0, 2200.0)),
        ),
        "end_offset": complex(
            float(rng.uniform(-2200.0, 2200.0)),
            float(rng.uniform(-2200.0, 2200.0)),
        ),
        "start_gain": start_gain,
        "end_gain": end_gain,
        "sealed_rate_scale": float(rng.uniform(0.92, 1.08)),
        "sealed_sauerbrey_scale": float(rng.uniform(0.97, 1.03)),
        "missing_fraction": 0.11 if kind == "rigid_missing" else 0.0,
    }
    world["rate_after_20"] = world["rate"]
    if kind == "rate_change":
        world["rate_after_20"] = world["rate"] * float(
            rng.choice((rng.uniform(0.28, 0.48), rng.uniform(1.65, 1.95)))
        )
    return world


def _mass_at(world, time_s):
    time_s = float(time_s)
    if time_s <= 20.0:
        mass = world["rate"] * time_s
    else:
        mass = (
            world["rate"] * 20.0
            + world["rate_after_20"] * (time_s - 20.0)
        )
    return float(mass)


def _robust_mass_at(world, time_s):
    """Counterfactual physical mass under sealed calibration/rate shifts.

    The supplied sweeps identify mass through the public Sauerbrey coefficient.
    A sealed coefficient scale therefore changes the physical mass and rate that
    correspond to the same observed frequency shifts.  The separate process-rate
    scale applies only after the last observed deposition time.
    """
    time_s = float(time_s)
    last_observed_time = DEPOSITION_TIMES_S[-1]
    sensitivity_scale = world["sealed_sauerbrey_scale"]
    if time_s <= last_observed_time:
        return float(_mass_at(world, time_s) / sensitivity_scale)
    robust_current_mass = _mass_at(world, last_observed_time) / sensitivity_scale
    robust_future_rate = (
        world["rate"] * world["sealed_rate_scale"] / sensitivity_scale
    )
    return float(
        robust_current_mass
        + robust_future_rate * (time_s - last_observed_time)
    )


def _shift_factor(world, harmonic):
    if world["kind"] != "viscoelastic":
        return 1.0
    return {1: 1.0, 3: 1.19, 5: 1.38}[int(harmonic)]


def _q_factor(world, harmonic, mass):
    harmonic = int(harmonic)
    if world["kind"] == "viscoelastic":
        loss = {1: 0.55, 3: 1.10, 5: 1.80}[harmonic]
    else:
        loss = {1: 0.055, 3: 0.070, 5: 0.085}[harmonic]
    return float(world["q0"][harmonic] / (1.0 + loss * float(mass)))


def _resonance_truth(world, harmonic, time_s):
    harmonic = int(harmonic)
    mass = _mass_at(world, time_s)
    frequency = (
        harmonic * world["fundamental_hz"]
        - harmonic * SAUERBREY_HZ_PER_UG_CM2
        * mass * _shift_factor(world, harmonic)
    )
    return float(frequency), _q_factor(world, harmonic, mass)


def _bvd_admittance(frequencies_hz, resonance_hz, quality_factor,
                    motional_capacitance_f, shunt_capacitance_f=SHUNT_CAPACITANCE_F):
    frequencies = np.asarray(frequencies_hz, dtype=float)
    omega = 2.0 * math.pi * frequencies
    omega_s = 2.0 * math.pi * float(resonance_hz)
    capacitance = float(motional_capacitance_f)
    inductance = 1.0 / (omega_s * omega_s * capacitance)
    resistance = omega_s * inductance / float(quality_factor)
    motional = 1.0 / (
        resistance + 1j * (omega * inductance - 1.0 / (omega * capacitance))
    )
    return motional + 1j * omega * float(shunt_capacitance_f)


def _chain_state(world, capture_index):
    weight = float(capture_index) / 10.0
    offset = (1.0 - weight) * world["start_offset"] + weight * world["end_offset"]
    gain = (1.0 - weight) * world["start_gain"] + weight * world["end_gain"]
    return complex(offset), complex(gain)


def _quantize(world, value, key, capture_index):
    offset, gain = _chain_state(world, capture_index)
    transformed = complex(value)
    if world["kind"] == "iq_conjugated" and int(capture_index) >= 6:
        transformed = transformed.conjugate()
    raw = offset + gain * transformed
    real = int(round(raw.real + _noise(world["seed"], str(key) + "|i", world["noise_counts"])))
    imag = int(round(raw.imag + _noise(world["seed"], str(key) + "|q", world["noise_counts"])))
    return (
        int(np.clip(real, -ADC_LIMIT, ADC_LIMIT)),
        int(np.clip(imag, -ADC_LIMIT, ADC_LIMIT)),
    )


def _frequency_grid(harmonic):
    harmonic = int(harmonic)
    half_width = {1: 850.0, 3: 2100.0, 5: 3400.0}[harmonic]
    return np.linspace(
        harmonic * NOMINAL_FUNDAMENTAL_HZ - half_width,
        harmonic * NOMINAL_FUNDAMENTAL_HZ + half_width,
        121,
    )


def _calibration_values():
    return (
        0.0 + 0.0j,
        0.012 + 0.0j,
        -0.012 + 0.0j,
        0.0 + 0.012j,
        0.0 - 0.012j,
        0.009 + 0.009j,
        -0.009 + 0.009j,
        0.009 - 0.009j,
    )


def _public_problem(world):
    calibration_blocks = []
    for label, capture_index in (("start", 0), ("end", 10)):
        calibration_id = _token("CAL-", world["seed"], label)
        records = []
        for index, value in enumerate(_calibration_values()):
            i_count, q_count = _quantize(
                world, value, calibration_id + "|" + str(index), capture_index
            )
            records.append({
                "record_id": _token("CR-", world["seed"], label, index),
                "known_admittance_s": [float(value.real), float(value.imag)],
                "i_count": i_count,
                "q_count": q_count,
            })
        calibration_blocks.append({
            "calibration_id": calibration_id,
            "capture_index": capture_index,
            "records": records,
        })

    sweeps = []
    capture_index = 0
    for time_index, time_s in enumerate(DEPOSITION_TIMES_S):
        for harmonic in HARMONICS:
            capture_index += 1
            sweep_id = _token("SWP-", world["seed"], harmonic, time_index)
            frequencies = _frequency_grid(harmonic)
            resonance, quality = _resonance_truth(world, harmonic, time_s)
            admittance = _bvd_admittance(
                frequencies,
                resonance,
                quality,
                world["motional_capacitance"][harmonic],
            )
            i_counts = []
            q_counts = []
            for point_index, value in enumerate(admittance):
                key = sweep_id + "|" + str(point_index)
                i_count, q_count = _quantize(world, value, key, capture_index)
                missing_digest = hashlib.sha256(
                    (str(world["seed"]) + "|missing|" + key).encode("utf-8")
                ).digest()
                missing_value = int.from_bytes(missing_digest[:4], "little") / 2**32
                if missing_value < world["missing_fraction"]:
                    i_counts.append(None)
                    q_counts.append(None)
                else:
                    i_counts.append(i_count)
                    q_counts.append(q_count)
            sweeps.append({
                "sweep_id": sweep_id,
                "capture_index": capture_index,
                "harmonic": harmonic,
                "deposition_time_s": time_s,
                "frequency_hz": [float(value) for value in frequencies],
                "i_counts": i_counts,
                "q_counts": q_counts,
            })
    return {
        "schema_version": 1,
        "measurement_model": (
            "raw = complex_offset(capture) + complex_gain(capture) * "
            "BVD_admittance + quantization_noise; supported offset/gain drift is "
            "linear between start and end calibrations"
        ),
        "mass_model": (
            "delta_f_n / n = -sauerbrey_hz_per_ug_cm2 * mass_ug_cm2; "
            "supported deposition mass is linear in time"
        ),
        "harmonics": list(HARMONICS),
        "deposition_times_s": list(DEPOSITION_TIMES_S),
        "prediction_time_s": PREDICTION_TIME_S,
        "target_mass_ug_cm2": world["target_mass"],
        "sauerbrey_hz_per_ug_cm2": SAUERBREY_HZ_PER_UG_CM2,
        "nominal_frequency_hz_by_harmonic": {
            str(harmonic): harmonic * NOMINAL_FUNDAMENTAL_HZ
            for harmonic in HARMONICS
        },
        "shunt_capacitance_f": SHUNT_CAPACITANCE_F,
        "motional_capacitance_initial_f_by_harmonic": {
            "1": 30.0e-15,
            "3": 10.0e-15,
            "5": 6.0e-15,
        },
        "quality_factor_bounds": list(QUALITY_FACTOR_BOUNDS),
        "mass_loading_bounds_ug_cm2": list(MASS_BOUNDS),
        "deposition_rate_bounds_ug_cm2_s": list(RATE_BOUNDS),
        "additional_time_bounds_s": list(ADDITIONAL_TIME_BOUNDS),
        "adc_limit": ADC_LIMIT,
        "calibration_blocks": calibration_blocks,
        "sweeps": sweeps,
        "diagnosis_values": sorted(DIAGNOSES),
    }


def _truth_by_sweep(world, problem):
    result = {}
    for sweep in problem["sweeps"]:
        frequency, quality = _resonance_truth(
            world, sweep["harmonic"], sweep["deposition_time_s"]
        )
        result[sweep["sweep_id"]] = {
            "frequency": frequency,
            "quality": quality,
        }
    return result


def _fit_affine(block):
    known = np.asarray([
        complex(*record["known_admittance_s"])
        for record in block["records"]
    ], dtype=complex)
    raw = np.asarray([
        complex(record["i_count"], record["q_count"])
        for record in block["records"]
    ], dtype=complex)
    design = np.column_stack((np.ones(len(known), dtype=complex), known))
    coefficients, _, _, _ = np.linalg.lstsq(design, raw, rcond=None)
    residual = raw - design @ coefficients
    return complex(coefficients[0]), complex(coefficients[1]), float(
        math.sqrt(np.mean(np.abs(residual) ** 2))
    )


def _correct_sweep(sweep, start, end):
    weight = float(sweep["capture_index"]) / 10.0
    offset = (1.0 - weight) * start[0] + weight * end[0]
    gain = (1.0 - weight) * start[1] + weight * end[1]
    frequencies = []
    values = []
    for frequency, i_count, q_count in zip(
        sweep["frequency_hz"], sweep["i_counts"], sweep["q_counts"]
    ):
        if i_count is None or q_count is None:
            continue
        frequencies.append(float(frequency))
        values.append((complex(i_count, q_count) - offset) / gain)
    if len(frequencies) < 45:
        raise ValueError("insufficient uncensored sweep points")
    return np.asarray(frequencies, dtype=float), np.asarray(values, dtype=complex)


def _fit_bvd(frequencies, values, harmonic, problem):
    conductance = np.real(values)
    initial_frequency = float(frequencies[int(np.argmax(conductance))])
    initial_q = 28000.0 / math.sqrt(float(harmonic))
    initial_capacitance = problem[
        "motional_capacitance_initial_f_by_harmonic"
    ][str(harmonic)]
    scale = max(1.0e-8, float(np.max(np.abs(values))))

    def residual(parameters):
        frequency, log_q, log_c = parameters
        predicted = _bvd_admittance(
            frequencies,
            frequency,
            math.exp(log_q),
            math.exp(log_c),
            problem["shunt_capacitance_f"],
        )
        difference = (predicted - values) / scale
        return np.concatenate((np.real(difference), np.imag(difference)))

    result = least_squares(
        residual,
        np.asarray((initial_frequency, math.log(initial_q),
                    math.log(initial_capacitance))),
        bounds=(
            np.asarray((float(np.min(frequencies)), math.log(QUALITY_FACTOR_BOUNDS[0]),
                        math.log(1.0e-16))),
            np.asarray((float(np.max(frequencies)), math.log(QUALITY_FACTOR_BOUNDS[1]),
                        math.log(1.0e-12))),
        ),
        max_nfev=1200,
        xtol=1.0e-12,
        ftol=1.0e-12,
        gtol=1.0e-12,
    )
    rms = float(math.sqrt(np.mean(residual(result.x) ** 2)))
    return float(result.x[0]), float(math.exp(result.x[1])), rms


def _raw_health(problem, start_fit, end_fit):
    counts = []
    missing = 0
    total = 0
    for sweep in problem["sweeps"]:
        for i_count, q_count in zip(sweep["i_counts"], sweep["q_counts"]):
            total += 1
            if i_count is None or q_count is None:
                missing += 1
                continue
            counts.extend((abs(int(i_count)), abs(int(q_count))))
    saturation = sum(value >= ADC_LIMIT for value in counts) / max(len(counts), 1)
    return {
        "calibration_rms_counts": max(start_fit[2], end_fit[2]),
        "saturation_fraction": float(saturation),
        "missing_fraction": float(missing / max(total, 1)),
    }


def _fallback_submission(problem, diagnosis="instrument_fault"):
    resonance = {}
    quality = {}
    nominal = problem["nominal_frequency_hz_by_harmonic"]
    for sweep in problem["sweeps"]:
        resonance[sweep["sweep_id"]] = nominal[str(sweep["harmonic"])]
        quality[sweep["sweep_id"]] = 20000.0
    return {
        "calibration": {
            "start_offset_counts": [0.0, 0.0],
            "end_offset_counts": [0.0, 0.0],
            "start_complex_gain_counts_per_siemens": [700000.0, 0.0],
            "end_complex_gain_counts_per_siemens": [700000.0, 0.0],
        },
        "resonance_frequency_hz_by_sweep": resonance,
        "quality_factor_by_sweep": quality,
        "mass_loading_ug_cm2": 0.0,
        "deposition_rate_ug_cm2_s": 0.0,
        "predicted_mass_ug_cm2": 0.0,
        "additional_deposition_time_s": 0.0,
        "diagnosis": diagnosis,
        "confidence": 0.0,
        "abstain": True,
        "evidence_ids": [
            block["calibration_id"] for block in problem["calibration_blocks"]
        ] + [sweep["sweep_id"] for sweep in problem["sweeps"]],
    }


def _reference_pipeline(problem):
    try:
        start = _fit_affine(problem["calibration_blocks"][0])
        end = _fit_affine(problem["calibration_blocks"][1])
        health = _raw_health(problem, start, end)
        resonance = {}
        quality = {}
        fit_rms = []
        mass_by_time = {time_s: [] for time_s in DEPOSITION_TIMES_S}
        q_loss_by_harmonic = {harmonic: [] for harmonic in HARMONICS}
        reference_frequency = {}
        reference_quality = {}
        for sweep in problem["sweeps"]:
            frequencies, values = _correct_sweep(sweep, start, end)
            fitted_frequency, fitted_q, rms = _fit_bvd(
                frequencies, values, sweep["harmonic"], problem
            )
            resonance[sweep["sweep_id"]] = fitted_frequency
            quality[sweep["sweep_id"]] = fitted_q
            fit_rms.append(rms)
            harmonic = int(sweep["harmonic"])
            time_s = float(sweep["deposition_time_s"])
            if time_s == 0.0:
                reference_frequency[harmonic] = fitted_frequency
                reference_quality[harmonic] = fitted_q
            else:
                mass = (
                    reference_frequency[harmonic] - fitted_frequency
                ) / (harmonic * problem["sauerbrey_hz_per_ug_cm2"])
                mass_by_time[time_s].append(float(mass))
                q_loss_by_harmonic[harmonic].append(
                    max(0.0, reference_quality[harmonic] / fitted_q - 1.0)
                )
        mass20 = float(np.median(mass_by_time[20.0]))
        mass40 = float(np.median(mass_by_time[40.0]))
        early_rate = mass20 / 20.0
        late_rate = (mass40 - mass20) / 20.0
        rate = mass40 / 40.0
        harmonic_masses = np.asarray(mass_by_time[40.0], dtype=float)
        dispersion = float(np.std(harmonic_masses))
        slope_mismatch = abs(late_rate - early_rate) / max(abs(rate), 1.0e-6)
        q_losses = np.asarray([
            values[-1] for values in q_loss_by_harmonic.values()
        ], dtype=float)
        q_loss_spread = float(np.max(q_losses) - np.min(q_losses))
        instrument_fault = bool(
            health["calibration_rms_counts"] > 45.0
            or health["saturation_fraction"] > 0.025
            or max(fit_rms) > 0.018
        )
        physical_anomaly = bool(
            dispersion > 0.075
            or slope_mismatch > 0.28
            or q_loss_spread > 0.22
        )
        if instrument_fault:
            diagnosis = "instrument_fault"
        elif physical_anomaly:
            diagnosis = "physical_anomaly"
        else:
            diagnosis = "supported"
        abstain = diagnosis != "supported"
        predicted_mass = max(0.0, rate * problem["prediction_time_s"])
        additional_time = float(np.clip(
            (problem["target_mass_ug_cm2"] - mass40) / max(rate, 1.0e-8),
            *ADDITIONAL_TIME_BOUNDS,
        ))
        return {
            "calibration": {
                "start_offset_counts": [start[0].real, start[0].imag],
                "end_offset_counts": [end[0].real, end[0].imag],
                "start_complex_gain_counts_per_siemens": [
                    start[1].real, start[1].imag
                ],
                "end_complex_gain_counts_per_siemens": [
                    end[1].real, end[1].imag
                ],
            },
            "resonance_frequency_hz_by_sweep": resonance,
            "quality_factor_by_sweep": quality,
            "mass_loading_ug_cm2": float(np.clip(mass40, *MASS_BOUNDS)),
            "deposition_rate_ug_cm2_s": float(np.clip(rate, *RATE_BOUNDS)),
            "predicted_mass_ug_cm2": float(np.clip(
                predicted_mass, *MASS_BOUNDS
            )),
            "additional_deposition_time_s": additional_time,
            "diagnosis": diagnosis,
            "confidence": 0.90 if not abstain else 0.86,
            "abstain": abstain,
            "evidence_ids": [
                block["calibration_id"] for block in problem["calibration_blocks"]
            ] + [sweep["sweep_id"] for sweep in problem["sweeps"]],
        }
    except Exception:
        return _fallback_submission(problem, diagnosis="instrument_fault")


def _validate_mapping(mapping, sweep_ids, bounds_by_id, name):
    if not isinstance(mapping, dict) or set(mapping) != set(sweep_ids):
        raise ValueError(name + " must contain exactly all sweep IDs")
    result = {}
    for sweep_id in sweep_ids:
        result[sweep_id] = _bounded(
            mapping[sweep_id], bounds_by_id[sweep_id], name + "[" + sweep_id + "]"
        )
    return result


def _validate_submission(submission, problem):
    if not isinstance(submission, dict) or set(submission) != SUBMISSION_KEYS:
        raise ValueError("submission must contain exactly the documented fields")
    calibration = submission["calibration"]
    if not isinstance(calibration, dict) or set(calibration) != CALIBRATION_KEYS:
        raise ValueError("calibration must contain exactly the documented fields")
    parsed_calibration = {
        key: _complex_pair(calibration[key], "calibration." + key)
        for key in CALIBRATION_KEYS
    }
    sweep_ids = [sweep["sweep_id"] for sweep in problem["sweeps"]]
    frequency_bounds = {
        sweep["sweep_id"]: (
            min(sweep["frequency_hz"]), max(sweep["frequency_hz"])
        ) for sweep in problem["sweeps"]
    }
    quality_bounds = {sweep_id: QUALITY_FACTOR_BOUNDS for sweep_id in sweep_ids}
    resonance = _validate_mapping(
        submission["resonance_frequency_hz_by_sweep"], sweep_ids,
        frequency_bounds, "resonance_frequency_hz_by_sweep"
    )
    quality = _validate_mapping(
        submission["quality_factor_by_sweep"], sweep_ids,
        quality_bounds, "quality_factor_by_sweep"
    )
    diagnosis = submission["diagnosis"]
    if not isinstance(diagnosis, str) or diagnosis not in DIAGNOSES:
        raise ValueError("diagnosis is not one of the documented values")
    evidence = submission["evidence_ids"]
    available = {
        block["calibration_id"] for block in problem["calibration_blocks"]
    } | set(sweep_ids)
    if (
        not isinstance(evidence, list)
        or any(not isinstance(value, str) for value in evidence)
        or len(evidence) != len(set(evidence))
        or not set(evidence).issubset(available)
    ):
        raise ValueError("evidence_ids must be unique returned calibration/sweep IDs")
    return {
        "calibration": parsed_calibration,
        "resonance": resonance,
        "quality": quality,
        "mass": _bounded(
            submission["mass_loading_ug_cm2"], MASS_BOUNDS,
            "mass_loading_ug_cm2"
        ),
        "rate": _bounded(
            submission["deposition_rate_ug_cm2_s"], RATE_BOUNDS,
            "deposition_rate_ug_cm2_s"
        ),
        "predicted_mass": _bounded(
            submission["predicted_mass_ug_cm2"], MASS_BOUNDS,
            "predicted_mass_ug_cm2"
        ),
        "additional_time": _bounded(
            submission["additional_deposition_time_s"], ADDITIONAL_TIME_BOUNDS,
            "additional_deposition_time_s"
        ),
        "diagnosis": diagnosis,
        "confidence": _bounded(submission["confidence"], (0.0, 1.0), "confidence"),
        "abstain": _strict_bool(submission["abstain"], "abstain"),
        "evidence": list(evidence),
        "available_evidence": available,
    }


def _expected_diagnosis(world):
    if world["kind"] in SUPPORTED_KINDS:
        return "supported"
    if world["kind"] in PHYSICAL_ANOMALY_KINDS:
        return "physical_anomaly"
    return "instrument_fault"


def _score_values(values, world, problem, truth_by_sweep):
    supported = world["kind"] in SUPPORTED_KINDS
    expected_diagnosis = _expected_diagnosis(world)
    lineage = len(values["evidence"]) / max(len(values["available_evidence"]), 1)
    diagnosis_quality = float(values["diagnosis"] == expected_diagnosis)
    if supported and not values["abstain"]:
        calibration_truth = {
            "start_offset_counts": world["start_offset"],
            "end_offset_counts": world["end_offset"],
            "start_complex_gain_counts_per_siemens": world["start_gain"],
            "end_complex_gain_counts_per_siemens": world["end_gain"],
        }
        calibration_parts = []
        for key, truth in calibration_truth.items():
            tolerance = 55.0 if "offset" in key else 0.018 * abs(truth)
            calibration_parts.append(_complex_quality(
                values["calibration"][key], truth, tolerance
            ))
        calibration_quality = _geometric(calibration_parts)
        frequency_parts = []
        q_parts = []
        for sweep_id, truth in truth_by_sweep.items():
            frequency_parts.append(_quality(
                values["resonance"][sweep_id], truth["frequency"], 8.0
            ))
            q_parts.append(_quality(
                values["quality"][sweep_id], truth["quality"],
                0.035 * truth["quality"]
            ))
        extraction_quality = _geometric((
            _geometric(frequency_parts), _geometric(q_parts)
        ))
        current_mass = _mass_at(world, DEPOSITION_TIMES_S[-1])
        current_rate = world["rate"]
        mechanism_quality = _geometric((
            _quality(values["mass"], current_mass, 0.055),
            _quality(values["rate"], current_rate, 0.0018),
        ))
        future_mass = _mass_at(world, problem["prediction_time_s"])
        prediction_quality = _quality(
            values["predicted_mass"], future_mass, 0.085
        )
        achieved_mass = current_mass + current_rate * values["additional_time"]
        decision_quality = _quality(
            achieved_mass, problem["target_mass_ug_cm2"], 0.12
        )
        robust_future = _robust_mass_at(
            world, problem["prediction_time_s"]
        )
        robust_prediction = _quality(
            values["predicted_mass"], robust_future, 0.11
        )
        robust_current = _robust_mass_at(world, DEPOSITION_TIMES_S[-1])
        robust_rate = (
            current_rate * world["sealed_rate_scale"]
            / world["sealed_sauerbrey_scale"]
        )
        robust_achieved = (
            robust_current + robust_rate * values["additional_time"]
        )
        robust_decision = _quality(
            robust_achieved, problem["target_mass_ug_cm2"], 0.16
        )
        joint = _geometric((
            lineage, calibration_quality, extraction_quality,
            mechanism_quality, prediction_quality, decision_quality,
            diagnosis_quality,
        ))
        robust_joint = _geometric((
            lineage, calibration_quality, extraction_quality,
            mechanism_quality, robust_prediction, robust_decision,
            diagnosis_quality,
        ))
        correct_refusal = False
        false_discovery = False
    elif not supported and values["abstain"]:
        calibration_quality = extraction_quality = mechanism_quality = 1.0
        prediction_quality = decision_quality = 1.0
        robust_prediction = robust_decision = 1.0
        joint = robust_joint = _geometric((lineage, diagnosis_quality))
        correct_refusal = True
        false_discovery = False
    else:
        calibration_quality = extraction_quality = mechanism_quality = 0.0
        prediction_quality = decision_quality = 0.0
        robust_prediction = robust_decision = 0.0
        joint = robust_joint = 0.0
        correct_refusal = False
        false_discovery = bool(not supported and not values["abstain"])
    confidence_score = float(np.clip(
        1.0 - (values["confidence"] - joint) ** 2, 0.0, 1.0
    ))
    return {
        "lineage_quality": float(lineage),
        "calibration_quality": float(calibration_quality),
        "extraction_quality": float(extraction_quality),
        "mechanism_quality": float(mechanism_quality),
        "prediction_quality": float(prediction_quality),
        "decision_quality": float(decision_quality),
        "robust_prediction_quality": float(robust_prediction),
        "robust_decision_quality": float(robust_decision),
        "diagnosis_quality": float(diagnosis_quality),
        "joint_quality": float(joint),
        "robust_joint_quality": float(robust_joint),
        "correct_refusal": bool(correct_refusal),
        "false_discovery": bool(false_discovery),
        "abstained": bool(values["abstain"]),
        "confidence": float(values["confidence"]),
        "confidence_score": confidence_score,
    }


def _raw_diagnostics(problem):
    start = _fit_affine(problem["calibration_blocks"][0])
    end = _fit_affine(problem["calibration_blocks"][1])
    return _raw_health(problem, start, end)


def _invalid_record(split, index, world, problem, failure_kind):
    try:
        reference_submission = _reference_pipeline(problem)
        reference_values = _validate_submission(reference_submission, problem)
        reference_score = _score_values(
            reference_values, world, problem, _truth_by_sweep(world, problem)
        )["joint_quality"]
        health = _raw_diagnostics(problem)
    except Exception:
        reference_score = 0.0
        health = {
            "calibration_rms_counts": 0.0,
            "saturation_fraction": 0.0,
            "missing_fraction": 0.0,
        }
    return {
        "split": str(split),
        "world_index": int(index),
        "kind": str(world["kind"]),
        "valid": False,
        "failure_kind": str(failure_kind),
        "lineage_quality": 0.0,
        "calibration_quality": 0.0,
        "extraction_quality": 0.0,
        "mechanism_quality": 0.0,
        "prediction_quality": 0.0,
        "decision_quality": 0.0,
        "robust_prediction_quality": 0.0,
        "robust_decision_quality": 0.0,
        "diagnosis_quality": 0.0,
        "joint_quality": 0.0,
        "robust_joint_quality": 0.0,
        "correct_refusal": False,
        "false_discovery": False,
        "abstained": False,
        "confidence": 0.0,
        "confidence_score": 0.0,
        "reference_preprocessor_joint_quality": float(reference_score),
        "oracle_clean_joint_quality": 1.0,
        **health,
    }


def _evaluate_world(candidate, spec, split, index):
    world = _make_world(spec)
    problem = _public_problem(world)
    truth_by_sweep = _truth_by_sweep(world, problem)
    stage = "candidate_execution"
    try:
        submission = candidate(problem)
        stage = "submission_validation"
        values = _validate_submission(submission, problem)
        stage = "trusted_scoring"
        scored = _score_values(values, world, problem, truth_by_sweep)
        reference_submission = _reference_pipeline(problem)
        reference_values = _validate_submission(reference_submission, problem)
        reference_scored = _score_values(
            reference_values, world, problem, truth_by_sweep
        )
        health = _raw_diagnostics(problem)
        return {
            "split": str(split),
            "world_index": int(index),
            "kind": str(world["kind"]),
            "valid": True,
            "failure_kind": None,
            **{key: round(value, 6) if isinstance(value, float) else value
               for key, value in scored.items()},
            "reference_preprocessor_joint_quality": round(
                reference_scored["joint_quality"], 6
            ),
            "oracle_clean_joint_quality": 1.0,
            "calibration_rms_counts": round(
                health["calibration_rms_counts"], 6
            ),
            "saturation_fraction": round(health["saturation_fraction"], 6),
            "missing_fraction": round(health["missing_fraction"], 6),
        }
    except Exception:
        failure_kind = (
            "invalid_submission" if stage == "submission_validation"
            else "trusted_scoring_failure" if stage == "trusted_scoring"
            else "candidate_execution_failure"
        )
        return _invalid_record(split, index, world, problem, failure_kind)


def _normalized_mean(records, field):
    unsupported = sum(row["kind"] not in SUPPORTED_KINDS for row in records)
    baseline = unsupported / len(records)
    raw = float(np.mean([float(row[field]) for row in records]))
    return float(np.clip(
        (raw - baseline) / max(1.0e-12, 1.0 - baseline), 0.0, 1.0
    ))


def _split_metrics(records):
    supported = sum(row["kind"] in SUPPORTED_KINDS for row in records)
    unsupported = len(records) - supported
    claims = sum(not row["abstained"] for row in records if row["valid"])
    fields = (
        "joint_quality", "robust_joint_quality", "lineage_quality",
        "calibration_quality", "extraction_quality", "mechanism_quality",
        "prediction_quality", "decision_quality", "robust_prediction_quality",
        "robust_decision_quality", "diagnosis_quality",
        "reference_preprocessor_joint_quality", "oracle_clean_joint_quality",
    )
    result = {
        field: _normalized_mean(records, field) for field in fields
    }
    result.update({
        "valid_rate": float(np.mean([bool(row["valid"]) for row in records])),
        "supported_claim_coverage": sum(
            row["kind"] in SUPPORTED_KINDS and row["valid"] and not row["abstained"]
            for row in records
        ) / supported,
        "unsupported_refusal_rate": sum(row["correct_refusal"] for row in records)
        / unsupported,
        "false_discovery_rate": sum(row["false_discovery"] for row in records)
        / max(claims, 1),
        "fault_diagnosis_accuracy": sum(
            row["kind"] not in SUPPORTED_KINDS
            and row["valid"] and row["diagnosis_quality"] == 1.0
            for row in records
        ) / unsupported,
        "confidence_score": float(np.mean([
            row["confidence_score"] for row in records
        ])),
        "mean_calibration_rms_counts": float(np.mean([
            row["calibration_rms_counts"] for row in records
        ])),
        "mean_saturation_fraction": float(np.mean([
            row["saturation_fraction"] for row in records
        ])),
        "mean_missing_fraction": float(np.mean([
            row["missing_fraction"] for row in records
        ])),
    })
    return result


def evaluate(analyze_qcm):
    development = []
    heldout = []
    rows = [
        ("development", index, spec)
        for index, spec in enumerate(DEVELOPMENT_SPECS)
    ] + [
        ("heldout", index, spec)
        for index, spec in enumerate(HELDOUT_SPECS)
    ]
    for call_index, (split, index, spec) in enumerate(rows):
        if call_index and hasattr(analyze_qcm, "reset_session"):
            analyze_qcm.reset_session()
        record = _evaluate_world(analyze_qcm, spec, split, index)
        (development if split == "development" else heldout).append(record)
    dev = _split_metrics(development)
    held = _split_metrics(heldout)
    development_valid = all(row["valid"] for row in development)
    heldout_valid = all(row["valid"] for row in heldout)
    return {
        "combined_score": dev["joint_quality"] if development_valid else 0.0,
        "valid": float(development_valid),
        "feasibility_rate": dev["valid_rate"],
        "robustness_score": (
            dev["robust_joint_quality"] if development_valid else 0.0
        ),
        "heldout_policy_score": (
            held["joint_quality"] if heldout_valid else 0.0
        ),
        "heldout_robustness_score": (
            held["robust_joint_quality"] if heldout_valid else 0.0
        ),
        "heldout_feasibility_rate": held["valid_rate"],
        "development_lineage_score": dev["lineage_quality"],
        "heldout_lineage_score": held["lineage_quality"],
        "development_calibration_score": dev["calibration_quality"],
        "heldout_calibration_score": held["calibration_quality"],
        "development_extraction_score": dev["extraction_quality"],
        "heldout_extraction_score": held["extraction_quality"],
        "development_mechanism_score": dev["mechanism_quality"],
        "heldout_mechanism_score": held["mechanism_quality"],
        "development_prediction_score": dev["prediction_quality"],
        "heldout_prediction_score": held["prediction_quality"],
        "development_decision_score": dev["decision_quality"],
        "heldout_decision_score": held["decision_quality"],
        "development_robust_prediction_score": dev["robust_prediction_quality"],
        "heldout_robust_prediction_score": held["robust_prediction_quality"],
        "development_robust_decision_score": dev["robust_decision_quality"],
        "heldout_robust_decision_score": held["robust_decision_quality"],
        "development_supported_claim_coverage": dev["supported_claim_coverage"],
        "heldout_supported_claim_coverage": held["supported_claim_coverage"],
        "development_unsupported_refusal_rate": dev["unsupported_refusal_rate"],
        "heldout_unsupported_refusal_rate": held["unsupported_refusal_rate"],
        "development_false_discovery_rate": dev["false_discovery_rate"],
        "heldout_false_discovery_rate": held["false_discovery_rate"],
        "development_fault_diagnosis_accuracy": dev["fault_diagnosis_accuracy"],
        "heldout_fault_diagnosis_accuracy": held["fault_diagnosis_accuracy"],
        "development_confidence_score": dev["confidence_score"],
        "heldout_confidence_score": held["confidence_score"],
        "development_reference_preprocessor_score": dev[
            "reference_preprocessor_joint_quality"
        ],
        "heldout_reference_preprocessor_score": held[
            "reference_preprocessor_joint_quality"
        ],
        "development_oracle_clean_feature_score": dev["oracle_clean_joint_quality"],
        "heldout_oracle_clean_feature_score": held["oracle_clean_joint_quality"],
        "development_mean_calibration_rms_counts": dev[
            "mean_calibration_rms_counts"
        ],
        "heldout_mean_calibration_rms_counts": held[
            "mean_calibration_rms_counts"
        ],
        "development_mean_saturation_fraction": dev["mean_saturation_fraction"],
        "heldout_mean_saturation_fraction": held["mean_saturation_fraction"],
        "development_mean_missing_fraction": dev["mean_missing_fraction"],
        "heldout_mean_missing_fraction": held["mean_missing_fraction"],
        "candidate_instance_call_count": len(rows),
        "candidate_instance_valid_rate": float(np.mean([
            row["valid"] for row in development + heldout
        ])),
        "per_world": development + heldout,
    }


def _reference_agent(problem):
    return _reference_pipeline(problem)


def _truth_agent(problem):
    del problem
    raise RuntimeError("truth agent requires a bound world")


def _evaluate_truth_world(spec, split="development", index=0):
    world = _make_world(spec)
    problem = _public_problem(world)
    truth = _truth_by_sweep(world, problem)

    def bound(public_problem):
        supported = world["kind"] in SUPPORTED_KINDS
        diagnosis = _expected_diagnosis(world)
        return {
            "calibration": {
                "start_offset_counts": [
                    world["start_offset"].real, world["start_offset"].imag
                ],
                "end_offset_counts": [
                    world["end_offset"].real, world["end_offset"].imag
                ],
                "start_complex_gain_counts_per_siemens": [
                    world["start_gain"].real, world["start_gain"].imag
                ],
                "end_complex_gain_counts_per_siemens": [
                    world["end_gain"].real, world["end_gain"].imag
                ],
            },
            "resonance_frequency_hz_by_sweep": {
                sweep_id: values["frequency"] for sweep_id, values in truth.items()
            },
            "quality_factor_by_sweep": {
                sweep_id: values["quality"] for sweep_id, values in truth.items()
            },
            "mass_loading_ug_cm2": _mass_at(world, DEPOSITION_TIMES_S[-1]),
            "deposition_rate_ug_cm2_s": world["rate"],
            "predicted_mass_ug_cm2": min(
                MASS_BOUNDS[1], _mass_at(world, PREDICTION_TIME_S)
            ),
            "additional_deposition_time_s": float(np.clip(
                (world["target_mass"] - _mass_at(world, DEPOSITION_TIMES_S[-1]))
                / max(world["rate"], 1.0e-12),
                *ADDITIONAL_TIME_BOUNDS,
            )),
            "diagnosis": diagnosis,
            "confidence": 1.0,
            "abstain": not supported,
            "evidence_ids": [
                block["calibration_id"]
                for block in public_problem["calibration_blocks"]
            ] + [sweep["sweep_id"] for sweep in public_problem["sweeps"]],
        }

    return _evaluate_world(bound, spec, split, index)
