"""Dated-proxy GLS reconstruction with calibration and coherence rejection.

Only public archive rows and charged dating responses are used. The Gaussian-process
prior and first-order propagation of dating error are approximations, not hidden truth.
"""
import numpy as np
from scipy.interpolate import PchipInterpolator
from scipy.linalg import cho_factor, cho_solve


def reconstruct_climate(time_grid_years, proxy_catalog, date_sample, budget_units):
    empty = {"temperature_mean": [], "temperature_std": [], "age_offsets_years": [],
             "confidence": .1, "abstain": True}
    calibration = []
    for row in proxy_catalog:
        predicted = row["sensitivity"] * np.asarray(row["calibration_temperature_c"])
        calibration.extend(((np.asarray(row["calibration_proxy_values"]) - predicted) /
                            row["calibration_noise_std"]) ** 2)
    if np.mean(calibration) > 4.0:
        return empty
    offsets, ages, values, variances, reconstructions, age_curves = [], [], [], [], [], []
    cost = 0
    for row in proxy_catalog:
        # Avoid clipped endpoints; one batch per proxy uses exactly the declared budget.
        nominal = np.asarray(row["nominal_age_years"])
        indices = np.linspace(1, len(nominal) - 2, 5, dtype=int)
        if cost + 2 > budget_units:
            return empty
        dated = date_sample(int(row["proxy_index"]), indices)
        cost += int(dated["budget_cost"])
        offset = float(np.mean(np.asarray(dated["dated_age_years"]) - nominal[indices]))
        offsets.append(float(np.clip(offset,-300,300)))
        # Shape-preserving interpolation of sparse dates; extrapolate then enforce bounds.
        measured = np.maximum.accumulate(np.asarray(dated["dated_age_years"]))
        corrected = np.clip(PchipInterpolator(nominal[indices], measured)(nominal),
                            time_grid_years[0], time_grid_years[-1])
        corrected = np.maximum.accumulate(corrected)
        age_curves.append(corrected)
        signal = np.asarray(row["values"]) / row["sensitivity"]
        noise_variance = (row["noise_std"] / row["sensitivity"]) ** 2
        # Dating errors are shared by a record. This diagonal approximation is conservative
        # at steep gradients; a joint age/field posterior remains a stronger method.
        slope = np.gradient(signal, nominal)
        variance = noise_variance + slope**2 * (dated["date_noise_std_years"]**2 + 35.**2)
        ages.extend(corrected); values.extend(signal); variances.extend(variance)
        reconstructions.append(np.interp(time_grid_years, corrected, signal))
    matrix = np.asarray(reconstructions)
    common = np.mean(matrix, axis=0)
    disagreement = float(np.mean((matrix - common) ** 2))
    if disagreement > .35:
        return empty
    ages = np.asarray(ages); values = np.asarray(values)
    grid = np.asarray(time_grid_years)
    def kernel(a, b):
        distance = np.abs(np.asarray(a)[:,None] - np.asarray(b)[None,:])
        return .55 * np.exp(-.5*(distance/100.0)**2) + .10 * np.exp(-distance/35.0)
    covariance = kernel(ages, ages) + np.diag(variances) + 1e-8*np.eye(len(ages))
    factor = cho_factor(covariance, lower=True)
    cross = kernel(grid, ages)
    mean = cross @ cho_solve(factor, values)
    variance = np.diag(kernel(grid,grid)) - np.sum(cross * cho_solve(factor,cross.T).T,axis=1)
    return {"temperature_mean":mean, "temperature_std":np.sqrt(np.maximum(variance,.04**2)),
            "sample_ages_years":age_curves,"confidence":.8,"abstain":False}
