"""Weak valid baseline: clustered low-cost surface-velocity observations."""


def design_ice_observation_network(problem):
    catalog = problem["observation_catalog"]
    cheap = sorted(catalog, key=lambda row: (row["cost_units"], row["x_normalized"], row["index"]))
    plans = []
    for offset in range(4):
        selected = [int(row["index"]) for row in cheap[offset:offset + 3]]
        plans.append(selected)
    return {"plans": plans}
