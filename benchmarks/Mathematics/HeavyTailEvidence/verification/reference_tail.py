"""Truth-blind Clauset-style family test with a small-n refusal."""
from __future__ import annotations

import math


def synthesize_tail_evidence(problem, extra_draw):
    xmin = float(problem["xmin"])
    public = [float(x) for x in problem["public_sample"] if float(x) >= xmin]
    _ = problem["family_names"]
    _ = problem["abstain_when"]
    if len(public) < 25:
        return {"abstain": True, "confidence": 0.86}
    extra = [float(extra_draw()) for _ in range(min(20, int(problem["extra_draw_budget"])))]
    data = public + extra
    n = len(data)
    logs = [math.log(x / xmin) for x in data]
    mean_log = sum(logs) / n
    second = sum((value - mean_log) ** 2 for value in logs) / n
    alpha = 1.0 + n / max(sum(logs), 1e-9)
    ratio = second / max(mean_log ** 2, 1e-9)
    if ratio < 0.32:
        return {
            "abstain": False,
            "family": "lognormal",
            "alpha": 2.0,
            "confidence": 0.7,
        }
    if 0.65 < ratio < 1.45 and 1.6 < alpha < 4.5:
        return {
            "abstain": False,
            "family": "powerlaw",
            "alpha": float(alpha),
            "confidence": 0.72,
        }
    return {"abstain": True, "confidence": 0.78}
