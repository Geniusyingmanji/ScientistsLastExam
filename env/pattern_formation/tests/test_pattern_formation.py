import ast
import copy
import json
from pathlib import Path

import numpy as np
import pytest

from env.pattern_formation.baseline import baseline
from env.pattern_formation.kernel import Kernel, Parameters, STRUCTURES
from env.pattern_formation.protocol import (CHANNELS, GRID_SIZE, PROBE_COUNT, describe,
                                            example, initial_values, validate_spec)
from env.pattern_formation.reference import radau_reference
from env.pattern_formation.world import World


def short_spec():
    spec = example()
    spec["times"] = [0., .1, .5, 1.]
    return spec


@pytest.mark.parametrize("path,value", [
    (("length",), True), (("length",), 11.9), (("length",), 32.1), (("length",), float("nan")),
    (("drive",), float("inf")), (("drive",), -.401), (("drive",), "0"),
    (("initial", "mean"), False), (("initial", "mean"), .201),
    (("initial", "modes", 0, "mode"), 1.0), (("initial", "modes", 0, "mode"), True),
    (("initial", "modes", 0, "mode"), 9), (("initial", "modes", 0, "amplitude"), np.bool_(True)),
    (("initial", "modes", 0, "phase"), 3.15), (("initial", "modes"), "none"),
    (("times",), []), (("times",), [0., 0.]), (("times",), [1., .5]),
    (("times",), [False]), (("times",), [61.]), (("times",), [0.]*34),
])
def test_rejects_malformed_controls(path, value):
    spec = example()
    target = spec
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    with pytest.raises(ValueError):
        validate_spec(spec)


@pytest.mark.parametrize("mutate", [
    lambda s: s.update(extra=1), lambda s: s["initial"].update(extra=1),
    lambda s: s["initial"]["modes"][0].update(extra=1),
    lambda s: s["initial"]["modes"].append(dict(s["initial"]["modes"][0])),
    lambda s: s["initial"].update(modes=[{"mode": i, "amplitude": .1, "phase": 0.} for i in (1, 2, 3, 4)]),
    lambda s: s["initial"].update(modes=[{"mode": i, "amplitude": .16, "phase": 0.} for i in (1, 2)]),
])
def test_rejects_extra_duplicate_or_oversized_fields(mutate):
    spec = example()
    mutate(spec)
    with pytest.raises(ValueError):
        validate_spec(spec)


def test_validation_is_canonical_and_detached():
    spec = example()
    spec["initial"]["modes"].reverse()
    before = copy.deepcopy(spec)
    result = validate_spec(spec)
    assert spec == before
    assert result["initial"]["modes"][0]["mode"] == 3
    result["initial"]["modes"][0]["amplitude"] = 0.
    assert spec == before


def test_public_contract_independent_of_instance_and_families():
    assert World(7).describe() == World(46).describe() == describe()
    encoded = json.dumps(describe())
    for private in STRUCTURES + ("r0", "cubic", "q0", "Swift", "Hohenberg", "forcing_mode", "private_parameters"):
        assert private not in encoded
    for spec in describe()["examples"]:
        validate_spec(spec)
    assert len(CHANNELS) == PROBE_COUNT == 16


def test_cost_maximum_and_invalid_seed_noise_keys():
    spec = example()
    spec["times"] = np.linspace(0, 60, 33).tolist()
    spec["initial"]["modes"].append({"mode": 5, "amplitude": .05, "phase": 0.})
    assert World(7).cost(spec) == 62
    for seed in (True, -1, 1.5, "7"):
        with pytest.raises(ValueError):
            World(seed)
    for key in (True, 1, [], "x"*257):
        with pytest.raises(ValueError):
            World(7).run(spec, noise_key=key)


def test_reset_noise_reproducibility_and_unclipped_sign():
    spec = example()
    spec["times"] = [0.]
    spec["initial"] = {"mean": 0., "modes": []}
    world = World(7)
    clean = world.run(spec)
    a = world.run(spec, noise_key="a")
    assert a == world.run(spec, noise_key="a")
    b = world.run(spec, noise_key="b")
    assert a != b
    assert clean["values"] == [[0.]*16]
    assert min(a["values"][0]) < 0 < max(a["values"][0])
    assert a["channels"] == list(CHANNELS)


def test_known_reset_and_unobserved_nyquist_quadrature():
    spec = example()
    spec["times"] = [0.]
    observed = np.asarray(World(7).run(spec)["values"])[0]
    np.testing.assert_array_equal(observed, initial_values(validate_spec(spec), GRID_SIZE)[::4])
    spec["initial"] = {"mean": 0., "modes": [{"mode": 8, "amplitude": .2, "phase": 0.}]}
    assert np.max(np.abs(initial_values(spec))) < 1e-14
    assert np.max(np.abs(initial_values(spec, GRID_SIZE))) > .19


def test_sampling_schedule_does_not_control_evolution():
    world = World(46)
    spec = short_spec()
    first = world.run(spec)
    extra = copy.deepcopy(spec)
    extra["times"] = [0., .05, .1, .3, .5, .7, 1.]
    second = world.run(extra)
    np.testing.assert_array_equal(first["values"], np.asarray(second["values"])[[0, 2, 4, 6]])


def test_linear_operator_and_analytic_jacobian():
    spec = short_spec()
    p = Parameters(forcing=.04)
    matrix, force, eigenvalues = Kernel(p).operator(spec)
    np.testing.assert_allclose(matrix, matrix.T, atol=1e-10)
    mode = np.sin(2*np.pi*3*np.arange(GRID_SIZE)/GRID_SIZE)
    np.testing.assert_allclose(matrix.dot(mode), eigenvalues[3]*mode, atol=2e-10)
    state = initial_values(spec, GRID_SIZE)
    direction = np.cos(np.arange(GRID_SIZE))
    epsilon = 1e-6
    rhs = lambda y: matrix.dot(y)-p.cubic*y**3+force
    finite_difference = (rhs(state+epsilon*direction)-rhs(state-epsilon*direction))/(2*epsilon)
    jacobian = matrix-np.diag(3*p.cubic*state**2)
    np.testing.assert_allclose(finite_difference, jacobian.dot(direction), rtol=1e-7, atol=1e-6)


def test_independent_radau_matches_finite_ode():
    spec = short_spec()
    p = Parameters(r0=-.12, forcing=.04)
    actual, _ = Kernel(p).trajectory(validate_spec(spec))
    expected, _ = radau_reference(p, validate_spec(spec))
    np.testing.assert_allclose(actual, expected, atol=2e-7, rtol=2e-6)


def test_exact_zero_is_invariant_even_with_positive_growth():
    spec = short_spec()
    spec["initial"] = {"mean": 0., "modes": []}
    values, _ = Kernel(Parameters()).trajectory(validate_spec(spec))
    np.testing.assert_array_equal(values, 0.)


def test_work_limit_fails_closed(monkeypatch):
    import env.pattern_formation.kernel as module
    monkeypatch.setattr(module, "MAX_EVALUATIONS", 0)
    with pytest.raises(RuntimeError, match="work limit"):
        Kernel(Parameters()).trajectory(validate_spec(short_spec()))


def test_baseline_uses_only_public_records_and_assigned_initial():
    source = short_spec()
    values = np.tile(initial_values(source), (4, 1)) + np.asarray([0., .1, .2, .3])[:, None]
    record = {"spec": source, "observation": {"axis": list(source["times"]), "channels": list(CHANNELS), "values": values.tolist()}}
    np.testing.assert_allclose(baseline([record], source), values, atol=1e-15)
    empty = np.asarray(baseline([], source))
    np.testing.assert_allclose(empty, np.tile(initial_values(source), (4, 1)))
    malformed = copy.deepcopy(record)
    malformed["observation"]["values"][0][0] = float("nan")
    with pytest.raises(ValueError):
        baseline([malformed], source)
    malformed = copy.deepcopy(record)
    malformed["observation"]["axis"][0] = .01
    with pytest.raises(ValueError):
        baseline([malformed], source)


@pytest.mark.parametrize("kind", ["development", "conditions", "interventions"])
def test_panels_reproducible_public_and_parameter_independent(kind):
    first = World(7).panel(123, kind, 4)
    assert first == World(8743).panel(123, kind, 4)
    assert first != World(7).panel(124, kind, 4)
    for spec in first:
        assert spec == validate_spec(spec)
    assert len({json.dumps(spec, sort_keys=True) for spec in first}) == 4


def test_source_python38_compatible():
    for path in Path(__file__).resolve().parents[1].rglob("*.py"):
        ast.parse(path.read_text(), filename=str(path), feature_version=(3, 8))
