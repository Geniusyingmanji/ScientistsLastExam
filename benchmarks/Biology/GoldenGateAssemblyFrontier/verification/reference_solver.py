"""Truth-blind deterministic reference using only the public target and count matrices."""

import importlib.util
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "golden_gate_reference_evaluator", Path(__file__).with_name("evaluator.py")
)
_EVALUATOR = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_EVALUATOR)


def design_assembly(problem):
    return _EVALUATOR.reference_design(problem)
