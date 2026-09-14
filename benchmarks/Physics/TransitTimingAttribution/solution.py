"""Weak, deterministic baseline that makes a deliberately overconfident claim."""
def attribute_ttv(observation, measure, budget_units):
    # Spend one legal query, then use only public observations.  The fixed
    # planet hypothesis is intentionally poor, but is a valid, testable claim.
    if budget_units:
        extra = measure(int(observation["maximum_followup_transit_number"]))
    ids = list(observation["query_ids"])
    evidence = ids[:2]
    grid = list(observation["planet_period_grid"])
    period = float(grid[0]) if grid else 1.0
    offsets = list(observation["timing_offsets_days"])
    forecast = float(offsets[-1]) if offsets else 0.0
    return {"abstain": False, "mechanism": "planet", "period": period,
            "next_offset_days": forecast, "confidence": 0.95,
            "evidence_query_ids": evidence}
