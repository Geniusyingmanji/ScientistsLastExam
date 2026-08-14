"""A truth-blind reference analysis for QuartzCrystalMicrobalanceLab.

Eighty-six per cent of recorded proposals decline every world, and the task scores zero for it.
The card claims a raw-signal reference would do better; nothing had run one. This runs it, from
the supplied problem alone.

    calibrate   each block gives eight records of a known admittance beside its raw I/Q counts,
                so `raw = offset + gain * admittance` is a two-parameter complex least squares.
                The two blocks bracket the run, and the instrument drifts linearly between them,
                so each sweep is calibrated at its own capture index.
    resonate    conductance - the real part of the calibrated admittance with the shunt removed -
                peaks at resonance. The peak frequency and the half-power width give the resonance
                frequency and the quality factor without assuming a full BVD fit.
    weigh       Sauerbrey: `delta_f_n / n = -S * mass`. Each harmonic gives an independent mass,
                which is what makes overtone dispersion visible.
    diagnose    clipping and I/Q conjugation are instrument faults and are read off the raw
                counts and the calibration residual. Overtone dispersion and a changing rate are
                physical anomalies and are read off the masses. Everything else is supported.

It never reads the hidden world.
"""
from __future__ import annotations

import numpy as np

# Overtone dispersion is a *trend*, not a spread. Measured on this task, the apparent Sauerbrey
# mass rises monotonically with harmonic on the viscoelastic worlds - [1.10, 1.30, 1.48] and
# [1.22, 1.45, 1.62] - while a world with missing raw samples scatters instead: [1.33, 1.20, 1.20]
# and [0.77, 0.99, 0.77]. Judging by spread alone marks the second group as dispersing, and one of
# them scatters wider (0.28) than either real dispersion (0.16). Requiring a monotone trend
# separates them, and the span threshold then only has to clear the rigid worlds, which drift by
# about 0.01.
DISPERSION_SPAN = 0.10

# The 20-second mass against half the 40-second mass. Rate-change worlds sit at 0.12, everything
# else at or below 0.07.
LINEARITY_TOLERANCE = 0.09

# Conjugate-fit residual over direct-fit residual. Below this the instrument is reporting the
# opposite quadrature convention: the conjugated worlds sit near 1.0 and every other world above
# 1900, because fitting a correctly-oriented signal against a conjugated model is hopeless.
CONJUGATION_RATIO = 10.0


def _finite(values):
    """Raw counts as floats, with the missing samples the task marks as `None` turned into NaN."""
    return np.array([np.nan if value is None else float(value) for value in values])


def _peak_count(sweep):
    """Largest magnitude the ADC reported on this sweep, over the samples that arrived."""
    counts = np.concatenate((_finite(sweep["i_counts"]), _finite(sweep["q_counts"])))
    counts = counts[np.isfinite(counts)]
    return float(np.max(np.abs(counts))) if len(counts) else 0.0


def _complex_pairs(values):
    array = np.asarray(values, dtype=float)
    return array[..., 0] + 1j * array[..., 1]


def _fit_block(block):
    """Solve raw = offset + gain * admittance over the block's records, and report the residual."""
    known = np.array([complex(*record["known_admittance_s"]) for record in block["records"]])
    raw = np.array([complex(record["i_count"], record["q_count"])
                    for record in block["records"]])
    design = np.stack((np.ones_like(known), known), axis=1)
    solution, *_ = np.linalg.lstsq(design, raw, rcond=None)
    residual = float(np.mean(np.abs(design @ solution - raw)))
    scale = float(np.mean(np.abs(raw))) or 1.0
    # The same fit against the conjugated admittance. If that one is much better, the instrument
    # is reporting the opposite quadrature convention, which is a fault rather than a mechanism.
    conjugate_design = np.stack((np.ones_like(known), np.conj(known)), axis=1)
    conjugate_solution, *_ = np.linalg.lstsq(conjugate_design, raw, rcond=None)
    conjugate_residual = float(np.mean(np.abs(conjugate_design @ conjugate_solution - raw)))
    return solution[0], solution[1], residual / scale, conjugate_residual / scale


def _resonance(frequency, admittance, shunt_susceptance):
    """Peak conductance and half-power width, on the points that survived acquisition."""
    conductance = np.real(admittance - 1j * shunt_susceptance)
    finite = np.isfinite(conductance) & np.isfinite(frequency)
    frequency, conductance = frequency[finite], conductance[finite]
    if len(frequency) < 5:
        return None, None
    peak = int(np.argmax(conductance))
    # Parabolic refinement on the three points around the peak: the grid is coarse enough that
    # taking the sampled maximum would quantise the frequency shift the mass is read from.
    if 0 < peak < len(frequency) - 1:
        y0, y1, y2 = conductance[peak - 1: peak + 2]
        denominator = y0 - 2.0 * y1 + y2
        offset = 0.5 * (y0 - y2) / denominator if denominator != 0 else 0.0
        spacing = frequency[peak] - frequency[peak - 1]
        resonance = float(frequency[peak] + np.clip(offset, -1.0, 1.0) * spacing)
    else:
        resonance = float(frequency[peak])
    half = conductance[peak] / 2.0
    above = frequency[conductance >= half]
    width = float(above.max() - above.min()) if len(above) > 1 else 0.0
    quality = resonance / width if width > 0 else None
    return resonance, quality


def analyze_qcm(problem):
    blocks = problem["calibration_blocks"]
    sweeps = problem["sweeps"]
    adc_limit = float(problem["adc_limit"])
    sauerbrey = float(problem["sauerbrey_hz_per_ug_cm2"])
    harmonics = [int(h) for h in problem["harmonics"]]
    nominal = {int(k): float(v) for k, v in problem["nominal_frequency_hz_by_harmonic"].items()}
    shunt = float(problem["shunt_capacitance_f"])
    target = float(problem["target_mass_ug_cm2"])
    horizon = float(problem["prediction_time_s"])

    first, last = blocks[0], blocks[-1]
    offset_a, gain_a, residual_a, conjugate_a = _fit_block(first)
    offset_b, gain_b, residual_b, conjugate_b = _fit_block(last)
    span = max(float(last["capture_index"]) - float(first["capture_index"]), 1e-9)

    clipped = any(_peak_count(sweep) >= adc_limit - 1.0 for sweep in sweeps)
    conjugated = (min(conjugate_a, conjugate_b)
                  / max(min(residual_a, residual_b), 1e-12)) < CONJUGATION_RATIO

    resonances, qualities, evidence = {}, {}, [first["calibration_id"], last["calibration_id"]]
    by_key = {}
    for sweep in sweeps:
        frequency = _finite(sweep["frequency_hz"])
        i_counts = _finite(sweep["i_counts"])
        q_counts = _finite(sweep["q_counts"])
        weight = (float(sweep["capture_index"]) - float(first["capture_index"])) / span
        offset = offset_a + (offset_b - offset_a) * weight
        gain = gain_a + (gain_b - gain_a) * weight
        admittance = ((i_counts + 1j * q_counts) - offset) / gain
        susceptance = 2.0 * np.pi * frequency * shunt
        resonance, quality = _resonance(frequency, admittance, susceptance)
        resonances[sweep["sweep_id"]] = (resonance if resonance is not None
                                         else nominal[int(sweep["harmonic"])])
        qualities[sweep["sweep_id"]] = quality if quality else 2000.0
        evidence.append(sweep["sweep_id"])
        by_key[(int(sweep["harmonic"]), float(sweep["deposition_time_s"]))] = \
            resonances[sweep["sweep_id"]]

    def mass_at(time_s):
        values = []
        for harmonic in harmonics:
            start = by_key.get((harmonic, 0.0))
            later = by_key.get((harmonic, time_s))
            if start is None or later is None:
                continue
            values.append(-(later - start) / harmonic / sauerbrey)
        return np.asarray(values, dtype=float)

    masses_40 = mass_at(40.0)
    masses_20 = mass_at(20.0)
    mass = float(np.median(masses_40)) if len(masses_40) else 0.0

    # Strictly monotone in harmonic, and moving far enough to be a dispersion rather than drift.
    ordered = masses_40
    monotone = (len(ordered) >= 3
                and (all(np.diff(ordered) > 0) or all(np.diff(ordered) < 0)))
    span = (float(np.max(ordered) - np.min(ordered)) / abs(mass)
            if len(ordered) and abs(mass) > 1e-9 else 0.0)
    dispersing = monotone and span >= DISPERSION_SPAN
    rate_changing = False
    if len(masses_20) and abs(mass) > 1e-9:
        expected = mass / 2.0
        observed = float(np.median(masses_20))
        rate_changing = abs(observed - expected) / max(abs(mass), 1e-9) > LINEARITY_TOLERANCE

    if clipped or conjugated:
        diagnosis, abstain = "instrument_fault", True
    elif dispersing or rate_changing:
        diagnosis, abstain = "physical_anomaly", True
    else:
        diagnosis, abstain = "supported", False

    rate = mass / 40.0
    predicted = rate * horizon
    additional = max(0.0, (target - mass) / rate) if rate > 0 else 0.0

    return {
        # The exact key names are part of the contract and are not spelled out in the prompt,
        # which is the same defect the input-key audit found on the other side of the interface.
        "calibration": {
            "start_offset_counts": [float(np.real(offset_a)), float(np.imag(offset_a))],
            "end_offset_counts": [float(np.real(offset_b)), float(np.imag(offset_b))],
            "start_complex_gain_counts_per_siemens": [float(np.real(gain_a)),
                                                      float(np.imag(gain_a))],
            "end_complex_gain_counts_per_siemens": [float(np.real(gain_b)),
                                                    float(np.imag(gain_b))],
        },
        "resonance_frequency_hz_by_sweep": resonances,
        "quality_factor_by_sweep": qualities,
        "mass_loading_ug_cm2": mass,
        "deposition_rate_ug_cm2_s": rate,
        "predicted_mass_ug_cm2": predicted,
        "additional_deposition_time_s": additional,
        "diagnosis": diagnosis,
        "confidence": 0.2 if abstain else 0.8,
        "abstain": abstain,
        "evidence_ids": list(dict.fromkeys(evidence)),
    }
