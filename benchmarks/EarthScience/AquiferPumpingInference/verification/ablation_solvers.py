"""Truth-blind capability ablations for task calibration."""
from __future__ import annotations

import importlib.util
from pathlib import Path


_SPEC = importlib.util.spec_from_file_location(
    "aquifer_reference_for_ablations", Path(__file__).with_name("reference_solver.py")
)
_REFERENCE = importlib.util.module_from_spec(_SPEC)
assert _SPEC.loader is not None
_SPEC.loader.exec_module(_REFERENCE)
_infer = _REFERENCE._infer


def one_radius_half_budget(problem, measure):
    return _infer(problem, measure, radius_indices=(-1,), repeats=1)


def fixed_storage(problem, measure):
    return _infer(problem, measure, fixed_storage=0.001)


def never_refuse(problem, measure):
    return _infer(problem, measure, allow_refusal=False)
