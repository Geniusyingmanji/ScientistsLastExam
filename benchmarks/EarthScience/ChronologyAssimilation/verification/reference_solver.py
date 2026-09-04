"""Truth-blind dated-proxy interpolation witness."""

import numpy as np


def reconstruct_climate(time_grid_years, proxy_catalog, date_sample, budget_units):
    del budget_units
    offsets = []
    reconstructions = []
    weights = []
    for record in proxy_catalog:
        indices = np.linspace(0, len(record["values"]) - 1, 5, dtype=int)
        dated = date_sample(int(record["proxy_index"]), indices)
        nominal = np.asarray(record["nominal_age_years"], dtype=float)
        offset = float(np.mean(np.asarray(dated["dated_age_years"]) - nominal[indices]))
        offsets.append(offset)
        corrected_age = nominal + offset
        values = np.asarray(record["values"], dtype=float) / float(record["sensitivity"])
        reconstructions.append(np.interp(time_grid_years, corrected_age, values))
        weights.append(float(record["site_weight"]) / float(record["noise_std"]) ** 2)
    matrix = np.asarray(reconstructions)
    weights = np.asarray(weights)
    mean = np.average(matrix, axis=0, weights=weights)
    spread = np.sqrt(np.average((matrix - mean) ** 2, axis=0, weights=weights) + 0.08 ** 2)
    return {"temperature_mean": mean, "temperature_std": spread,
            "age_offsets_years": offsets, "confidence": 0.7, "abstain": False}
