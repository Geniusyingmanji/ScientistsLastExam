"""Weak legal baseline: one screen measurement and a fixed concordant interpretation."""


def infer_upb_history(problem, measure):
    reading = measure(problem["grain_descriptors"][0]["grain_id"], "screen")
    return {
        "history": "concordant",
        "crystallization_age_myr": 1000.0,
        "confidence": 0.5,
        "evidence_query_ids": [reading["query_id"]],
        "abstain": False,
    }
