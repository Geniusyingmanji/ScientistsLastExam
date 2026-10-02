import copy
import json
from pathlib import Path

import numpy as np
import pytest
from scipy.integrate import solve_ivp

from env.reaction_kinetics.world import World, baseline


def experiment():
    return {"temperature_k": 325.0, "initial_mM": [1.0, 0.0, 0.0, 0.0],
            "times_s": [0.0, 0.1, 1.0, 5.0, 15.0, 40.0, 80.0, 120.0]}


def test_reaction_kinetics_analytic_reversible_pair():
    class PairWorld(World):
        def _generator(self, temperature):
            del temperature
            return np.array([[-0.1, 0.04, 0, 0], [0.1, -0.04, 0, 0],
                             [0, 0, 0, 0], [0, 0, 0, 0]], dtype=float)

    spec = experiment()
    values = np.asarray(PairWorld(1).run(spec)["values"])
    a = 0.04 / 0.14 + (1.0 - 0.04 / 0.14) * np.exp(-0.14 * np.asarray(spec["times_s"]))
    expected = np.column_stack((a, 1.0 - a, a * 0.0, a * 0.0))
    np.testing.assert_allclose(values, expected, rtol=2e-12, atol=2e-13)


def test_reaction_kinetics_independent_adaptive_solver_and_events():
    world = World(23)
    spec = world.describe()["examples"][1]
    expected = []
    state = np.asarray(spec["initial_mM"], dtype=float)
    current = 0.0
    temperature = spec["temperature_k"]
    events = iter(spec["interventions"])
    event = next(events, None)
    for time in spec["times_s"]:
        while event is not None and event["time_s"] <= time:
            if event["time_s"] > current:
                matrix = world._generator(temperature)
                state = solve_ivp(lambda _, c: matrix.dot(c), (current, event["time_s"]), state,
                                  rtol=2e-11, atol=2e-13, method="DOP853").y[:, -1]
            current = event["time_s"]
            if event["kind"] == "temperature":
                temperature = event["temperature_k"]
            else:
                state = state + event["amounts_mM"]
            event = next(events, None)
        if time > current:
            matrix = world._generator(temperature)
            state = solve_ivp(lambda _, c: matrix.dot(c), (current, time), state,
                              rtol=2e-11, atol=2e-13, method="DOP853").y[:, -1]
        current = time
        expected.append(state.copy())
    np.testing.assert_allclose(world.run(spec)["values"], expected, rtol=2e-9, atol=2e-11)


def test_reaction_kinetics_conservation_and_right_continuity():
    world = World(0)
    spec = experiment()
    spec["interventions"] = [{"time_s": 15.0, "kind": "add", "amounts_mM": [0, 0.2, 0.1, 0]},
                             {"time_s": 120.0, "kind": "add", "amounts_mM": [0, 0, 0, 0.4]}]
    values = np.asarray(world.run(spec)["values"])
    np.testing.assert_allclose(values.sum(axis=1), [1, 1, 1, 1, 1.3, 1.3, 1.3, 1.7], atol=2e-14)
    before = copy.deepcopy(spec)
    before["interventions"] = before["interventions"][:-1]
    last_without_pulse = np.asarray(world.run(before)["values"][-1])
    np.testing.assert_allclose(values[-1] - last_without_pulse, [0, 0, 0, 0.4], atol=2e-14)
    assert np.min(values) >= 0.0


def test_reaction_kinetics_arrhenius_detailed_balance_and_public_ranges():
    world = World(55)
    ref = world._generator(325.0)
    cold = world._generator(305.0)
    ranges = world.describe()["parameter_ranges"]
    positive = ref > 0
    activation = -8.31446261815324 * np.log(cold[positive] / ref[positive]) / (1 / 305.0 - 1 / 325.0)
    assert np.all((ref[positive] >= ranges["present_rate_at_325_k_per_s"][0]) &
                  (ref[positive] <= ranges["present_rate_at_325_k_per_s"][1]))
    assert np.all((activation >= ranges["activation_energy_j_per_mol"][0]) &
                  (activation <= ranges["activation_energy_j_per_mol"][1]))
    for temperature in [285.0, 325.0, 365.0]:
        matrix = world._generator(temperature)
        weights = np.exp(world._log_weights - world._enthalpies / 8.31446261815324 *
                         (1 / temperature - 1 / 325.0))
        flux = matrix * weights[None, :]
        np.testing.assert_allclose(flux, flux.T, atol=2e-15, rtol=2e-14)
        np.testing.assert_allclose(matrix.sum(axis=0), 0.0, atol=5e-16)


def test_reaction_kinetics_fixed_instance_noise_and_private_public_separation():
    spec = experiment()
    world = World(7)
    other = World(7)
    assert world.run(spec) == other.run(spec)
    assert world.run(spec, noise_key="x") == other.run(spec, noise_key="x")
    assert world.run(spec, noise_key="x") != world.run(spec, noise_key="y")
    assert world.run(spec, noise_key="x") != world.run(spec)
    assert world.run(spec) != World(8).run(spec)
    assert world.describe() == World(8).describe()
    response = world.run(spec, noise_key="x")
    assert set(response) == {"axis", "channels", "values"}
    public_text = json.dumps(world.describe()).lower()
    for field in ["_edges", "_conductances", "_barriers", "panel_seed", "_enthalpies", "clean_values"]:
        assert field not in public_text
    json.dumps(response, allow_nan=False)
    # Private randomness has no effect on global NumPy random state.
    np.random.seed(13)
    expected = np.random.random(3)
    np.random.seed(13)
    World(91).run(spec, noise_key="stable")
    np.testing.assert_array_equal(np.random.random(3), expected)


def test_reaction_kinetics_topology_variation():
    worlds = [World(seed) for seed in range(24)]
    assert len({world._edges for world in worlds}) > 8
    assert {len(world._edges) for world in worlds} == {3, 4, 5}
    for world in worlds:
        assert np.all(np.isfinite(world.run(experiment())["values"]))


@pytest.mark.parametrize("mutate", [
    lambda s: s.update(temperature_k=float("nan")),
    lambda s: s.update(temperature_k=float("inf")),
    lambda s: s.update(temperature_k=284),
    lambda s: s.update(temperature_k=366),
    lambda s: s.update(temperature_k=True),
    lambda s: s.update(temperature_k=10 ** 1000),
    lambda s: s.update(initial_mM=[1, 0, 0]),
    lambda s: s.update(initial_mM=[0, 0, 0, 0]),
    lambda s: s.update(initial_mM=[2, 2, 0, 0]),
    lambda s: s.update(initial_mM=[-0.1, 1, 0, 0]),
    lambda s: s.update(initial_mM=[float("inf"), 0, 0, 0]),
    lambda s: s.update(initial_mM=["1", 0, 0, 0]),
    lambda s: s.update(times_s=[0]),
    lambda s: s.update(times_s=[1, 2]),
    lambda s: s.update(times_s=[0, 2, 2]),
    lambda s: s.update(times_s=[0, 2, 1]),
    lambda s: s.update(times_s=[0, 121]),
    lambda s: s.update(times_s=list(range(34))),
    lambda s: s.update(times_s=[0, float("nan")]),
    lambda s: s.update(unsupported=1),
    lambda s: s.update(interventions=None),
    lambda s: s.update(interventions=[{"time_s": 0, "kind": "temperature", "temperature_k": 325}]),
    lambda s: s.update(interventions=[{"time_s": 130, "kind": "temperature", "temperature_k": 325}]),
    lambda s: s.update(interventions=[{"time_s": 1, "kind": "temperature", "temperature_k": 380}]),
    lambda s: s.update(interventions=[{"time_s": 1, "kind": "remove", "amounts_mM": [1, 0, 0, 0]}]),
    lambda s: s.update(interventions=[{"time_s": 1, "kind": "add", "amounts_mM": [0, 0, 0, 0]}]),
    lambda s: s.update(interventions=[{"time_s": 1, "kind": "add", "amounts_mM": [1, 1, 0, 0]}]),
    lambda s: s.update(interventions=[{"time_s": 1, "kind": "add", "amounts_mM": [1.1, 0, 0, 0]}]),
    lambda s: s.update(interventions=[{"time_s": 1, "kind": "add"}]),
    lambda s: s.update(interventions=[{"time_s": 1, "kind": "temperature", "temperature_k": 325}] * 2),
    lambda s: s.update(interventions=[{"time_s": t, "kind": "temperature", "temperature_k": 325} for t in range(1, 6)]),
    lambda s: s.update(interventions=[{"time_s": t, "kind": "add", "amounts_mM": [1, .5, 0, 0]} for t in range(1, 5)]),
])
def test_reaction_kinetics_invalid_experiments_leave_world_unchanged(mutate):
    world = World(2)
    original = world.run(experiment())
    spec = experiment()
    mutate(spec)
    for action in [world.validate, world.cost, world.run]:
        with pytest.raises(ValueError):
            action(spec)
    assert world.run(experiment()) == original


@pytest.mark.parametrize("key", ["", 1, True, [], "x" * 257])
def test_reaction_kinetics_invalid_noise_key(key):
    with pytest.raises(ValueError):
        World(0).run(experiment(), noise_key=key)


@pytest.mark.parametrize("seed", [-1, True, 0.2, 2 ** 63])
def test_reaction_kinetics_invalid_seed(seed):
    with pytest.raises(ValueError):
        World(seed)


def test_reaction_kinetics_panels_are_deterministic_valid_and_distinct():
    world = World(42)
    panels = {}
    for kind in ["development", "conditions", "interventions"]:
        panel = world.panel(99, kind, count=16)
        assert panel == world.panel(99, kind, count=16)
        assert panel == World(43).panel(99, kind, count=16)
        assert panel != world.panel(100, kind, count=16)
        assert len(panel) == 16
        for spec in panel:
            assert world.validate(spec) == spec
            result = world.run(spec)
            assert np.asarray(result["values"]).shape == (len(spec["times_s"]), 4)
        panels[kind] = panel
    assert all(not spec["interventions"] for spec in panels["conditions"])
    assert all(len(spec["interventions"]) == 2 for spec in panels["interventions"])
    assert panels["development"] != panels["conditions"]
    for kind, count in [("unknown", 8), ("conditions", 0), ("conditions", 65), ("conditions", True)]:
        with pytest.raises(ValueError):
            world.panel(1, kind, count)


def test_reaction_kinetics_examples_canonical_copy_and_cost():
    world = World(1)
    for path in (Path(__file__).parent.parent / "examples").glob("*.json"):
        raw = json.loads(path.read_text())
        original = copy.deepcopy(raw)
        canonical = world.validate(raw)
        assert raw == original
        assert world.cost(raw) == 1 + (len(raw["times_s"]) + 7) // 8 + len(raw.get("interventions", []))
        assert len(world.run(raw)["axis"]) == len(raw["times_s"])
        canonical["initial_mM"][0] = 123
        assert raw == original
    for spec in world.describe()["examples"]:
        world.validate(spec)


def test_reaction_kinetics_baseline_no_data_pulses_and_observation_fit():
    world = World(19)
    target = world.describe()["examples"][1]
    empty = np.asarray(baseline([], target))
    assert empty.shape == (len(target["times_s"]), 4)
    np.testing.assert_allclose(empty[0], target["initial_mM"])
    np.testing.assert_allclose(empty[-1], [0.25, 0.6, 0.0, 0.4])
    records = []
    for channel in range(4):
        spec = {"temperature_k": 325, "initial_mM": [float(i == channel) for i in range(4)],
                "times_s": np.linspace(0, 40, 33).tolist()}
        records.append({"spec": spec, "observation": world.run(spec, noise_key="train-%d" % channel)})
    query = {"temperature_k": 325, "initial_mM": [0.3, 0.1, 0.4, 0.2],
             "times_s": [0, 2, 5, 10, 20, 40, 70],
             "interventions": [{"time_s": 10, "kind": "add", "amounts_mM": [0, 0.2, 0, 0]}]}
    prediction = np.asarray(baseline(records, query))
    assert np.all(np.isfinite(prediction)) and np.min(prediction) >= 0
    assert np.sqrt(np.mean((prediction - world.run(query)["values"]) ** 2)) < 0.025
    assert baseline(records, query) == baseline(copy.deepcopy(records), query)
    np.testing.assert_allclose(prediction.sum(axis=1), [1, 1, 1, 1.2, 1.2, 1.2, 1.2])
    # Deliberately unusable observations are skipped rather than used as truth.
    bad = [{"spec": experiment(), "observation": {"channels": ["hidden"], "values": [[float("nan")]]}}]
    assert baseline(bad, target) == baseline([], target)


def test_reaction_kinetics_baseline_has_no_world_dependency(monkeypatch):
    world = World(14)
    spec = experiment()
    records = [{"spec": spec, "observation": world.run(spec)}]

    def forbidden(*args, **kwargs):
        raise AssertionError("baseline accessed the private world")

    monkeypatch.setattr(World, "__init__", forbidden)
    monkeypatch.setattr(World, "_generator", forbidden)
    monkeypatch.setattr(World, "run", forbidden)
    result = baseline(records, spec)
    assert np.asarray(result).shape == (len(spec["times_s"]), 4)
