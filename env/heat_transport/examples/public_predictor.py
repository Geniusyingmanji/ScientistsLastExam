"""Minimal frozen predictor example; uses public semantics and no world import.

This constant-in-time predictor is an interface example, not an inferred model.
Replace it with a model fitted to the observations collected during exploration.
"""


def predict(spec):
    return [[float(spec["initial_temperature"])] * 3 for _ in spec["times"]]
