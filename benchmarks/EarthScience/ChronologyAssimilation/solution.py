"""Weak valid baseline: sparse constant age offsets and an overconfident proxy mean."""

import numpy as np


def reconstruct_climate(time_grid_years, proxy_catalog, date_sample, budget_units):
    del budget_units
    offsets = np.zeros(len(proxy_catalog))
    for index, record in enumerate(proxy_catalog[:3]):
        indices = np.linspace(0, len(record["values"]) - 1, 3, dtype=int)
        dated = date_sample(int(record["proxy_index"]), indices)
        offsets[index] = np.clip(np.mean(np.asarray(dated["dated_age_years"])
                                       - np.asarray(record["nominal_age_years"])[indices]), -300., 300.)
    estimates = []
    for record, offset in zip(proxy_catalog, offsets):
        ages = np.clip(np.asarray(record["nominal_age_years"]) + offset,
                       time_grid_years[0], time_grid_years[-1])
        signal = np.asarray(record["values"]) / record["sensitivity"]
        estimates.append(np.interp(time_grid_years, ages, signal))
    # Ignore nonlinear chronology, response misspecification and cross-record
    # disagreement; a noise-only uncertainty understates these errors.
    return {"temperature_mean": np.mean(estimates, axis=0),
            "temperature_std": np.full(len(time_grid_years), .25),
            "age_offsets_years": offsets, "confidence": .9, "abstain": False}
