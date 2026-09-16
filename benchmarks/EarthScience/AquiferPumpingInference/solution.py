"""Weak valid baseline: collect one datum and make no aquifer claim."""


def infer_aquifer(problem, measure):
    row = measure(problem["observation_radii_m"][0], problem["observation_times_s"][0])
    return {
        "diagnosis": "undetermined",
        "transmissivity_m2_s": 0.001,
        "storativity": 0.001,
        "predicted_drawdown_m": [0.0 for _ in problem["prediction_contexts"]],
        "confidence": 0.0,
        "abstain": True,
        "evidence_measurement_ids": [row["measurement_id"]],
    }
