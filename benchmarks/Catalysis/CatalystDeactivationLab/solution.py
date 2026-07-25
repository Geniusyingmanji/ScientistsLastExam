"""Weak valid baseline: record one blank and abstain."""


def investigate_catalyst(problem, experiment):
    coupon_versions = dict(problem["coupon_state_versions"])
    response = experiment([{
        "request_id": "baseline-blank",
        "kind": "blank",
        "lab_state_version": problem["lab_state_version"],
    }])
    events = response["events"]
    return {
        "log10_preexponential": 6.0,
        "activation_energy_kj_mol": 60.0,
        "deactivation_rate_per_min": 0.012,
        "gain_drift_per_event": 0.0,
        "offset_drift_per_event": 0.0,
        "operating_policy": {
            "temperature_k": 500.0,
            "feed_concentration": 0.5,
            "duration_min": 8.0,
        },
        "confidence": 0.0,
        "abstain": True,
        "evidence_event_ids": [event["event_id"] for event in events],
        "final_lab_state_version": response["lab_state_version"],
        "final_coupon_state_versions": coupon_versions,
    }
