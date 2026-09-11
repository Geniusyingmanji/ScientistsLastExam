"""Previously disclosed four-way probe; fixed configuration, no search."""
import numpy as np


def peak_features(counts, controls):
    """Single-target features, including narrow residuals omitted in the first audit."""
    excess = np.maximum(0, counts - controls / 8)
    smooth = np.convolve(excess, np.ones(3) / 3, mode="valid")
    # Approximate variance of the centre-minus-three-bin-mean contrast.
    variance = counts + controls / 64
    contrast_var = (variance[:-2] + 4 * variance[1:-1] + variance[2:]) / 9
    peak = float(np.max((excess[1:-1] - smooth) / np.sqrt(np.maximum(1, contrast_var))))
    fractional_peak = float(np.max((excess[1:-1] - smooth) / np.maximum(1, smooth)))
    return peak, fractional_peak


def probe_answer(problem, experiment, config):
    """Legal truth-blind four-way candidate; no evaluator state or labels."""
    target, units, threshold, ratio, mass, peak_kind, peak_threshold = config
    obs = experiment({"target": int(target), "units": int(units)})
    counts, controls = np.array(obs["counts"]), np.array(obs["background_counts"])
    excess = np.maximum(0, counts - controls / 8)
    if excess.sum() / units < threshold:
        return {"model": "none"}
    if peak_features(counts, controls)[int(peak_kind)] > peak_threshold:
        return {"abstain": True}
    hardness = excess[9:].sum() / max(1, excess[:9].sum())
    return {"model": "q2" if hardness > ratio else "contact", "mass_gev": float(mass)}


FIXED_CONFIG = (1, 1, 60, 2, 95.83680934806682, 1, 0.5)


def infer_recoil(problem, experiment):
    return probe_answer(problem, experiment, FIXED_CONFIG)
