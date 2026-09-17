"""Weak valid baseline: confidently fit the wrong fixed confined model."""


def infer_aquifer(problem, measure):
    rows = [
        measure(problem["observation_radii_m"][1], time)
        for time in problem["observation_times_s"][1:7]
    ]
    return {
        "diagnosis": "confined",
        "transmissivity_m2_s": problem["parameter_bounds"]["transmissivity_m2_s"][0],
        "storativity": problem["parameter_bounds"]["storativity"][1],
        "predicted_drawdown_m": [0.0 for _ in problem["prediction_contexts"]],
        "confidence": 0.99,
        "abstain": False,
        "evidence_measurement_ids": [row["measurement_id"] for row in rows],
    }
