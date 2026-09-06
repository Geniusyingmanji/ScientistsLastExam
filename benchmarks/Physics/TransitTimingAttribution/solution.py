"""Weak baseline: make no claim and spend one legal follow-up measurement."""
def attribute_ttv(observation, measure, budget_units):
    if budget_units: measure(0)
    return {"abstain": True}
