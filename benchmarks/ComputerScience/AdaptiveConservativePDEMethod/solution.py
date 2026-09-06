"""Legal weak finite-volume method used as the zero-score normalization anchor."""
from __future__ import annotations


def design_finite_volume_method(problem):
    choices = problem["discrete_choices"]
    bounds = problem["continuous_bounds"]
    return {
        "reconstruction": choices["reconstruction"][0],
        "limiter": choices["limiter"][0],
        "riemann_solver": choices["riemann_solver"][0],
        "time_integrator": choices["time_integrator"][0],
        "cells": choices["cells"][0],
        "cfl": 0.45,
        "sensor_threshold": 0.5,
        "shock_blend": bounds["shock_blend"][1],
        "flux_dissipation": 1.15,
    }
