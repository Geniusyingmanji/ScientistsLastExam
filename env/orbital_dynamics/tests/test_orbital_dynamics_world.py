"""Independent polar equations, analytic limits and public protocol checks."""

import ast
import copy
import json
from pathlib import Path

import numpy as np
import pytest

from env.orbital_dynamics import World, baseline
from env.orbital_dynamics import kernel as kernel_module
from env.orbital_dynamics.kernel import Kernel, Parameters, STRUCTURES, MAX_EVALUATIONS
from env.orbital_dynamics.protocol import example, validate_spec
from env.orbital_dynamics.reference import polar_reference, energy


def apparatus(parameters):
    world = World(7)
    world._kernel = Kernel(parameters)
    return world


@pytest.mark.parametrize("parameters", [Parameters(), Parameters(exponent=1.48), Parameters(exponent=2.57), Parameters(drag=.075)])
def test_orbital_independent_polar_radau_and_cartesian_dop853_with_impulses(parameters):
    world = apparatus(parameters)
    spec = world.validate({"position": [1.1, .4], "velocity": [-.3, .8],
                           "times": [0, .2, .7, 1.3, 2.6, 4, 6],
                           "impulses": [{"time": .7, "delta_v": [.13, -.04]}, {"time": 2.1, "delta_v": [-.08, .03]}]})
    expected, _, _ = polar_reference(spec, parameters)
    np.testing.assert_allclose(world.run(spec)["values"], expected, rtol=3e-8, atol=3e-9)


@pytest.mark.parametrize("power", [1.0, 1.45, 2., 2.6])
def test_orbital_exact_circular_orbit_and_conservative_invariants(power):
    p, r = Parameters(mu=.95, exponent=power), 1.2
    angular_frequency = np.sqrt(p.mu / (r*r + p.softening**2)**((power + 1) / 2))
    times = np.linspace(0, 12, 65)
    spec = {"position": [r, 0], "velocity": [0, r*angular_frequency], "times": times.tolist()}
    values = np.asarray(apparatus(p).run(spec)["values"])
    theta = times * angular_frequency
    expected = np.column_stack([r*np.cos(theta), r*np.sin(theta), -r*angular_frequency*np.sin(theta), r*angular_frequency*np.cos(theta)])
    np.testing.assert_allclose(values, expected, atol=2e-9, rtol=2e-9)
    np.testing.assert_allclose(energy(values, p), energy(values, p)[0], atol=3e-10)
    momentum = values[:, 0]*values[:, 3] - values[:, 1]*values[:, 2]
    np.testing.assert_allclose(momentum, momentum[0], atol=3e-10)


def test_orbital_unified_potential_gradient_and_log_limit():
    position = np.asarray([[.7, -.4], [1.8, .2]])
    for power in (1., 1.45, 2., 2.6):
        kernel = Kernel(Parameters(exponent=power))
        for row in position:
            gradient = []
            for index in range(2):
                shift = np.zeros(2)
                shift[index] = 1e-5
                gradient.append((kernel.potential(row + shift) - kernel.potential(row - shift)) / 2e-5)
            np.testing.assert_allclose(-np.asarray(gradient), kernel.derivative(0, [row[0], row[1], 0, 0])[2:], atol=3e-10)
    # The zero-at-infinity convention diverges by a constant as p -> 1;
    # potential differences converge to the logarithmic convention.
    logarithmic = Kernel(Parameters(exponent=1)).potential(position)
    near = Kernel(Parameters(exponent=1.000001)).potential(position)
    assert near[1] - near[0] == pytest.approx(logarithmic[1] - logarithmic[0], rel=2e-6)


def test_orbital_drag_energy_work_and_angular_momentum_decay():
    p = Parameters(mu=1.03, drag=.08)
    spec = validate_spec({"position": [1.3, 0], "velocity": [.12, .8], "times": np.linspace(0, 8, 33).tolist()})
    values = np.asarray(apparatus(p).run(spec)["values"])
    reference, drag_work, _ = polar_reference(spec, p)
    momentum = values[:, 0]*values[:, 3] - values[:, 1]*values[:, 2]
    np.testing.assert_allclose(momentum, momentum[0] * np.exp(-p.drag*np.asarray(spec["times"])), atol=2e-9)
    actual_energy = energy(values, p)
    np.testing.assert_allclose(actual_energy - actual_energy[0], drag_work, atol=3e-9)
    assert np.all(np.diff(actual_energy) < 0)
    np.testing.assert_allclose(values, reference, atol=8e-9)


@pytest.mark.parametrize("drag", [0., .08])
def test_orbital_zero_attraction_analytic_free_motion_with_impulses(drag):
    world = apparatus(Parameters(mu=0, drag=drag))
    spec = world.validate(example())
    rows = []
    for t in spec["times"]:
        relaxation = (1 - np.exp(-drag*t)) / drag if drag else t
        position = np.asarray(spec["position"]) + relaxation * np.asarray(spec["velocity"])
        velocity = np.asarray(spec["velocity"]) * np.exp(-drag*t)
        for event in spec["impulses"]:
            if t >= event["time"]:
                dt = t - event["time"]
                factor = (1 - np.exp(-drag*dt)) / drag if drag else dt
                position += factor * np.asarray(event["delta_v"])
                velocity += np.exp(-drag*dt) * np.asarray(event["delta_v"])
        rows.append(position.tolist() + velocity.tolist())
    np.testing.assert_allclose(world.run(spec)["values"], rows, atol=2e-11)


def test_orbital_impulse_post_sample_and_energy_momentum_jump():
    world = apparatus(Parameters(exponent=2.4))
    spec = {"position": [1.1, 0], "velocity": [0, .9], "times": [0, 1, 2], "impulses": []}
    before = np.asarray(world.run(spec)["values"])
    delta = np.asarray([.15, -.11])
    spec["impulses"] = [{"time": 1, "delta_v": delta.tolist()}]
    after = np.asarray(world.run(spec)["values"])
    np.testing.assert_allclose(after[1, :2], before[1, :2], atol=2e-10)
    np.testing.assert_allclose(after[1, 2:] - before[1, 2:], delta, atol=2e-10)
    p = world._kernel.parameters
    energy_jump = energy(after, p)[1] - energy(before, p)[1]
    assert energy_jump == pytest.approx(np.dot(before[1, 2:], delta) + np.dot(delta, delta)/2, abs=3e-10)
    momentum_jump = (after[1, 0]*after[1, 3] - after[1, 1]*after[1, 2]) - (before[1, 0]*before[1, 3] - before[1, 1]*before[1, 2])
    assert momentum_jump == pytest.approx(before[1, 0]*delta[1] - before[1, 1]*delta[0], abs=3e-10)
    assert np.linalg.norm(after[2, :2] - before[2, :2]) > .05


@pytest.mark.parametrize("matrix", [np.asarray([[0, -1], [1, 0]]), np.asarray([[1, 0], [0, -1]])])
def test_orbital_rotation_and_reflection_equivariance(matrix):
    world, spec = World(46), example()
    transformed = copy.deepcopy(spec)
    for field in ("position", "velocity"):
        transformed[field] = matrix.dot(spec[field]).tolist()
    for event in transformed["impulses"]:
        event["delta_v"] = matrix.dot(event["delta_v"]).tolist()
    original = np.asarray(world.run(spec)["values"])
    expected = np.column_stack((original[:, :2].dot(matrix.T), original[:, 2:].dot(matrix.T)))
    np.testing.assert_allclose(world.run(transformed)["values"], expected, atol=4e-9)


def test_orbital_time_reversal_only_in_conservative_case():
    spec = {"position": [1.2, 0], "velocity": [.05, .9], "times": [0, 1, 2]}
    for drag in (0., .08):
        world = apparatus(Parameters(drag=drag))
        end = np.asarray(world.run(spec)["values"])[-1]
        reverse = {"position": end[:2].tolist(), "velocity": (-end[2:]).tolist(), "times": [0, 1, 2]}
        returned = np.asarray(world.run(reverse)["values"])[-1]
        error = np.linalg.norm(returned[:2] - spec["position"])
        assert error < 1e-8 if drag == 0 else error > .02


def test_orbital_measurement_grid_does_not_change_physics():
    world, spec = World(1439), example()
    expected = world.run(spec)
    dense = copy.deepcopy(spec)
    dense["times"] = sorted(set(spec["times"] + [.01, .1, .3, 2.7, 3.01, 7.7]))
    actual = world.run(dense)
    extracted = [actual["values"][dense["times"].index(t)] for t in spec["times"]]
    np.testing.assert_array_equal(extracted, expected["values"])


def test_orbital_numerical_work_failure_is_bounded_and_never_silent_fallback(monkeypatch):
    world = World(7)
    monkeypatch.setattr(kernel_module, "MAX_EVALUATIONS", 1)
    with pytest.raises(RuntimeError, match="^numerical work limit exceeded$"):
        world.run(example())


@pytest.mark.parametrize("seed", [7, 46, 1439, 8743])
def test_orbital_boundary_legal_specs_and_center_crossing_are_finite_bounded_work(seed):
    world = World(seed)
    extremes = [
        {"position": [.75, 0], "velocity": [0, 0], "times": np.linspace(0, 12, 65).tolist()},
        {"position": [2, 0], "velocity": [1.5, 0], "times": [0, 1, 4, 8, 12],
         "impulses": [{"time": .01, "delta_v": [.5, 0]}, {"time": 12, "delta_v": [.3, 0]}]},
        {"position": [0, 1], "velocity": [0, -1.5], "times": [0]},
        {"position": [-2, 0], "velocity": [0, 1.5], "times": [12]}]
    for spec in extremes:
        spec = world.validate(spec)
        values, work = world._kernel.trajectory(spec)
        assert values.shape == (len(spec["times"]), 4) and np.isfinite(values).all()
        assert work["rhs_evaluations"] < MAX_EVALUATIONS
        assert 1 <= world.cost(spec) <= 91
    # The radial, zero-angular-momentum trajectory passes through rather than
    # terminating or dividing by its radius at the softened center.
    values = np.asarray(world.run(extremes[0])["values"])
    assert np.min(values[:, 0]) < 0
    np.testing.assert_array_equal(values[:, [1, 3]], 0)


@pytest.mark.parametrize("power", [1.35, 2., 2.65])
@pytest.mark.parametrize("drag", [0., .1])
def test_orbital_parameter_extremes_radial_crossing_energy_and_global_bounds(power, drag):
    parameters = Parameters(mu=1.2, exponent=power, drag=drag)
    spec = validate_spec({"position": [.75, 0], "velocity": [-1.5, 0], "times": np.linspace(0, 12, 65).tolist()})
    values, work = Kernel(parameters).trajectory(spec)
    assert work["rhs_evaluations"] < MAX_EVALUATIONS
    assert np.linalg.norm(values[:, 2:], axis=1).max() < 4.9
    assert np.linalg.norm(values[:, :2], axis=1).max() < 61
    energies = energy(values, parameters)
    if drag == 0:
        np.testing.assert_allclose(energies, energies[0], atol=2e-8, rtol=0)
    else:
        assert np.all(np.diff(energies) < 2e-8)
        assert energies[-1] < energies[0] - .01


@pytest.mark.parametrize("bad", [None, {}, {"times": []}, {"position": [0, 0]}, {"position": [2, 2]},
                                {"velocity": [True, 0]}, {"velocity": [float("nan"), 0]}, {"velocity": [float("inf"), 0]},
                                {"velocity": [10**1000, 0]}, {"times": [1, 1]}, {"times": [0, 12.1]}, {"times": [0]*66},
                                {"unknown": 1}, {"impulses": [{"time": 0, "delta_v": [.1, 0]}]},
                                {"impulses": [{"time": 9, "delta_v": [.1, 0]}]},
                                {"impulses": [{"time": 1, "delta_v": [.5, .1]}]},
                                {"impulses": [{"time": 1, "delta_v": [.5, 0]}, {"time": 2, "delta_v": [.5, 0]}]},
                                {"impulses": [{"time": 1, "delta_v": [.1, 0]}, {"time": 1, "delta_v": [0, .1]}]}])
def test_orbital_invalid_inputs_rejected_before_numerics_and_do_not_mutate(bad, monkeypatch):
    world, spec = World(7), example()
    invalid = bad if bad is None or bad == {} else dict(spec, **bad)
    original = copy.deepcopy(spec)
    monkeypatch.setattr(world._kernel, "trajectory", lambda *_: pytest.fail("invalid request reached numerical kernel"))
    for operation in (world.validate, world.cost, world.run):
        with pytest.raises(ValueError):
            operation(invalid)
    assert spec == original


def test_orbital_seed_noise_reproducibility_and_public_private_separation():
    world, spec = World(7), example()
    assert world.run(spec) == World(7).run(spec)
    assert world.run(spec, noise_key="replica-1") == World(7).run(spec, noise_key="replica-1")
    assert world.run(spec, noise_key="replica-1") != world.run(spec, noise_key="replica-2")
    reordered = {key: spec[key] for key in reversed(list(spec))}
    assert world.run(spec, noise_key="replica-1") == world.run(reordered, noise_key="replica-1")
    assert world.run(spec) != World(46).run(spec)
    descriptions = [json.dumps(World(seed).describe(), sort_keys=True) for seed in range(24)]
    assert len(set(descriptions)) == 1
    assert {World(seed).operator_stratum() for seed in range(64)} == set(STRUCTURES)
    assert all(label not in descriptions[0] for label in STRUCTURES)
    assert "mu" not in world.describe() and "private" not in world.run(spec)
    assert set(world.run(spec)) == {"axis", "channels", "values"}
    changed = world.describe()
    changed["examples"][0]["times"].append(999)
    assert changed != world.describe()
    for key in (True, 7, [], "x"*257):
        with pytest.raises(ValueError):
            world.run(spec, noise_key=key)
    for seed in (-1, True, 1.5, 2**63):
        with pytest.raises(ValueError):
            World(seed)


def test_orbital_noise_is_unclipped_additive_including_known_initial_state():
    world = World(7)
    spec = {"position": [1, 0], "velocity": [0, 0], "times": [0]}
    values = np.asarray([world.run(spec, noise_key="n-%d" % i)["values"][0] for i in range(800)])
    error = values - [1, 0, 0, 0]
    assert np.all(error.min(axis=0) < 0) and np.all(error.max(axis=0) > 0)
    np.testing.assert_allclose(error.std(axis=0), world.noise_std, rtol=.12)


def test_orbital_panels_deterministic_parameter_blind_and_distinct():
    world = World(7)
    panels = {}
    for kind in ("development", "conditions", "interventions"):
        panels[kind] = world.panel(46, kind, 8)
        assert panels[kind] == World(8743).panel(46, kind, 8)
        for spec in panels[kind]:
            assert spec == world.validate(spec)
        assert panels[kind] != world.panel(47, kind, 8)
    assert all(not spec["impulses"] for spec in panels["conditions"])
    assert all(spec["impulses"] for spec in panels["interventions"])
    fingerprints = [set(json.dumps(s, sort_keys=True) for s in rows) for rows in panels.values()]
    assert not fingerprints[1].intersection(fingerprints[2])
    for arguments in ((-1, "conditions", 1), (1, "unknown", 1), (1, "conditions", 0), (1, "conditions", 65), (1, "conditions", True)):
        with pytest.raises(ValueError):
            world.panel(*arguments)


def test_orbital_public_baseline_shapes_identity_rotation_and_no_kernel_dependency(monkeypatch):
    world, spec = World(46), example()
    record = {"spec": spec, "observation": world.run(spec)}
    np.testing.assert_allclose(baseline([record], spec), record["observation"]["values"], atol=1e-13)
    monkeypatch.setattr(Kernel, "trajectory", lambda *_: pytest.fail("baseline read private kernel"))
    for history in ([], [record]):
        prediction = np.asarray(baseline(history, spec))
        assert prediction.shape == (len(spec["times"]), 4) and np.isfinite(prediction).all()
        np.testing.assert_array_equal(prediction[0], spec["position"] + spec["velocity"])
    rotation = np.asarray([[0., -1.], [1., 0.]])
    rotated = copy.deepcopy(spec)
    for field in ("position", "velocity"):
        rotated[field] = rotation.dot(rotated[field]).tolist()
    for event in rotated["impulses"]:
        event["delta_v"] = rotation.dot(event["delta_v"]).tolist()
    expected = np.asarray(record["observation"]["values"])
    expected = np.column_stack((expected[:, :2].dot(rotation.T), expected[:, 2:].dot(rotation.T)))
    np.testing.assert_allclose(baseline([record], rotated), expected, atol=2e-14)
    malformed = copy.deepcopy(record)
    malformed["observation"]["values"][0] = [1]
    with pytest.raises(ValueError):
        baseline([malformed], spec)
    malformed = copy.deepcopy(record)
    malformed["observation"]["axis"][1] = 99
    with pytest.raises(ValueError):
        baseline([malformed], spec)


def test_orbital_examples_metadata_and_python38_syntax():
    root = Path(__file__).resolve().parents[1]
    metadata = json.loads((root / "world.json").read_text())
    assert metadata["name"] == World.name and metadata["version"] == World.version
    assert metadata["status"] == "experimental_registered"
    assert metadata["operator_strata"] == list(STRUCTURES)
    for example_path in (root / "examples").glob("*.json"):
        World(7).validate(json.loads(example_path.read_text()))
    for spec in World(7).describe()["examples"]:
        World(7).validate(spec)
    for source in root.rglob("*.py"):
        ast.parse(source.read_text(), feature_version=(3, 8))
