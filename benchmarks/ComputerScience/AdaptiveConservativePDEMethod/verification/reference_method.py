"""Executable public-model witness; it is not asserted to be globally optimal."""
from __future__ import annotations


def design_finite_volume_method(problem):
    return {
        "reconstruction": "weno3",
        "limiter": "superbee",
        "riemann_solver": "godunov",
        "time_integrator": "ssprk3",
        "cells": 192,
        "cfl": 0.7,
        "sensor_threshold": 0.15,
        "shock_blend": 1.0,
        "flux_dissipation": 1.0,
    }
