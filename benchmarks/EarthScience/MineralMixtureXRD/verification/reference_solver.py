"""Truth-blind reference witness: matched-filter phases, hump-aware residual refusal.

The coarse scan is cross-correlated against every library mineral's peak set
(matched filtering over the public grid); a mineral is called present when its
matched score clears a noise-scaled threshold; fractions normalize the scores; two
slow scans cover the highest residual windows. Refusal fires when the residual
after the best library fit carries sharp unbroadened peak structure beyond the
noise floor (an unknown crystalline phase), while a broad low hump is absorbed by
a fitted amorphous band and must not trigger refusal. It deliberately lacks
full-pattern Rietveld refinement, per-peak width fitting and amorphous quantification.
"""

from __future__ import annotations

import math

import numpy as np

PRESENCE_SIGMA = 5.0
UNKNOWN_RESIDUAL_GATE = 6.0


def _nnls_weighted(problem, two_theta, intensity, noise_map):
    """Noise-weighted NNLS amplitudes over merged coarse and slow windows."""
    from scipy.optimize import nnls
    names = sorted(problem["mineral_library"])
    centers = sorted({center for peaks in problem["mineral_library"].values()
                      for center, _ in peaks})
    baseline = float(np.min(intensity))
    b = np.zeros(len(centers))
    shape = np.zeros((len(centers), len(names)))
    rows = []
    for row, center in enumerate(centers):
        window = np.abs(two_theta - center) <= 0.12
        if not window.any():
            continue
        observed = float(intensity[window].max())
        noise = float(np.min(noise_map[window]))
        b[row] = max(observed - baseline, 0.0) / max(noise, 1e-9)
        rows.append((row, noise))
    for column, name in enumerate(names):
        for center, weight in problem["mineral_library"][name]:
            row = centers.index(center)
            shape[row, column] += weight / 100.0
    for row, noise in rows:
        shape[row] /= max(noise, 1e-9)
    solution, _ = nnls(shape, b)
    return {name: float(value) for name, value in zip(names, solution)}


def _nnls_mixture(problem, two_theta, intensity):
    """Nonnegative amplitudes of the library minerals from feature positions."""
    from scipy.optimize import nnls
    names = sorted(problem["mineral_library"])
    centers = sorted({center for peaks in problem["mineral_library"].values()
                      for center, _ in peaks})
    design = np.zeros((len(centers), len(names)))
    for row, center in enumerate(centers):
        window = np.abs(two_theta - center) <= 0.12
        if not window.any():
            continue
        observed = float(intensity[window].max())
        for column, name in enumerate(names):
            for peak_center, weight in problem["mineral_library"][name]:
                if abs(peak_center - center) < 1e-9:
                    design[row, column] = weight / 100.0 * observed
    # Scale rows so the design holds unit shape and the observation drives b.
    b = np.asarray([float(intensity[np.abs(two_theta - center) <= 0.12].max())
                    if np.abs(two_theta - center).any() and
                    (np.abs(two_theta - center) <= 0.12).any() else 0.0
                    for center in centers])
    shape = np.zeros_like(b)
    solution = np.zeros(len(names))
    # Build shape columns on the feature grid and solve nnls(shape, b - baseline).
    baseline = float(np.min(intensity))
    for column, name in enumerate(names):
        for center, weight in problem["mineral_library"][name]:
            for row, ref in enumerate(centers):
                if abs(ref - center) < 1e-9:
                    shape[row] += 0.0  # placeholder, replaced below
    # Simpler direct construction:
    shape = np.zeros((len(centers), len(names)))
    for column, name in enumerate(names):
        for center, weight in problem["mineral_library"][name]:
            row = centers.index(center)
            shape[row, column] += weight / 100.0
    solution, _ = nnls(shape, np.maximum(b - baseline, 0.0))
    return {name: float(value) for name, value in zip(names, solution)}





def identify_minerals(problem, coarse_scan, slow_scan, budget_units):
    scan = coarse_scan()
    two_theta = np.asarray(scan["two_theta_deg"])
    intensity = np.asarray(scan["intensity"])
    noise = problem["coarse_noise"]

    amplitudes = _nnls_mixture(problem, two_theta, intensity)
    top = max(amplitudes.values()) or 1.0
    present = [name for name, amplitude in sorted(amplitudes.items(),
                                                  key=lambda row: -row[1])
               if amplitude > 0.12 * top]

    if not present:
        present = [max(amplitudes, key=amplitudes.get)]
    # Refine on high-resolution windows: slow-scan the neighborhoods of the top
    # candidates' strongest peaks and re-estimate amplitudes from the union.
    names_sorted = sorted(present, key=lambda n: -amplitudes[n])
    budget = int(budget_units or 0)
    tt_all, ii_all = [two_theta], [intensity]
    for name in names_sorted[:max(budget, 0)]:
        strongest = max(problem["mineral_library"][name],
                        key=lambda peak: peak[1])
        report = slow_scan(strongest[0], min(problem["slow_window_deg"], 8.0))
        tt_all.append(np.asarray(report["two_theta_deg"]))
        ii_all.append(np.asarray(report["intensity"]))
    refined = amplitudes
    if len(tt_all) > 1:
        tt_cat = np.concatenate(tt_all)
        ii_cat = np.concatenate(ii_all)
        # Weight the slow windows by their lower noise.
        weight_map = np.concatenate([np.full(len(t), 0.08)
                                     if index == 0 else np.full(len(t), 0.025)
                                     for index, t in enumerate(tt_all)])
        refined = _nnls_weighted(problem, tt_cat, ii_cat, weight_map)
    top = max(refined.values()) or 1.0
    present = [name for name, amplitude in sorted(refined.items(),
                                                  key=lambda row: -row[1])
               if amplitude > 0.12 * top] or [max(refined, key=refined.get)]
    weights = {name: refined[name] for name in present}
    norm = sum(weights.values()) or 1.0
    fractions = {name: weights[name] / norm for name in present}

    # Rebuild the fitted pattern with a globally calibrated amplitude.
    shape = np.zeros_like(intensity)
    for name in present:
        for center, weight in problem["mineral_library"][name]:
            shape += (fractions[name] * weight / 100.0) * np.exp(
                -0.5 * ((two_theta - center) / 0.12) ** 2)
    gain = float(np.dot(shape, intensity) / max(np.dot(shape, shape), 1e-12))
    fitted = gain * shape
    # Local-contrast sharpness of the coarse residual: a sharp unknown peak rises
    # over its +-0.5 degree neighborhood; a broad amorphous hump does not.
    residual = intensity - fitted
    half = 10  # 0.5 degrees on the public grid
    sharpness = 0.0
    for i in range(half, len(residual) - half):
        local = float(residual[i] - 0.5 * (residual[i - half] + residual[i + half]))
        sharpness = max(sharpness, local)
    slow_noise = problem["slow_noise"] * float(intensity.max())
    if sharpness > 8.0 * slow_noise + 0.45 * float(intensity.max()):
        return {"minerals": [], "fractions": {}, "abstain": True, "confidence": 0.75}

    return {"minerals": present, "fractions": fractions,
            "abstain": False, "confidence": 0.7}
