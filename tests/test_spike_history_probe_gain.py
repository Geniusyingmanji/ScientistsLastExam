"""The two-point probe must propagate its measured gain into its predictions."""
import importlib.util
import math
from pathlib import Path
import sys
from unittest.mock import patch

import pytest


TASK = Path(__file__).resolve().parents[1] / "benchmarks/Biology/SpikeHistoryInference"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def probe():
    oracle = _load("spike_gain_oracle", TASK / "verification/evaluator.py")
    with patch.dict(sys.modules, {"evaluator": oracle}):
        return _load("spike_gain_probe", TASK / "verification/shortcut_probe.py")


def _problem():
    return {
        "parameter_bounds": {"intercept": [-5.0, 5.0], "stimulus_gain": [0.0, 2.0]},
        "prediction_contexts": [{"stimulus": 1.0, "recent_spike_lags_ms": []}],
        "trials": [{"trial_id": "synthetic"}],
    }


@pytest.mark.parametrize("estimated_gain,expected_gain", [(1.6, 1.6), (-4.0, 0.0), (4.0, 2.0)])
def test_two_point_gain_drives_output_and_prediction(probe, estimated_gain, expected_gain):
    features = (0.5, 0.0, 0.0, 0.0, -0.2, estimated_gain)
    result = probe._candidate(_problem(), (1.0, 1.0, 1.0), (0.4, 0.8, 20.0),
                              features=features, two_point=True)
    assert result["stimulus_gain"] == expected_gain
    assert result["prediction_probabilities"] == pytest.approx(
        [1.0 / (1.0 + math.exp(0.2 - expected_gain))])


def test_constant_probe_keeps_its_declared_grid_gain(probe):
    features = (0.5, 0.0, 0.0, 0.0, -0.2, 1.6)
    result = probe._candidate(_problem(), (1.0, 1.0, 1.0), (0.4, 0.8, 20.0),
                              features=features, two_point=False)
    assert result["stimulus_gain"] == 0.4
    assert result["prediction_probabilities"] == pytest.approx([1.0 / (1.0 + math.exp(-0.4))])
