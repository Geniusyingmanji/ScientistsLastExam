"""Weak legal baseline for FRAPBindingInference."""


def infer_frap_binding(problem, measure):
    observation = measure(problem["bleach_radii_um"][0], problem["sample_times_s"][0])
    return {
        "diagnosis": "undetermined",
        "diffusion_coefficient_um2_s": 0.5,
        "mobile_fraction": 0.75,
        "binding_on_rate_s": 0.2,
        "binding_off_rate_s": 0.1,
        "predicted_recovery": [0.0 for _ in problem["prediction_contexts"]],
        "confidence": 0.0,
        "abstain": True,
        "evidence_measurement_ids": [observation["measurement_id"]],
    }
