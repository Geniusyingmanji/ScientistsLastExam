"""Truth-blind capability ablations for the FRAP reference."""
from __future__ import annotations

from reference_solver import solve


def one_radius_only(problem, measure):
    return solve(problem, measure, radii=(problem["bleach_radii_um"][0],))


def half_time_grid(problem, measure):
    return solve(problem, measure, time_indices=(2, 4, 7, 9))


def fixed_binding_rates(problem, measure):
    return solve(problem, measure, fixed_rates=(0.30, 0.12))


def never_refuse(problem, measure):
    return solve(problem, measure, force_supported=True)
