"""Independent physical checks and public-contract tests for the oscillator world."""

import copy
import json
import math
from pathlib import Path

import numpy as np
import pytest
from scipy.integrate import solve_ivp

from env.coupled_oscillators.world import CHANNELS, NODES, PAIRS, World, baseline


def dense_spec(**kwargs):
    spec = {"times": np.linspace(0, 12, 121).tolist(), "initial_position": [0.6, 0.1, -0.2, 0.3]}
    spec.update(kwargs)
    return spec


def all_pairs():
    return [[NODES[i], NODES[j]] for i, j in PAIRS]


def test_oscillator_cut_network_matches_four_analytic_solutions():
    world = World(182)
    spec = dense_spec(cut_edges=all_pairs(), initial_velocity=[0.2, -0.3, 0.1, -0.1], mass_add=[0, 1, 2, 3])
    observed = np.asarray(world.run(spec)["values"])
    t = np.asarray(spec["times"])[:, None]
    m = 1 + np.asarray(spec["mass_add"])
    alpha = world._damping / (2 * m)
    omega = np.sqrt(world._grounding / m - alpha ** 2)
    q = np.asarray(spec["initial_position"])
    v = np.asarray(spec["initial_velocity"])
    b = (v + alpha * q) / omega
    envelope = np.exp(-alpha * t)
    x = envelope * (q * np.cos(omega * t) + b * np.sin(omega * t))
    velocity = -alpha * x + envelope * omega * (-q * np.sin(omega * t) + b * np.cos(omega * t))
    np.testing.assert_allclose(observed, np.column_stack([x, velocity]), rtol=1e-10, atol=1e-11)


def test_oscillator_constant_force_analytic_and_clamp_zero():
    world = World(81)
    spec = {
        "times": [0, 0.4, 1.7, 4.1, 11.0],
        "cut_edges": all_pairs(),
        "clamp": ["B", "C", "D"],
        "drive": {"node": "A", "amplitude": 0.7, "frequency": 0, "phase": math.pi / 2},
    }
    values = np.asarray(world.run(spec)["values"])
    t = np.asarray(spec["times"])
    alpha = world._damping[0] / 2
    omega = math.sqrt(world._grounding[0] - alpha ** 2)
    equilibrium = 0.7 / world._grounding[0]
    expected_x = equilibrium * (1 - np.exp(-alpha * t) * (np.cos(omega * t) + alpha / omega * np.sin(omega * t)))
    expected_v = equilibrium * world._grounding[0] / omega * np.exp(-alpha * t) * np.sin(omega * t)
    np.testing.assert_allclose(values[:, 0], expected_x, atol=1e-11)
    np.testing.assert_allclose(values[:, 4], expected_v, atol=1e-11)
    np.testing.assert_array_equal(values[:, [1, 2, 3, 5, 6, 7]], 0)
    fully_clamped = world.run({"times": [0, 0.3, 24], "clamp": list(NODES)})
    np.testing.assert_array_equal(fully_clamped["values"], np.zeros((3, 8)))


@pytest.mark.parametrize("seed", [0, 12, 999])
def test_oscillator_matrix_kernel_agrees_with_independent_time_domain_solver(seed):
    world = World(seed)
    spec = world.validate({
        "times": [0.0, 0.11, 0.33, 0.92, 1.9, 4.7, 12.0, 24.0],
        "initial_position": [0.4, -0.7, 0, 0.3],
        "initial_velocity": [0.2, 0.1, 0, -0.5],
        "mass_add": [0.4, 1.0, 0, 2.0],
        "damping_add": [0.3, 0, 0, 0.6],
        "cut_edges": [["A", "D"]],
        "clamp": ["C"],
        "drive": {"node": "B", "amplitude": 0.9, "frequency": 0.7, "phase": 1.1},
    })

    def derivative(t, state):
        position, velocity = state[:4], state[4:]
        force = -world._grounding * position - (world._damping + spec["damping_add"]) * velocity
        for (i, j), stiffness in zip(PAIRS, world._springs):
            if [NODES[i], NODES[j]] in spec["cut_edges"]:
                continue
            pair_force = stiffness * (position[j] - position[i])
            force[i] += pair_force
            force[j] -= pair_force
        drive = spec["drive"]
        force[1] += drive["amplitude"] * math.sin(2 * math.pi * drive["frequency"] * t + drive["phase"])
        acceleration = force / (1 + np.asarray(spec["mass_add"]))
        dx = velocity.copy()
        dx[2] = acceleration[2] = 0
        return np.concatenate([dx, acceleration])

    solution = solve_ivp(derivative, (0, 24), spec["initial_position"] + spec["initial_velocity"], t_eval=spec["times"], rtol=2e-11, atol=1e-12, max_step=0.015)
    assert solution.success
    np.testing.assert_allclose(world.run(spec)["values"], solution.y.T, rtol=2e-8, atol=2e-9)


def test_oscillator_passive_energy_decreases_and_absent_cut_is_noop():
    world = World(16)
    spec = dense_spec(initial_velocity=[0.1, -0.2, 0.7, 0.3], mass_add=[0, 1, 2, 0.5])
    values = np.asarray(world.run(spec)["values"])
    x, v = values[:, :4], values[:, 4:]
    energy = 0.5 * np.sum((1 + np.asarray(spec["mass_add"])) * v * v + world._grounding * x * x, axis=1)
    for (i, j), stiffness in zip(PAIRS, world._springs):
        energy += 0.5 * stiffness * (x[:, i] - x[:, j]) ** 2
    assert np.all(np.diff(energy) < 0)
    found_absent = False
    for seed in range(10):
        world = World(seed)
        absent = np.flatnonzero(world._springs == 0)
        if len(absent):
            i, j = PAIRS[int(absent[0])]
            cut = dict(spec, cut_edges=[[NODES[i], NODES[j]]])
            assert world.run(spec) == world.run(cut)
            found_absent = True
            break
    assert found_absent


@pytest.mark.parametrize("spec", [
    None, [], {}, {"times": []}, {"times": [1, 0]}, {"times": [0, 0]},
    {"times": [-1]}, {"times": [24.01]}, {"times": [float("nan")]},
    {"times": [float("inf")]}, {"times": [True]}, {"times": ["1"]},
    {"times": [10 ** 1000]}, {"times": [0] * 242}, {"times": [0], "seed": 2},
    {"times": [0], "initial_position": [0, 0, 0]},
    {"times": [0], "initial_position": [0, 0, 0, 1.1]},
    {"times": [0], "initial_velocity": [0, 0, 0, -2.1]},
    {"times": [0], "initial_velocity": [0, 0, 0, True]},
    {"times": [0], "mass_add": [0, 0, 0, -1]},
    {"times": [0], "damping_add": [0, 0, 0, 2.1]},
    {"times": [0], "cut_edges": [["A", "A"]]},
    {"times": [0], "cut_edges": [["A", "B"], ["B", "A"]]},
    {"times": [0], "cut_edges": [["A", "E"]]},
    {"times": [0], "cut_edges": ["AB"]},
    {"times": [0], "clamp": ["A", "A"]},
    {"times": [0], "clamp": ["A"], "initial_position": [1, 0, 0, 0]},
    {"times": [0], "clamp": "A"},
    {"times": [0], "drive": {}},
    {"times": [0], "drive": {"node": "A", "amplitude": 0.5, "frequency": 3, "phase": 0}},
    {"times": [0], "drive": {"node": "A", "amplitude": 0.5, "frequency": 1, "phase": 4}},
    {"times": [0], "drive": {"node": "A", "amplitude": 0.5, "frequency": 1, "phase": 0, "secret": 1}},
    {"times": [0], "clamp": ["A"], "drive": {"node": "A", "amplitude": 0.5, "frequency": 1, "phase": 0}},
])
def test_oscillator_rejects_invalid_experiments_without_mutation(spec):
    world = World(11)
    control = dense_spec()
    before = world.run(control)
    for method in (world.validate, world.cost, world.run):
        with pytest.raises(ValueError):
            method(spec)
    assert world.run(control) == before


@pytest.mark.parametrize("seed", [True, 1.2, "7", -1, 2 ** 63, None])
def test_oscillator_invalid_instance_seeds(seed):
    with pytest.raises(ValueError):
        World(seed)


def test_oscillator_canonical_json_and_output_ownership():
    world = World(2)
    spec = {"times": (0, 1), "cut_edges": [("D", "C"), ("B", "A")], "clamp": ("D", "A")}
    original = copy.deepcopy(spec)
    canonical = world.validate(spec)
    assert spec == original
    assert canonical["cut_edges"] == [["A", "B"], ["C", "D"]]
    assert canonical["clamp"] == ["A", "D"]
    assert world.validate(canonical) == canonical
    assert json.loads(json.dumps(canonical, allow_nan=False)) == canonical
    result = world.run(spec)
    assert set(result) == {"axis", "channels", "values"}
    assert result["channels"] == list(CHANNELS)
    assert np.shape(result["values"]) == (2, 8)
    result["axis"][0] = 123
    result["values"][0][0] = 123
    assert world.run(spec)["axis"][0] == 0
    assert world.cost({"times": [0]}) == 2
    assert world.cost({"times": np.linspace(0, 24, 241).tolist()}) == 15


def test_oscillator_noise_reproducible_centered_and_no_state_leak():
    world = World(321)
    spec = {"times": np.linspace(0, 24, 241).tolist()}
    first = world.run(spec, noise_key="replica-a")
    assert first == world.run(spec, noise_key="replica-a")
    assert first == World(321).run(spec, noise_key="replica-a")
    assert first != world.run(spec, noise_key="replica-b")
    assert first != World(322).run(spec, noise_key="replica-a")
    assert world.run(spec) == World(321).run(spec)
    noise = np.asarray(first["values"]) / world.noise_std
    assert abs(np.mean(noise)) < 0.12
    assert 0.88 < np.std(noise) < 1.12
    for invalid in (2, True, {}, "x" * 257, "\ud800"):
        with pytest.raises(ValueError):
            world.run(spec, noise_key=invalid)
    description = world.describe()
    assert description == World(932).describe()
    assert "seed" not in json.dumps(description)
    assert "_grounding" not in json.dumps(description)
    for example in description["examples"]:
        world.validate(example)
    description["scales"][0] = 100
    assert world.describe()["scales"][0] == 1


def test_oscillator_hidden_seeds_change_parameters_and_graphs():
    worlds = [World(i) for i in range(32)]
    assert len({tuple(world._springs > 0) for world in worlds}) >= 8
    assert len({tuple(world._grounding) for world in worlds}) == 32
    for world in worlds:
        reached = {0}
        for _ in range(4):
            for (i, j), stiffness in zip(PAIRS, world._springs):
                if stiffness > 0 and (i in reached or j in reached):
                    reached.update([i, j])
        assert len(reached) == 4


def test_oscillator_panels_valid_deterministic_and_distinguish_manipulations():
    world = World(8)
    for kind in ("development", "conditions", "interventions"):
        panel = world.panel(55, kind, count=10)
        assert panel == world.panel(55, kind, count=10)
        assert panel == World(9).panel(55, kind, count=10)
        assert panel != world.panel(56, kind, count=10)
        for spec in panel:
            assert world.validate(spec) == spec
            assert 2 <= world.cost(spec) <= 15
            if kind == "conditions":
                assert not spec["cut_edges"] and not spec["clamp"]
                assert not any(spec["mass_add"] + spec["damping_add"])
                assert spec["drive"] is None
            if kind == "interventions":
                assert spec["cut_edges"] or spec["clamp"] or any(spec["mass_add"] + spec["damping_add"]) or spec["drive"]
        # Check one maximal-duration response per kind, without needlessly
        # executing all operator panel members during contract validation.
        assert np.isfinite(world.run(max(panel, key=lambda s: s["times"][-1]))["values"]).all()
    for args in [(2, "unknown", 8), (-1, "conditions", 8), (2, "conditions", 0), (2, "conditions", 65), (2, "conditions", True)]:
        with pytest.raises(ValueError):
            world.panel(*args)


def test_oscillator_baseline_empty_malformed_and_public_only(monkeypatch):
    spec = dense_spec()
    expected = np.asarray(baseline([], spec))
    assert expected.shape == (121, 8)
    assert np.isfinite(expected).all()
    np.testing.assert_array_equal(expected[0], spec["initial_position"] + [0] * 4)
    bad_records = [None, {}, {"spec": spec, "observation": {"axis": spec["times"], "channels": list(CHANNELS), "values": [[0] * 7] * 121}}]
    assert baseline(bad_records, spec) == expected.tolist()
    with pytest.raises(ValueError):
        baseline([{}] * 257, spec)
    world = World(73)
    records = [{"spec": spec, "observation": world.run(spec, noise_key="train")}]
    before = copy.deepcopy(records)

    def forbidden(*args, **kwargs):
        raise AssertionError("public baseline must never construct a hidden world")

    monkeypatch.setattr(World, "__init__", forbidden)
    fitted = np.asarray(baseline(records, spec))
    assert np.isfinite(fitted).all()
    assert records == before


def test_oscillator_public_fit_learns_across_initial_conditions_and_interventions():
    world = World(46)
    records = []
    for i in range(4):
        initial = [0.0] * 4
        initial[i] = 0.7
        spec = dense_spec(initial_position=initial)
        records.append({"spec": spec, "observation": world.run(spec, noise_key="training-%s" % i)})
    # The holdout contains a clamp, a loading, an unknown link cut and a drive.
    # Its outcome is only used to measure public-model transfer, never to fit.
    target = dense_spec(initial_position=[-0.5, 0.1, 0.4, 0], clamp=["D"], cut_edges=[["A", "C"]], mass_add=[0, 0.8, 0, 0], drive={"node": "A", "amplitude": 0.4, "frequency": 0.22, "phase": 0.2})
    actual = np.asarray(world.run(target)["values"])
    informed = np.asarray(baseline(records, target))
    naive = np.asarray(baseline([], target))
    informed_rmse = np.sqrt(np.mean(((informed - actual) / world.scales) ** 2))
    naive_rmse = np.sqrt(np.mean(((naive - actual) / world.scales) ** 2))
    assert informed_rmse < 0.025
    assert informed_rmse < naive_rmse / 4


def test_oscillator_initial_zero_and_single_nonzero_requested_time():
    world = World(901)
    spec = dense_spec()
    observed = world.run(spec)
    np.testing.assert_array_equal(observed["values"][0], spec["initial_position"] + [0] * 4)
    assert np.asarray(world.run({"times": [0, 24]})["values"]).max() == 0
    single = dict(spec, times=[12])
    np.testing.assert_allclose(world.run(single)["values"][0], observed["values"][-1], atol=1e-12)


def test_oscillator_extreme_legal_controls_remain_finite():
    world = World(2 ** 63 - 1)
    spec = {
        "times": np.linspace(0, 24, 241).tolist(),
        "initial_position": [-1, 1, -1, 1],
        "initial_velocity": [2, -2, 2, -2],
        "mass_add": [0, 3, 0, 3],
        "damping_add": [0, 2, 0, 2],
        "drive": {"node": "A", "amplitude": -2, "frequency": 2, "phase": -math.pi},
    }
    observation = world.run(spec, noise_key="extreme")
    assert np.shape(observation["values"]) == (241, 8)
    assert np.isfinite(observation["values"]).all()


def test_oscillator_documented_plan_and_metadata_match_contract():
    root = Path(__file__).parents[1]
    world = World(7)
    plan = json.loads((root / "examples" / "experiments.json").read_text())
    assert len(plan) == 12
    assert sum(world.cost(spec) for spec in plan) == 96
    for spec in plan:
        world.validate(spec)
    metadata = json.loads((root / "world.json").read_text())
    assert metadata["name"] == world.name
    assert metadata["version"] == world.version
    assert metadata["channels"] == list(world.channels)
    assert metadata["scales"] == list(world.scales)
    assert metadata["noise_std"] == list(world.noise_std)
