"""Share expensive, freshly computed FWI reference results within one test run.

No stored scores are loaded. Each budget is evaluated against the actual oracle
once, and callers receive copies. Deterministic sandbox replay is checked by the
separate Linux validation, rather than repeated by unrelated assertion groups.
"""
from copy import deepcopy
from functools import lru_cache
import importlib.util
from pathlib import Path

TASK = Path(__file__).resolve().parents[1] / "benchmarks/EarthScience/ActiveFullWaveformInversion"


def _load(relative, name):
    spec = importlib.util.spec_from_file_location(name, TASK / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@lru_cache(maxsize=None)
def _reference_result(budget):
    oracle = _load("verification/evaluator.py", "cached_fwi_oracle")
    reference = _load("verification/reference_solver.py", "cached_fwi_reference")
    return oracle.evaluate(lambda *inputs: reference.invert_velocity_model(
        *inputs[:-1], min(inputs[-1], budget)))


def reference_result(budget=3):
    return deepcopy(_reference_result(budget))
