"""Independent physics checks and public-contract regressions."""

import ast
import copy
import itertools
import json
from pathlib import Path

import numpy as np
import pytest
from scipy.integrate import solve_ivp

from env.hysteresis_material import World, baseline
from env.hysteresis_material.calibrate import loop_area, loop_spec, memory_spec
from env.hysteresis_material.protocol import example


def _world(family):
    return World(7 if family == "relaxation" else 1439)


def _reference(world, spec):
    """Separate DOP853 solve with independently written equations and segmentation."""
    def propagate(initial, duration, h0, h1, sample):
        def rhs(t, y):
            field = h0 + (h1 - h0) * t / duration
            if world._family == "relaxation":
                return [(np.tanh(world._coupling * field + world._bias) - y[0]) / world._tau]
            return [(-y[0]**3 + world._a * y[0] + world._bias + world._coupling * field) / world._tau]
        solution = solve_ivp(rhs, [0.0, duration], [initial], method="DOP853", rtol=1e-11,
                             atol=1e-13, max_step=0.15, dense_output=True)
        assert solution.success
        return float(solution.y[0, -1]), solution.sol(sample)[0] if len(sample) else []
    field = -1.5 if spec["reset"] == "negative" else 1.5
    state, _ = propagate(0.0, 300.0, field, field, [])
    for step in spec["preparation"]:
        state, _ = propagate(state, step["duration"], step["field"], step["field"], [])
    times = np.asarray(spec["times"])
    values = np.full(len(times), np.nan)
    values[times == 0] = state
    knots = copy.deepcopy(spec["protocol"])
    if knots[-1]["time"] < times[-1]:
        knots.append({"time": times[-1], "field": knots[-1]["field"]})
    for left, right in zip(knots, knots[1:]):
        chosen = (times > left["time"]) & (times <= right["time"])
        state, sampled = propagate(state, right["time"] - left["time"], left["field"], right["field"], times[chosen] - left["time"])
        values[chosen] = sampled
    return (world._gain * values + world._offset).reshape(-1, 1)


@pytest.mark.parametrize("family", ["relaxation", "bistable"])
def test_hysteresis_independent_solver_preparation_ramps_dwells(family):
    world = _world(family)
    spec = {"reset": "positive", "preparation": [{"field": -0.4, "duration": 12.0}, {"field": 0.2, "duration": 3.0}],
            "protocol": [{"time": 0.0, "field": -1.2}, {"time": 13.0, "field": 0.8},
                         {"time": 22.0, "field": 0.8}, {"time": 40.0, "field": -0.7}],
            "times": [0.0, 0.01, 4.0, 13.0, 19.0, 22.0, 30.0, 40.0, 55.0]}
    np.testing.assert_allclose(world.run(spec)["values"], _reference(world, spec), atol=2e-7, rtol=2e-7)


def test_hysteresis_monostable_constant_field_analytic_limit():
    world = _world("relaxation")
    spec = memory_spec("negative")
    reset_eq = np.tanh(-1.5 * world._coupling + world._bias)
    initial = reset_eq * (1.0 - np.exp(-300.0 / world._tau))
    equilibrium = np.tanh(world._bias)
    expected = equilibrium + (initial - equilibrium) * np.exp(-np.asarray(spec["times"]) / world._tau)
    np.testing.assert_allclose(np.asarray(world.run(spec)["values"])[:, 0], world._gain * expected + world._offset, atol=1e-13)


@pytest.mark.parametrize("initial", [-1.8, -0.2, 0.2, 1.8])
def test_hysteresis_landau_zero_field_analytic_limit(initial):
    world = _world("bistable")
    world._bias = 0.0
    times = np.linspace(0.0, 20.0, 81)
    values, _ = world._advance(initial, 20.0, 0.0, 0.0, times)
    expected = np.sign(initial) * np.sqrt(world._a / (1.0 + (world._a / initial**2 - 1.0) * np.exp(-2 * world._a * times / world._tau)))
    np.testing.assert_allclose(values, expected, atol=3e-8, rtol=3e-8)


@pytest.mark.parametrize("family", ["relaxation", "bistable"])
def test_hysteresis_constant_field_dissipates_potential(family):
    world = _world(family)
    field = 0.15
    values, _ = world._advance(-1.5, 80.0, field, field, np.linspace(0.0, 80.0, 401))
    if family == "relaxation":
        potential = 0.5 * (values - np.tanh(world._coupling * field + world._bias))**2
    else:
        potential = values**4 / 4.0 - world._a * values**2 / 2.0 - (world._coupling * field + world._bias) * values
    assert np.max(np.diff(potential)) < 1e-8


def test_hysteresis_invariant_interval_and_reset_corners():
    for family in ("relaxation", "bistable"):
        world = _world(family)
        corners = itertools.product((0.75, 1.15), (5.0, 14.0), (0.6, 0.9), (-0.025, 0.025)) if family == "bistable" else itertools.product((0.0,), (5.0, 14.0), (1.0, 1.8), (-0.06, 0.06))
        for a, tau, coupling, bias in corners:
            world._a, world._tau, world._coupling, world._bias = a, tau, coupling, bias
            for field in (-1.5, 1.5):
                assert world._rhs(-2.0, field) > 0.0
                assert world._rhs(2.0, field) < 0.0
                reset_ends = []
                for initial in (-2.0, 2.0):
                    samples, final = world._advance(initial, 300.0, field, field, np.linspace(0.0, 300.0, 101))
                    assert np.max(np.abs(samples)) <= 2.0 + 1e-8
                    reset_ends.append(final)
                # Numeric evidence at all range corners, not an exact-equilibrium claim.
                assert abs(reset_ends[0] - reset_ends[1]) < 1e-8


@pytest.mark.parametrize("seed", [7, 46, 1439, 8743])
def test_hysteresis_development_mechanisms_are_diagnosable(seed):
    world = World(seed)
    fast, slow = loop_spec(20.0), loop_spec(1200.0)
    fast_area, slow_area = loop_area(fast, world.run(fast)), loop_area(slow, world.run(slow))
    negative = world.run(memory_spec("negative"))["values"][-1][0]
    positive = world.run(memory_spec("positive"))["values"][-1][0]
    assert fast_area > 0.5  # Far above quadrature measurement noise in both families.
    if world._family == "relaxation":
        assert slow_area / fast_area < 0.08
        assert abs(positive - negative) < 1e-8
    else:
        assert slow_area > 0.8
        assert abs(positive - negative) > 1.4
        quasistatic = 1.5 * world._gain * world._a**2 / world._coupling
        # Finite-rate switching retains a bifurcation delay even on a long
        # sweep. It approaches the nonzero static area from above.
        assert quasistatic < slow_area < 1.8 * quasistatic


@pytest.mark.parametrize("family", ["relaxation", "bistable"])
def test_hysteresis_extreme_controls_no_clipping_or_instability(family):
    world = _world(family)
    times = np.linspace(0.0, 3600.0, 129).tolist()
    spec = {"reset": "positive", "preparation": [{"field": -1.5, "duration": 300.0}, {"field": 1.5, "duration": 300.0}],
            "protocol": [{"time": i * 0.05, "field": 1.5 * (-1)**i} for i in range(20)], "times": times}
    values = np.asarray(world.run(spec)["values"])
    assert values.shape == (129, 1)
    assert np.isfinite(values).all() and np.max(np.abs(values)) < 2.5
    assert "clip(" not in Path(__import__("env.hysteresis_material.world", fromlist=["__file__"]).__file__).read_text()


def test_hysteresis_public_boundary_shape_and_seed_independence():
    worlds = [World(seed) for seed in (7, 46, 1439, 8743)]
    descriptions = [world.describe() for world in worlds]
    assert all(description == descriptions[0] for description in descriptions)
    serialized = json.dumps(descriptions[0], allow_nan=False).lower()
    for forbidden in ("landau", "bistable", "relaxation", "tanh", "_family", "_seed", "_tau", "coupling", "quartic"):
        assert forbidden not in serialized
    for world in worlds:
        for spec in world.describe()["examples"]:
            assert world.cost(spec) == 1
            result = world.run(spec, noise_key="public")
            assert set(result) == {"axis", "channels", "values"}
            assert result["axis"] == world.validate(spec)["times"]
            assert result["channels"] == ["response"]
            assert np.asarray(result["values"]).shape == (len(spec["times"]), 1)
            json.dumps(result, allow_nan=False)
    descriptions[0]["examples"][0]["reset"] = "changed"
    assert worlds[0].describe()["examples"][0]["reset"] == "negative"


def test_hysteresis_reproducibility_noise_and_observation_grid_invariance():
    world = World(1439)
    spec = example()
    assert world.run(spec) == World(1439).run(spec)
    assert world.run(spec, noise_key="a") == world.run(spec, noise_key="a")
    assert world.run(spec, noise_key="a") != world.run(spec, noise_key="b")
    assert world.run(spec) != World(8743).run(spec)
    augmented = dict(spec, times=sorted(set(spec["times"] + [0.01, 1.1, 49.0, 80.0])))
    original = np.asarray(world.run(spec)["values"])
    later = np.asarray(world.run(augmented)["values"])
    np.testing.assert_allclose(original, later[[augmented["times"].index(t) for t in spec["times"]]], atol=1e-10, rtol=1e-10)
    # Run order does not carry material state across fresh experiments.
    world.run(memory_spec("positive"))
    assert world.run(spec) == World(1439).run(spec)


@pytest.mark.parametrize("bad", [None, [], {}, {"extra": 1}])
def test_hysteresis_rejects_wrong_top_level(bad):
    with pytest.raises(ValueError):
        World(7).validate(bad)


@pytest.mark.parametrize("value", [True, None, "1", float("nan"), float("inf"), 10**1000, -1.0, 3600.1])
def test_hysteresis_rejects_nonfinite_bool_overflow_and_bounds(value):
    spec = example()
    spec["times"] = [value]
    with pytest.raises(ValueError):
        World(7).validate(spec)


@pytest.mark.parametrize("mutate", [
    lambda s: s.update(reset=[]),
    lambda s: s.update(times=[]),
    lambda s: s.update(times=[0, 0, 60]),
    lambda s: s.update(times=[60, 0]),
    lambda s: s.update(times=list(range(130))),
    lambda s: s.update(protocol=[]),
    lambda s: s["protocol"][0].update(time=1),
    lambda s: s["protocol"][0].update(field=1.51),
    lambda s: s["protocol"][1].update(time=0.001),
    lambda s: s["protocol"][1].update(extra=1),
    lambda s: s["protocol"][-1].update(time=61),
    lambda s: s.update(preparation=[{"field": 0, "duration": 300}] * 3),
    lambda s: s.update(preparation=[{"field": 0, "duration": 0}]),
    lambda s: s.update(preparation=[{"field": True, "duration": 1}]),
    lambda s: s.update(preparation=[{"field": 0, "duration": 1}] * 7),
])
def test_hysteresis_rejects_malformed_protocol_and_work(mutate):
    spec = example()
    mutate(spec)
    with pytest.raises(ValueError):
        World(7).validate(spec)


@pytest.mark.parametrize("bad_seed", [True, -1, 2**63, 1.5, "7", None])
def test_hysteresis_seed_validation(bad_seed):
    with pytest.raises(ValueError):
        World(bad_seed)


def test_hysteresis_panels_cover_rates_histories_and_holdout_kinds():
    world = World(7)
    for kind in ("development", "conditions", "interventions"):
        panel = world.panel(239, kind, 8)
        assert panel == World(1439).panel(239, kind, 8)
        assert panel == world.panel(239, kind, 8)
        assert panel != world.panel(240, kind, 8)
        assert len({json.dumps(spec, sort_keys=True) for spec in panel}) == 8
        assert {spec["reset"] for spec in panel} == {"negative", "positive"}
        for spec in panel:
            assert world.validate(spec) == spec
            assert np.isfinite(world.run(spec)["values"]).all()
        if kind == "interventions":
            for spec in panel:
                fields = [k["field"] for k in spec["protocol"]]
                changes = np.diff(fields)
                assert any(changes == 0) and any(changes > 0) and any(changes < 0)
        else:
            durations = [spec["times"][-1] for spec in panel]
            assert min(durations) < 50 and max(durations) > 400
            assert any(spec["preparation"] for spec in panel)
    for invalid in ("test", None, []):
        with pytest.raises(ValueError):
            world.panel(1, invalid)
    for count in (0, 129, True, 1.5):
        with pytest.raises(ValueError):
            world.panel(1, "conditions", count)


def test_hysteresis_baseline_public_records_only_and_exact_neighbor(monkeypatch):
    spec = example()
    observation = {"axis": spec["times"], "channels": ["response"],
                   "values": [[float(i) / 10] for i in range(len(spec["times"]))]}
    record = {"spec": spec, "observation": observation}
    before = copy.deepcopy(record)
    monkeypatch.setattr(World, "run", lambda *a, **k: (_ for _ in ()).throw(AssertionError("no simulator access")))
    assert baseline([], spec) == [[0.0] for _ in spec["times"]]
    assert baseline([record], spec) == observation["values"]
    assert record == before
    package = Path(__import__("env.hysteresis_material.baseline", fromlist=["__file__"]).__file__)
    tree = ast.parse(package.read_text())
    imported = [node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
    assert imported == ["protocol"]
    for bad in ([{}], [{"spec": spec, "observation": {}}], [dict(record, observation=dict(observation, values=[[1.0]]))]):
        with pytest.raises(ValueError):
            baseline(bad, spec)


def test_hysteresis_single_initial_observation_and_key_validation():
    world = World(7)
    spec = {"reset": "negative", "preparation": [], "protocol": [{"time": 0, "field": 0}], "times": [0]}
    assert len(world.run(spec)["values"]) == 1
    for key in (True, 3, {}, "x" * 257):
        with pytest.raises(ValueError):
            world.run(spec, noise_key=key)


def test_hysteresis_observation_noise_has_declared_scale():
    world = World(7)
    spec = {"reset": "negative", "preparation": [], "protocol": [{"time": 0, "field": 0}], "times": [0]}
    clean = world.run(spec)["values"][0][0]
    deviations = np.asarray([world.run(spec, noise_key="noise-check-%d" % index)["values"][0][0] - clean
                             for index in range(256)])
    assert abs(deviations.mean()) < 0.0012
    assert 0.0048 < deviations.std(ddof=1) < 0.0072
