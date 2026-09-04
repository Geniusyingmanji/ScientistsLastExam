"""Truth-blind greedy A-optimal multibudget observation archive."""

import numpy as np


def design_ice_observation_network(problem):
    h = np.asarray(problem["proxy_sensitivity"], dtype=float)
    prior = np.asarray(problem["prior_covariance"], dtype=float)
    forecast = np.asarray(problem["forecast_matrix"], dtype=float)
    catalog = problem["observation_catalog"]
    costs = np.asarray([row["cost_units"] for row in catalog], dtype=float)
    plans = []
    for target in (7, 9, 11, 13, 15, 16, 17, 18):
        selected = []
        while len(selected) < int(problem["selection_size_bounds"][1]):
            best = None
            for index in range(len(catalog)):
                if index in selected or np.sum(costs[selected]) + costs[index] > target:
                    continue
                trial = selected + [index]
                hs = h[trial]
                noise = np.diag([catalog[i]["noise_std"] ** 2 for i in trial])
                posterior = prior - prior @ hs.T @ np.linalg.inv(hs @ prior @ hs.T + noise) @ hs @ prior
                objective = float(np.trace(forecast @ posterior @ forecast.T))
                if best is None or objective < best[0]:
                    best = (objective, index)
            if best is None:
                break
            selected.append(best[1])
        if len(selected) >= int(problem["selection_size_bounds"][0]):
            plan = sorted(selected)
            if plan not in plans:
                plans.append(plan)
    return {"plans": plans}
