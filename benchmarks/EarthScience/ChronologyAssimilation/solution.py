"""Weak valid baseline: purchase a small dating panel and abstain."""

import numpy as np


def reconstruct_climate(time_grid_years, proxy_catalog, date_sample, budget_units):
    del time_grid_years, budget_units
    for record in proxy_catalog[:3]:
        indices = np.linspace(0, len(record["values"]) - 1, 3, dtype=int)
        date_sample(int(record["proxy_index"]), indices)
    return {"temperature_mean": [], "temperature_std": [], "age_offsets_years": [],
            "confidence": 0.0, "abstain": True}
