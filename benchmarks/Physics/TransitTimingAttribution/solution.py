"""Weak, deterministic baseline that is confidently wrong.

It buys two legal follow-up timings, cites both real query ids, and then commits to a fixed
planet claim at the shortest grid period with high confidence. The claim is testable and wrong
by construction, so the baseline is valid and scores exactly zero: it earns nothing on supported
worlds and is a false discovery on every unsupported world. It never abstains.
"""
def attribute_ttv(observation, measure, budget_units):
    limit = int(observation["maximum_followup_transit_number"])
    start = max(int(n) for n in observation["transit_numbers"]) + 1
    ids = []
    for number in (limit, limit - 1):
        if len(ids) >= int(budget_units) or number < start:
            break
        ids.append(measure(int(number))["query_id"])
    if len(ids) < 2:
        # Cannot cite two distinct measurements: the only valid move left is to decline.
        return {"abstain": True}
    grid = list(observation["planet_period_grid"])
    period = float(grid[0]) if grid else 1.0
    offsets = list(observation["timing_offsets_days"])
    forecast = float(offsets[-1]) if offsets else 0.0
    return {"abstain": False, "mechanism": "planet", "period": period,
            "next_offset_days": forecast, "confidence": 0.95, "evidence_query_ids": ids}
