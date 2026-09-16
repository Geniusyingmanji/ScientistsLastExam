"""Weak legal baseline for FRAPBindingInference."""


def infer_frap_binding(problem, measure):
    observations = [
        measure(problem["bleach_radii_um"][0], time)
        for time in problem["sample_times_s"][:4]
    ]
    return {
        "diagnosis": "supported",
        "diffusion_coefficient_um2_s": 0.5,
        "mobile_fraction": 0.75,
        "binding_on_rate_s": 0.2,
        "binding_off_rate_s": 0.1,
        "predicted_recovery": [0.0 for _ in problem["prediction_contexts"]],
        "confidence": 0.95,
        "abstain": False,
        "evidence_measurement_ids": [row["measurement_id"] for row in observations],
    }
