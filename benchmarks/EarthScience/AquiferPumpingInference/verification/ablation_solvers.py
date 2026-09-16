"""Truth-blind capability ablations for task calibration."""
from reference_solver import _infer


def two_radii_only(problem, measure):
    return _infer(problem, measure, radius_count=2)


def fixed_storage(problem, measure):
    return _infer(problem, measure, fixed_storage=0.001)


def never_refuse(problem, measure):
    return _infer(problem, measure, allow_refusal=False)
