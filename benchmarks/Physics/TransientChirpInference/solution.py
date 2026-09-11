"""Weak but valid baseline: sparse H1 samples and a fixed line claim."""

def infer_transient(problem, observe):
    rows = [observe(float(t), "H1") for t in problem["candidate_times"][:6]]
    return {
        "abstain": False,
        "model": "line",
        "initial_frequency": 0.11,
        "frequency_slope": 0.0,
        "event_time": 9.0,
        "amplitude": 0.2,
        "confidence": 0.4,
        "evidence_query_ids": [row["query_id"] for row in rows],
    }
