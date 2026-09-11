"""Truth-blind capability ablations for the FRAP reference."""
from __future__ import annotations

from reference_solver import solve


def two_radii_only(problem, measure):
    return solve(problem, measure, radii=problem["bleach_radii_um"][1:3])


def short_times_only(problem, measure):
    return solve(problem, measure, time_indices=tuple(range(8)))


def fixed_binding_rates(problem, measure):
    return solve(problem, measure, fixed_rates=(0.30, 0.12))


def never_refuse(problem, measure):
    return solve(problem, measure, force_supported=True)
