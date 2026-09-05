"""Standalone normalized A-optimal greedy/swap archive; public matrices only."""
import numpy as np

def _reference_archive(problem):
    hp, prior, g = problem["proxy_sensitivity"], problem["prior_covariance"], problem["forecast_matrix"]
    costs = np.asarray([row["cost_units"] for row in problem["observation_catalog"]])
    scales = np.sqrt(np.diag(g @ prior @ g.T))
    normalized_g = g / scales[:, None]
    def objective_for(indices):
        h = hp[indices]
        r = np.diag([problem["observation_catalog"][i]["noise_std"] ** 2 for i in indices])
        post = prior - prior @ h.T @ np.linalg.solve(h @ prior @ h.T + r, h @ prior)
        return float(np.trace(normalized_g @ post @ normalized_g.T))
    plans = []
    for target_cost in (7, 9, 11, 13, 15, 16, 17, 18):
        selected = []
        while len(selected) < 10:
            best = None
            for index in range(len(costs)):
                if index in selected or np.sum(costs[selected]) + costs[index] > target_cost:
                    continue
                trial = selected + [index]
                h = hp[trial]
                r = np.diag([problem["observation_catalog"][i]["noise_std"] ** 2 for i in trial])
                post = prior - prior @ h.T @ np.linalg.inv(h @ prior @ h.T + r) @ h @ prior
                objective = objective_for(trial)
                if best is None or objective < best[0]:
                    best = (objective, index)
            if best is None:
                break
            selected.append(best[1])
        for _pass in range(3):
            best_value = objective_for(selected)
            replacement = None
            for position in range(len(selected)):
                for index in range(len(costs)):
                    if index in selected:
                        continue
                    trial = selected.copy(); trial[position] = index
                    if costs[trial].sum() > target_cost:
                        continue
                    value = objective_for(trial)
                    if value < best_value - 1e-12:
                        best_value, replacement = value, trial
            if replacement is None:
                break
            selected = replacement
        if len(selected) >= 3:
            plans.append(np.asarray(sorted(selected), dtype=int))
    unique = []
    for plan in plans:
        if not any(np.array_equal(plan, old) for old in unique):
            unique.append(plan)
    return unique[:16]

def design_ice_observation_network(problem):
    return {"plans": _reference_archive(problem)}
