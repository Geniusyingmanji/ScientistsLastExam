import copy
import json
from pathlib import Path

import numpy as np
import pytest
from scipy.integrate import solve_ivp
from scipy.special import expit

from env.gene_regulation.world import World, baseline


def experiment():
    return {"initial_expression": [0.1, 0.3, 0.7, 0.9],
            "times_h": [0, 0.5, 1, 2, 4, 8, 12, 18, 24]}


def test_gene_regulation_analytic_unregulated_limit():
    world = World(1)
    world._weights[:] = 0
    world._biases = np.array([-0.5, 0.1, 0.3, -0.2])
    world._decays = np.array([0.15, 0.3, 0.5, 0.8])
    spec = experiment()
    spec["initial_drive"] = [2, 0, -1, 0]
    target = expit(world._biases + spec["initial_drive"])
    times = np.asarray(spec["times_h"])
    expected = target + (np.asarray(spec["initial_expression"]) - target) * np.exp(-times[:, None] * world._decays)
    np.testing.assert_allclose(world.run(spec)["values"], expected, atol=4e-9, rtol=4e-9)


def test_gene_regulation_independent_solver_with_input_switches():
    world = World(31)
    spec = world.describe()["examples"][1]
    state = np.asarray(spec["initial_expression"])
    drive = np.asarray(spec["initial_drive"])
    current = 0.0
    events = iter(spec["interventions"])
    event = next(events, None)
    expected = []
    for time in spec["times_h"]:
        while event is not None and event["time_h"] <= time:
            if event["time_h"] > current:
                state = solve_ivp(lambda _, x: world._rhs(x, drive), (current, event["time_h"]), state,
                                  method="DOP853", rtol=1e-11, atol=1e-13).y[:, -1]
            current = event["time_h"]
            drive = np.asarray(event["drive"])
            event = next(events, None)
        if time > current:
            state = solve_ivp(lambda _, x: world._rhs(x, drive), (current, time), state,
                              method="DOP853", rtol=1e-11, atol=1e-13).y[:, -1]
        current = time
        expected.append(state.copy())
    np.testing.assert_allclose(world.run(spec)["values"], expected, atol=2e-8, rtol=2e-8)


def test_gene_regulation_event_continuity_and_whole_vector_replacement():
    world = World(5)
    world._weights[:] = 0
    world._biases[:] = 0
    world._decays[:] = 0.5
    spec = {"initial_expression": [0.5] * 4, "initial_drive": [2, 0, 0, 0],
            "times_h": [0, 4, 8, 12],
            "interventions": [{"time_h": 4, "kind": "set_drive", "drive": [0, -2, 0, 0]},
                              {"time_h": 12, "kind": "set_drive", "drive": [3, 0, 0, 0]}]}
    output = np.asarray(world.run(spec)["values"])
    control = copy.deepcopy(spec)
    control["interventions"] = []
    np.testing.assert_allclose(output[1], world.run(control)["values"][1], atol=1e-12)
    assert output[2, 0] < output[1, 0]
    assert output[2, 1] < output[1, 1]
    no_final = copy.deepcopy(spec)
    no_final["interventions"].pop()
    assert world.run(spec) == world.run(no_final)


def test_gene_regulation_mutual_activation_memory_and_threshold():
    world = World(0)
    world._weights[:] = 0
    world._weights[0, 1] = world._weights[1, 0] = 3.0
    world._biases[:] = 0
    world._decays[:] = 0.5
    low = {"initial_expression": [0.1] * 4, "times_h": [0, 4, 8, 12, 18, 24]}
    high = copy.deepcopy(low)
    high["initial_expression"] = [0.9] * 4
    low_values = np.asarray(world.run(low)["values"])
    high_values = np.asarray(world.run(high)["values"])
    assert np.min(high_values[-1, :2] - low_values[-1, :2]) > 0.8
    pulse = copy.deepcopy(low)
    pulse["initial_drive"] = [3, 0, 0, 0]
    pulse["interventions"] = [{"time_h": 8, "kind": "set_drive", "drive": [0] * 4}]
    pulse_values = np.asarray(world.run(pulse)["values"])
    assert np.min(pulse_values[-1, :2]) > 0.8


def test_gene_regulation_incoherent_pathway_partial_adaptation():
    world = World(0)
    world._weights[:] = 0
    world._weights[0, 1] = 3
    world._weights[0, 2] = 3
    world._weights[1, 2] = -3
    world._weights[2, 3] = 2
    world._biases[:] = 0
    world._decays = np.array([0.8, 0.15, 0.8, 0.4])
    spec = {"initial_expression": [0.5] * 4, "initial_drive": [3, 0, 0, 0],
            "times_h": list(range(25))}
    values = np.asarray(world.run(spec)["values"])
    assert np.max(values[:, 2]) > values[0, 2] + 0.15
    assert np.max(values[:, 2]) > values[-1, 2] + 0.1
    # Drive remains on; reduced late response comes from the regulatory path.
    assert values[-1, 0] > 0.9


def test_gene_regulation_saturating_drive_is_not_linear():
    world = World(3)
    world._weights[:] = 0
    world._biases[:] = 0
    state = np.full(4, 0.5)
    one = world._rhs(state, np.array([1, 0, 0, 0]))[0]
    two = world._rhs(state, np.array([2, 0, 0, 0]))[0]
    assert 0 < two < 2 * one


def test_gene_regulation_clean_bounds_and_public_parameter_ranges():
    for seed in range(10):
        world = World(seed)
        assert np.all(np.diag(world._weights) == 0)
        nonzero = np.abs(world._weights[world._weights != 0])
        assert np.all((nonzero >= 0.65) & (nonzero <= 3.2))
        assert np.all((world._biases >= -0.6) & (world._biases <= 0.6))
        assert np.all((world._decays >= 0.15) & (world._decays <= 0.8))
        spec = {"initial_expression": [0, 1, 0, 1], "initial_drive": [-3, 3, 0, 0],
                "times_h": np.linspace(0, 24, 41).tolist(),
                "interventions": [{"time_h": 6, "kind": "set_drive", "drive": [0, 0, 3, -3]},
                                  {"time_h": 12, "kind": "set_drive", "drive": [3, -3, 0, 0]},
                                  {"time_h": 18, "kind": "set_drive", "drive": [0, 0, -3, 3]},
                                  {"time_h": 23, "kind": "set_drive", "drive": [0, 0, 0, 0]}]}
        values = np.asarray(world.run(spec)["values"])
        assert np.all(np.isfinite(values)) and np.min(values) >= 0 and np.max(values) <= 1


def test_gene_regulation_reproducible_private_instances_and_noise():
    world = World(7)
    spec = experiment()
    assert world.run(spec) == World(7).run(spec)
    assert world.run(spec, noise_key="x") == World(7).run(spec, noise_key="x")
    assert world.run(spec, noise_key="x") != world.run(spec, noise_key="y")
    assert world.run(spec) != World(8).run(spec)
    assert world.describe() == World(8).describe()
    assert world.axis_field == "times_h"
    assert world.run(spec)["axis"] == world.validate(spec)[world.axis_field]
    assert set(world.run(spec)) == {"axis", "channels", "values"}
    public_text = json.dumps(world.describe()).lower()
    for field in ["_motif", "_weights", "_biases", "_decays", "panel_seed", "clean_values"]:
        assert field not in public_text
    json.dumps(world.run(spec), allow_nan=False)
    np.random.seed(99)
    expected = np.random.random(3)
    np.random.seed(99)
    World(1).run(spec, noise_key="replay")
    np.testing.assert_array_equal(np.random.random(3), expected)


def test_gene_regulation_seeded_signed_topology_variation():
    worlds = [World(seed) for seed in range(24)]
    assert {world._motif for world in worlds} == {0, 1, 2}
    assert len({tuple(np.sign(world._weights).ravel()) for world in worlds}) > 12


@pytest.mark.parametrize("mutate", [
    lambda s: s.update(initial_expression=[0, 1, 2, 0]),
    lambda s: s.update(initial_expression=[0, -0.1, 0, 0]),
    lambda s: s.update(initial_expression=[0, 1, 0]),
    lambda s: s.update(initial_expression=[True, 0, 0, 0]),
    lambda s: s.update(initial_expression=[float("nan"), 0, 0, 0]),
    lambda s: s.update(initial_expression=[10 ** 1000, 0, 0, 0]),
    lambda s: s.update(initial_drive=[1, 1, 1, 0]),
    lambda s: s.update(initial_drive=[3.1, 0, 0, 0]),
    lambda s: s.update(initial_drive=[-3.1, 0, 0, 0]),
    lambda s: s.update(initial_drive=[float("inf"), 0, 0, 0]),
    lambda s: s.update(initial_drive="zero"),
    lambda s: s.update(times_h=[0]),
    lambda s: s.update(times_h=[1, 2]),
    lambda s: s.update(times_h=[0, 2, 2]),
    lambda s: s.update(times_h=[0, 2, 1]),
    lambda s: s.update(times_h=[0, 25]),
    lambda s: s.update(times_h=np.linspace(0, 24, 42).tolist()),
    lambda s: s.update(times_h=[0, float("nan")]),
    lambda s: s.update(times_h=[0, "1"]),
    lambda s: s.update(unknown=True),
    lambda s: s.update(interventions=None),
    lambda s: s.update(interventions=[{"time_h": 0, "kind": "set_drive", "drive": [0] * 4}]),
    lambda s: s.update(interventions=[{"time_h": 25, "kind": "set_drive", "drive": [0] * 4}]),
    lambda s: s.update(interventions=[{"time_h": 1, "kind": "clamp", "drive": [0] * 4}]),
    lambda s: s.update(interventions=[{"time_h": 1, "kind": "set_drive", "drive": [0] * 4}] * 2),
    lambda s: s.update(interventions=[{"time_h": i, "kind": "set_drive", "drive": [0] * 4} for i in range(1, 6)]),
    lambda s: s.update(interventions=[{"time_h": 1, "kind": "set_drive", "drive": [1, 1, 1, 0]}]),
    lambda s: s.update(interventions=[{"time_h": 1, "kind": "set_drive"}]),
])
def test_gene_regulation_invalid_inputs_leave_instance_unchanged(mutate):
    world = World(12)
    original = world.run(experiment())
    spec = experiment()
    mutate(spec)
    for function in [world.validate, world.cost, world.run]:
        with pytest.raises(ValueError):
            function(spec)
    assert world.run(experiment()) == original


@pytest.mark.parametrize("key", ["", 1, False, [], "a" * 257])
def test_gene_regulation_invalid_noise_key(key):
    with pytest.raises(ValueError):
        World(0).run(experiment(), noise_key=key)


@pytest.mark.parametrize("seed", [-1, True, 0.5, 2 ** 63])
def test_gene_regulation_invalid_seed(seed):
    with pytest.raises(ValueError):
        World(seed)


def test_gene_regulation_examples_cost_and_canonical_copy():
    world = World(0)
    examples = world.describe()["examples"]
    for path in (Path(__file__).parent.parent / "examples").glob("*.json"):
        examples.append(json.loads(path.read_text()))
    for spec in examples:
        original = copy.deepcopy(spec)
        canonical = world.validate(spec)
        assert world.cost(spec) == 1 + (len(spec["times_h"]) + 9) // 10 + len(spec["interventions"])
        canonical["initial_expression"][0] = 123
        assert spec == original
        assert np.asarray(world.run(spec)["values"]).shape == (len(spec["times_h"]), 4)


def test_gene_regulation_panels_are_valid_deterministic_and_separate():
    world = World(3)
    panels = {}
    for kind in ["development", "conditions", "interventions"]:
        panel = world.panel(99, kind, count=16)
        assert panel == world.panel(99, kind, count=16)
        assert panel == World(4).panel(99, kind, count=16)
        assert panel != world.panel(100, kind, count=16)
        for spec in panel:
            assert world.validate(spec) == spec
        for spec in panel[:3]:
            assert np.asarray(world.run(spec)["values"]).shape == (len(spec["times_h"]), 4)
        panels[kind] = panel
    assert all(not s["interventions"] and not any(s["initial_drive"]) for s in panels["conditions"])
    assert all(len(s["interventions"]) == 2 for s in panels["interventions"])
    for kind, count in [("unknown", 8), ("conditions", 0), ("conditions", 65), ("conditions", True)]:
        with pytest.raises(ValueError):
            world.panel(1, kind, count)


def test_gene_regulation_baseline_public_only_shape_and_data_dependence(monkeypatch):
    world = World(7)
    spec = world.describe()["examples"][1]
    records = [{"spec": s, "observation": world.run(s, noise_key="fit-%d" % i)}
               for i, s in enumerate(world.panel(5, "development", count=10))]
    empty = np.asarray(baseline([], spec))
    fitted = np.asarray(baseline(records, spec))
    assert fitted.shape == (len(spec["times_h"]), 4)
    assert np.all(np.isfinite(fitted)) and np.min(fitted) >= 0 and np.max(fitted) <= 1
    assert not np.allclose(fitted, empty)
    np.testing.assert_allclose(fitted[0], spec["initial_expression"])
    assert baseline(records, spec) == baseline(copy.deepcopy(records), spec)

    def forbidden(*args, **kwargs):
        raise AssertionError("baseline accessed a private World")

    monkeypatch.setattr(World, "__init__", forbidden)
    monkeypatch.setattr(World, "_rhs", forbidden)
    monkeypatch.setattr(World, "run", forbidden)
    np.testing.assert_array_equal(baseline(records, spec), fitted)
    invalid_records = [{"spec": spec, "observation": {"values": [[float("nan")]], "channels": []}}]
    assert baseline(invalid_records, spec) == baseline([], spec)
