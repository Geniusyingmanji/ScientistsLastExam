"""Pure contract fixtures: never import or instantiate Kernel/World.

All production physics and independent reference calls belong to the separately
budgeted, preregistered one-shot calibration; they are not hidden in pytest.
"""

import ast
import copy
import json
import math
from pathlib import Path

import numpy as np
import pytest

from env.spin_echo.baseline import baseline
from env.spin_echo.protocol import CHANNELS, describe, example, integer, validate_spec


def spec():
    return {"initial_magnetization": [1., 0., 0.], "times_ms": [0., 1., 10.]}


def test_canonical_defaults_do_not_mutate():
    raw = spec()
    before = copy.deepcopy(raw)
    canonical = validate_spec(raw)
    assert raw == before
    assert canonical["detuning_hz"] == 0 and canonical["pulses"] == []
    canonical["initial_magnetization"][0] = .5
    assert raw == before


@pytest.mark.parametrize("value", [True, np.bool_(False), "1", float("nan"), float("inf"), 1j, 10**400])
def test_nonfinite_nonreal_and_bool_rejected(value):
    raw = spec()
    raw["detuning_hz"] = value
    with pytest.raises(ValueError):
        validate_spec(raw)


@pytest.mark.parametrize("changes", [
    {"extra": 1}, {"initial_magnetization": [1, 1, 0]},
    {"initial_magnetization": [1, 0]}, {"initial_magnetization": (1, 0, 0)},
    {"times_ms": []}, {"times_ms": [0]*130}, {"times_ms": [0, 0]},
    {"times_ms": [1, 0]}, {"times_ms": [-.1, 10]}, {"times_ms": [251]},
    {"times_ms": [True, 10]}, {"detuning_hz": 40.001}, {"pulses": {}},
    {"pulses": [{"time_ms": 0, "angle_rad": 1, "phase_rad": 0}]},
    {"pulses": [{"time_ms": 11, "angle_rad": 1, "phase_rad": 0}]},
    {"pulses": [{"time_ms": 1, "angle_rad": 7, "phase_rad": 0}]},
    {"pulses": [{"time_ms": 1, "angle_rad": 1, "phase_rad": 4}]},
    {"pulses": [{"time_ms": 1, "angle_rad": 1}]},
    {"pulses": [{"time_ms": 1, "angle_rad": 1, "phase_rad": 0, "extra": 0}]},
    {"pulses": [{"time_ms": 1, "angle_rad": 1, "phase_rad": 0}]*2},
    {"pulses": [{"time_ms": t, "angle_rad": 1, "phase_rad": 0} for t in [1, 1.05]]},
    {"pulses": [{"time_ms": t, "angle_rad": 1, "phase_rad": 0} for t in [2, 1]]},
    {"pulses": [{"time_ms": t, "angle_rad": 1, "phase_rad": 0} for t in range(1, 14)]},
])
def test_invalid_contract(changes):
    raw = spec()
    raw.update(changes)
    with pytest.raises(ValueError):
        validate_spec(raw)


def test_boundary_validity_without_trajectory():
    raw = {"initial_magnetization": [0, 0, 0], "times_ms": np.linspace(0, 250, 129).tolist(),
           "detuning_hz": -40, "pulses": [{"time_ms": .1+i*.1, "angle_rad": 2*math.pi,
                                           "phase_rad": -math.pi} for i in range(12)]}
    out = validate_spec(raw)
    assert len(out["pulses"]) == 12 and len(out["times_ms"]) == 129
    assert validate_spec({"initial_magnetization": [1, 0, 0], "times_ms": [0]})["times_ms"] == [0.]
    assert validate_spec({"initial_magnetization": [1, 0, 0], "times_ms": [.1],
                          "pulses": [{"time_ms": .1, "angle_rad": 1, "phase_rad": 0}]})["pulses"]


def test_public_description_and_manifest():
    public = describe()
    for raw in public["examples"]:
        validate_spec(raw)
    serialized = json.dumps(public)
    for secret in ("static_frequency_spread", "irreversible_transverse_decay", "31001", "r2_per_s", "offsets_hz", "weights"):
        assert secret not in serialized
    assert "AFTER" in serialized and "R1=0" in serialized and "zero initial vector" in serialized
    manifest = json.loads((Path(__file__).parents[1]/"world.json").read_text())
    assert manifest["status"] == "experimental"
    assert manifest["channels"] == public["channels"] == list(CHANNELS)
    assert manifest["version"] == public["version"]


def test_source_compilation_and_import_boundaries():
    directory = Path(__file__).parents[1]
    for path in directory.glob("*.py"):
        compile(path.read_text(), str(path), "exec")
    for filename, forbidden in (("baseline.py", {"kernel", "world", "generator", "reference"}),
                                 ("reference.py", {"kernel", "protocol", "world", "generator"})):
        tree = ast.parse((directory/filename).read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                assert not any(word in (node.module or "").split(".") for word in forbidden)
            if isinstance(node, ast.Import):
                assert not any(word in alias.name.split(".") for alias in node.names for word in forbidden)
    assert not any(isinstance(node, (ast.Import, ast.ImportFrom)) for node in ast.walk(ast.parse((directory/"__init__.py").read_text())))


def test_baseline_synthetic_records_only():
    raw = spec()
    assert np.array_equal(baseline([], raw), [[1, 0, 0]]*3)
    observation = {"axis": raw["times_ms"], "channels": list(CHANNELS),
                   "values": [[1.01, .02, 0], [.7, .1, 0], [.2, -.1, 0]]}
    record = {"spec": raw, "observation": observation}
    before = copy.deepcopy(record)
    prediction = baseline([record], raw)
    assert prediction[0] == raw["initial_magnetization"]
    assert np.allclose(prediction[1:], observation["values"][1:], rtol=0, atol=1e-15)
    assert record == before
    shifted = {"initial_magnetization": [1, 0, 0], "times_ms": [6.25], "detuning_hz": 40}
    assert np.allclose(baseline([], shifted), [[0, 1, 0]], atol=1e-15)
    pulse = {"initial_magnetization": [0, 1, 0], "times_ms": [1],
             "pulses": [{"time_ms": 1, "angle_rad": math.pi/2, "phase_rad": 0}]}
    assert np.allclose(baseline([], pulse), [[0, 0, 1]], atol=1e-15)


@pytest.mark.parametrize("bad", [None, [{}], [False], [{"spec": spec(), "observation": {}}]])
def test_baseline_rejects_bad_records(bad):
    with pytest.raises(ValueError):
        baseline(bad, spec())


@pytest.mark.parametrize("value", [True, -1, 1.5, 2**63])
def test_seed_validation_without_world(value):
    with pytest.raises(ValueError):
        integer(value, "seed")
