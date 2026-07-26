"""Weak valid baseline: optimize the public proxy/diversity batch without assays."""

import itertools


def _distance(left, right):
    elements = set(left["composition"]) | set(right["composition"])
    return 0.5 * sum(abs(
        float(left["composition"].get(element, 0.0))
        - float(right["composition"].get(element, 0.0))
    ) for element in elements)


def design_alloy_batch(problem, assay):
    del assay
    rows = list(problem["candidates"])
    values = [float(row["proxy_hardness_hv"]) for row in rows]
    lower, upper = min(values), max(values)
    normalized = [
        (value - lower) / (upper - lower) if upper > lower else 0.0
        for value in values
    ]
    best = None
    for indices in itertools.combinations(range(len(rows)), int(problem["batch_size"])):
        diversity = sum(
            _distance(rows[left], rows[right])
            for left, right in itertools.combinations(indices, 2)
        ) / 3.0
        value = 0.90 * sum(normalized[index] for index in indices) / 3.0
        value += 0.10 * diversity
        key = tuple(str(rows[index]["id"]) for index in indices)
        if (
            best is None or value > best[0] + 1.0e-15
            or (abs(value - best[0]) <= 1.0e-15 and key < best[1])
        ):
            best = (value, key, indices)
    selected = [rows[index] for index in best[2]]
    predictions = {}
    for row in selected:
        point = float(row["proxy_hardness_hv"])
        predictions[str(row["id"])] = {
            "predicted_hardness_hv": point,
            "interval_hv": [max(0.0, point - 300.0), min(2000.0, point + 300.0)],
        }
    return {
        "alloy_ids": [str(row["id"]) for row in selected],
        "predictions": predictions,
    }
