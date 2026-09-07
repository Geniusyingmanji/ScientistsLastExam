"""Weak but valid baseline: claim a point lens after a fixed sparse cadence."""


def infer_microlensing(problem, observe):
    times = problem["candidate_times"]
    rows = [observe(float(t), "r") for t in times[:6]]
    return {
        "abstain": False,
        "model": "point_lens",
        "timescale_days": 8.0,
        "amplitude": 0.0,
        "confidence": 0.5,
        "evidence_query_ids": [row["query_id"] for row in rows],
    }
