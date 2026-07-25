"""Weak valid baseline: return nominal sweep values and abstain."""


def analyze_qcm(problem):
    resonance = {}
    quality = {}
    nominal = problem["nominal_frequency_hz_by_harmonic"]
    for sweep in problem["sweeps"]:
        resonance[sweep["sweep_id"]] = nominal[str(sweep["harmonic"])]
        quality[sweep["sweep_id"]] = 20000.0
    return {
        "calibration": {
            "start_offset_counts": [0.0, 0.0],
            "end_offset_counts": [0.0, 0.0],
            "start_complex_gain_counts_per_siemens": [700000.0, 0.0],
            "end_complex_gain_counts_per_siemens": [700000.0, 0.0],
        },
        "resonance_frequency_hz_by_sweep": resonance,
        "quality_factor_by_sweep": quality,
        "mass_loading_ug_cm2": 0.0,
        "deposition_rate_ug_cm2_s": 0.0,
        "predicted_mass_ug_cm2": 0.0,
        "additional_deposition_time_s": 0.0,
        "diagnosis": "undetermined",
        "confidence": 0.0,
        "abstain": True,
        "evidence_ids": [
            block["calibration_id"] for block in problem["calibration_blocks"]
        ] + [sweep["sweep_id"] for sweep in problem["sweeps"]],
    }
