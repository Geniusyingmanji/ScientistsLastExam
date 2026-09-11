"""Scientific regressions for the retained wind-farm co-design candidate."""

import ast
import importlib.util
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
TASK = ROOT / "benchmarks/Engineering/WakeAwareFarmCoDesign"
_MODULE_CACHE = {}


def load(file="verification/evaluator.py"):
    if file not in _MODULE_CACHE:
        path = TASK / file
        spec = importlib.util.spec_from_file_location("wake_" + file.replace("/", "_"), path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _MODULE_CACHE[file] = module
    return _MODULE_CACHE[file]


def test_reference_is_standalone_and_direction_count_is_problem_driven():
    path = TASK / "verification/reference.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert all(alias.name.split(".")[0] in {"numpy", "math"} for alias in node.names)
        if isinstance(node, ast.ImportFrom):
            assert node.module.split(".")[0] in {"numpy", "math"}
    assert "DIRECTIONS" not in path.read_text(encoding="utf-8")


def test_twelve_malformed_candidates_fail_closed():
    evaluator = load()
    invalid = [None, {}, "", True, 12, float("nan"), float("inf"), [], [0],
               {"plans": []}, {"abstain": "yes"}, {"confidence": float("nan")}]
    for value in invalid:
        result = evaluator.evaluate(lambda *_args, **_kwargs: value)
        assert result["valid"] == 0, value
        assert result["combined_score"] == 0, value


def test_public_contract_contains_every_scoring_constant():
    evaluator = load()
    problem = evaluator._problem(evaluator.INSTANCE_SPECS[0])
    for key in ("wake_expansion_public", "yaw_power_exponent"):
        assert key in problem


def test_layout_only_and_yaw_only_cannot_masquerade_as_co_design():
    evaluator = load()

    def layout_only(problem):
        layout = evaluator._grid(problem, True)
        yaw = np.zeros((len(problem["wind_directions_deg"]), len(layout)))
        return {"layout_xy_m": layout.tolist(), "yaw_by_direction_deg": yaw.tolist()}

    def yaw_only(problem):
        layout = evaluator._grid(problem, False)
        yaw = evaluator._refine_yaw(problem, layout, np.zeros(
            (len(problem["wind_directions_deg"]), len(layout))))
        return {"layout_xy_m": layout.tolist(), "yaw_by_direction_deg": yaw.tolist()}

    layout_result = evaluator.evaluate(layout_only)
    yaw_result = evaluator.evaluate(yaw_only)
    assert layout_result["valid"] == yaw_result["valid"] == 1
    assert layout_result["combined_score"] == 0
    assert yaw_result["combined_score"] == 0
    assert any(row["layout_score"] > 0 for row in layout_result["per_instance"])
    assert any(row["yaw_control_score"] > 0 for row in yaw_result["per_instance"])


def test_reference_uses_both_axes_and_leaves_component_headroom():
    evaluator = load()
    reference = load("verification/reference.py")
    result = evaluator.evaluate(reference.design_wind_farm)
    assert result["valid"] == 1
    assert 0.5 < result["combined_score"] < 0.9
    for row in result["per_instance"]:
        assert row["layout_score"] > 0
        assert row["yaw_control_score"] > 0
        assert row["yaw_gain_gwh"] > 0
        assert row["layout_score"] <= 1 + 1e-9
        assert row["yaw_control_score"] <= 1 + 1e-9
