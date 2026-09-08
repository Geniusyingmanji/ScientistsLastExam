"""Truth-blind capability ablations for task calibration."""
from reference_solver import _infer


def one_radius_repeated(problem, measure):
    return _infer(problem, measure, radius_count=1, repeats=2)


def fixed_storage(problem, measure):
    return _infer(problem, measure, fixed_storage=0.001)


def never_refuse(problem, measure):
    return _infer(problem, measure, allow_refusal=False)
