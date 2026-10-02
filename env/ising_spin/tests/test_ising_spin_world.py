"""Independent finite-state checks, response identities and interface tests."""

import copy
import json
import math
from itertools import product
from pathlib import Path

import numpy as np
import pytest

from env.ising_spin.world import CHANNELS, NODES, PAIRS, World, baseline


def suppress_all():
    return [{"nodes": [NODES[i], NODES[j]], "fraction": 1.0} for i, j in PAIRS]


def sweep(**kwargs):
    spec = {"temperatures": [0.5, 0.7, 1.0, 1.5, 2.2, 3.2, 4.5, 6.0]}
    spec.update(kwargs)
    return spec


@pytest.mark.parametrize("seed", [0, 17, 991])
def test_ising_exact_expectations_agree_with_independent_brute_force(seed):
    world = World(seed)
    spec = world.validate({
        "temperatures": [0.35, 0.77, 1.3, 2.6, 6.0],
        "external_field": [0.3, -0.8, 1.2, 0, 0.2, -0.3],
        "clamp": {"B": -1, "E": 1},
        "suppress_bonds": [{"nodes": ["A", "C"], "fraction": 0.6}, {"nodes": ["C", "F"], "fraction": 1.0}],
    })
    control = {tuple(item["nodes"]): item["fraction"] for item in spec["suppress_bonds"]}
    expected = []
    for temperature in spec["temperatures"]:
        weighted_states = []
        for state in product((-1, 1), repeat=6):
            if any(state[NODES.index(node)] != value for node, value in spec["clamp"].items()):
                continue
            energy = -sum((float(world._coefficients[i]) + spec["external_field"][i]) * state[i] for i in range(6))
            for p, (i, j) in enumerate(PAIRS):
                fraction = control.get((NODES[i], NODES[j]), 0)
                energy -= float(world._coefficients[6 + p]) * (1 - fraction) * state[i] * state[j]
            weight = math.exp(-energy / temperature)
            features = list(state) + [state[i] * state[j] for i, j in PAIRS]
            weighted_states.append((weight, features))
        partition = sum(weight for weight, _ in weighted_states)
        expected.append([sum(weight * feature[column] for weight, feature in weighted_states) / partition for column in range(21)])
    np.testing.assert_allclose(world.run(spec)["values"], expected, atol=2e-14, rtol=2e-13)


def test_ising_cut_network_matches_independent_spin_analytic_solution():
    world = World(7)
    spec = sweep(suppress_bonds=suppress_all(), external_field=[0.2, -0.5, 0.7, 0.1, -0.3, 0.4], clamp={"C": -1})
    temperature = np.asarray(spec["temperatures"])[:, None]
    means = np.tanh((world._coefficients[:6] + spec["external_field"]) / temperature)
    means[:, 2] = -1
    expected = np.column_stack([means] + [means[:, i] * means[:, j] for i, j in PAIRS])
    np.testing.assert_allclose(world.run(spec)["values"], expected, atol=2e-14)


def test_ising_global_spin_reversal_and_zero_field_symmetry():
    world = World(85)
    world._coefficients[:6] = 0
    unforced = np.asarray(world.run(sweep())["values"])
    np.testing.assert_allclose(unforced[:, :6], 0, atol=1e-15)
    field = np.asarray([0.2, -0.3, 0.5, -0.4, 0.1, 0.7])
    positive = np.asarray(world.run(sweep(external_field=field.tolist()))["values"])
    negative = np.asarray(world.run(sweep(external_field=(-field).tolist()))["values"])
    np.testing.assert_allclose(positive[:, :6], -negative[:, :6], atol=2e-14)
    np.testing.assert_allclose(positive[:, 6:], negative[:, 6:], atol=2e-14)


def test_ising_gauge_transformation_including_clamps_and_suppression():
    original = World(301)
    transformed = World(301)
    signs = np.asarray([-1, 1, -1, -1, 1, 1])
    feature_signs = np.concatenate([signs, [signs[i] * signs[j] for i, j in PAIRS]])
    transformed._coefficients *= feature_signs
    spec = sweep(external_field=[0.3, -0.2, 0.4, 0, 0.7, -0.1], clamp={"A": 1, "F": -1}, suppress_bonds=[{"nodes": ["D", "E"], "fraction": 0.4}])
    changed = copy.deepcopy(spec)
    changed["external_field"] = (np.asarray(spec["external_field"]) * signs).tolist()
    changed["clamp"] = {node: int(value * signs[NODES.index(node)]) for node, value in spec["clamp"].items()}
    expected = np.asarray(original.run(spec)["values"]) * feature_signs
    np.testing.assert_allclose(transformed.run(changed)["values"], expected, atol=2e-14)


def test_ising_pair_correlation_can_be_indirect_and_absent_cut_noop():
    world = World(9)
    world._coefficients[:] = 0
    world._coefficients[6 + PAIRS.index((0, 1))] = 0.8
    world._coefficients[6 + PAIRS.index((1, 2))] = -0.7
    spec = sweep()
    observed = np.asarray(world.run(spec)["values"])
    temperature = np.asarray(spec["temperatures"])
    indirect = 6 + PAIRS.index((0, 2))
    np.testing.assert_allclose(observed[:, indirect], np.tanh(0.8 / temperature) * np.tanh(-0.7 / temperature), atol=1e-14)
    assert abs(observed[0, indirect]) > 0.5
    cut = sweep(suppress_bonds=[{"nodes": ["A", "C"], "fraction": 1.0}])
    assert world.run(spec) == world.run(cut)


def test_ising_fluctuation_response_identity_and_nonnegative_susceptibility():
    world = World(418)
    temperatures = [0.35, 0.8, 1.4, 3.0, 6.0]
    moments = np.asarray(world.run({"temperatures": temperatures})["values"])
    susceptibility = (6 + 2 * np.sum(moments[:, 6:], axis=1) - np.sum(moments[:, :6], axis=1) ** 2) / temperatures
    assert np.all(susceptibility > 0)
    delta = 1e-5
    plus = np.asarray(world.run({"temperatures": temperatures, "external_field": [delta] * 6})["values"])
    minus = np.asarray(world.run({"temperatures": temperatures, "external_field": [-delta] * 6})["values"])
    finite_difference = np.sum(plus[:, :6] - minus[:, :6], axis=1) / (2 * delta)
    np.testing.assert_allclose(finite_difference, susceptibility, rtol=2e-8, atol=2e-8)


def test_ising_finite_antiferromagnetic_dimers_have_response_peak():
    world = World(42)
    world._coefficients[:] = 0
    for pair in ((0, 1), (2, 3), (4, 5)):
        world._coefficients[6 + PAIRS.index(pair)] = -1
    temperatures = np.asarray([0.35, 1.5, 6.0])
    moments = np.asarray(world.run({"temperatures": temperatures.tolist()})["values"])
    susceptibility = (6 + 2 * np.sum(moments[:, 6:], axis=1) - np.sum(moments[:, :6], axis=1) ** 2) / temperatures
    expected = 6 * (1 - np.tanh(1 / temperatures)) / temperatures
    np.testing.assert_allclose(susceptibility, expected, atol=2e-14)
    assert susceptibility[1] > susceptibility[0] and susceptibility[1] > susceptibility[2]


def test_ising_frustrated_triangle_cannot_satisfy_every_antiferromagnetic_bond():
    world = World(41)
    world._coefficients[:] = 0
    triangle = ((0, 1), (0, 2), (1, 2))
    for pair in triangle:
        world._coefficients[6 + PAIRS.index(pair)] = -1
    temperatures = np.asarray([0.35, 0.6, 1, 2, 6])
    moments = np.asarray(world.run({"temperatures": temperatures.tolist()})["values"])
    # Two fully aligned states have energy +3; six frustrated ground states
    # have energy -1. Each triangle bond averages -1/3 over the ground states.
    ratio = np.exp(-4 / temperatures)
    expected = (ratio - 1) / (ratio + 3)
    for pair in triangle:
        np.testing.assert_allclose(moments[:, 6 + PAIRS.index(pair)], expected, atol=2e-14)
    assert abs(expected[0] + 1 / 3) < 1e-5
    np.testing.assert_allclose(moments[:, :6], 0, atol=2e-14)


def test_ising_all_clamps_and_field_on_clamped_node():
    world = World(11)
    states = [-1, 1, -1, 1, 1, -1]
    spec = sweep(clamp=dict(zip(NODES, states)))
    features = states + [states[i] * states[j] for i, j in PAIRS]
    np.testing.assert_allclose(world.run(spec)["values"], [features] * len(spec["temperatures"]), atol=1e-14)
    partial = sweep(clamp={"B": -1})
    changed = sweep(clamp={"B": -1}, external_field=[0, 2, 0, 0, 0, 0])
    np.testing.assert_allclose(world.run(partial)["values"], world.run(changed)["values"], atol=2e-14)
    empty = World(2)
    empty._coefficients[:] = 0
    np.testing.assert_allclose(empty.run(sweep())["values"], np.zeros((8, 21)), atol=1e-15)


@pytest.mark.parametrize("spec", [
    None, [], {}, {"temperatures": []}, {"temperatures": [1, 0.9]},
    {"temperatures": [1, 1]}, {"temperatures": [0.349]}, {"temperatures": [6.001]},
    {"temperatures": [float("nan")]}, {"temperatures": [float("inf")]},
    {"temperatures": [True]}, {"temperatures": ["1"]}, {"temperatures": [10 ** 1000]},
    {"temperatures": [1] * 33}, {"temperatures": [1], "seed": 1},
    {"temperatures": [1], "external_field": [0] * 5},
    {"temperatures": [1], "external_field": [0] * 5 + [2.01]},
    {"temperatures": [1], "external_field": [0] * 5 + [False]},
    {"temperatures": [1], "clamp": []}, {"temperatures": [1], "clamp": {"A": 0}},
    {"temperatures": [1], "clamp": {"A": 1.0}}, {"temperatures": [1], "clamp": {"G": 1}},
    {"temperatures": [1], "clamp": {"A": True}},
    {"temperatures": [1], "suppress_bonds": {}},
    {"temperatures": [1], "suppress_bonds": [{"nodes": ["A", "A"], "fraction": 0.5}]},
    {"temperatures": [1], "suppress_bonds": [{"nodes": ["A", "G"], "fraction": 0.5}]},
    {"temperatures": [1], "suppress_bonds": [{"nodes": "AB", "fraction": 0.5}]},
    {"temperatures": [1], "suppress_bonds": [{"nodes": ["A", "B"], "fraction": 1.1}]},
    {"temperatures": [1], "suppress_bonds": [{"nodes": ["A", "B"], "fraction": -0.1}]},
    {"temperatures": [1], "suppress_bonds": [{"nodes": ["A", "B"], "fraction": 0.5, "hidden": 1}]},
    {"temperatures": [1], "suppress_bonds": [{"nodes": ["A", "B"]}]},
    {"temperatures": [1], "suppress_bonds": [{"nodes": ["A", "B"], "fraction": 0}, {"nodes": ["B", "A"], "fraction": 1}]},
])
def test_ising_rejects_invalid_inputs_without_instance_mutation(spec):
    world = World(8)
    before = world.run(sweep())
    for operation in (world.validate, world.cost, world.run):
        with pytest.raises(ValueError):
            operation(spec)
    assert world.run(sweep()) == before


@pytest.mark.parametrize("seed", [True, np.bool_(False), 1.0, -1, 2 ** 63, "4", None])
def test_ising_invalid_instance_seed(seed):
    with pytest.raises(ValueError):
        World(seed)


def test_ising_canonical_contract_ownership_and_extreme_legal_inputs():
    world = World(2 ** 63 - 1)
    spec = {"temperatures": (0.35, 6), "external_field": (-2, 2, -2, 2, -2, 2), "clamp": {"F": -1, "A": 1}, "suppress_bonds": [{"nodes": ["F", "B"], "fraction": 0.75}]}
    before = copy.deepcopy(spec)
    canonical = world.validate(spec)
    assert spec == before
    assert canonical["suppress_bonds"][0]["nodes"] == ["B", "F"]
    assert list(canonical["clamp"]) == ["A", "F"]
    assert world.validate(canonical) == canonical
    assert json.loads(json.dumps(canonical, allow_nan=False)) == canonical
    result = world.run(spec)
    assert set(result) == {"axis", "channels", "values"}
    assert result["axis"] == canonical[world.axis_field]
    assert np.shape(result["values"]) == (2, 21)
    assert np.isfinite(result["values"]).all()
    result["axis"][0] = 99
    result["values"][0][0] = 99
    assert world.run(spec)["axis"][0] == 0.35
    assert world.cost({"temperatures": [1]}) == 2
    assert world.cost({"temperatures": np.linspace(0.35, 6, 32).tolist()}) == 9


def test_ising_noise_reproducibility_statistics_and_public_privacy():
    world = World(19)
    spec = {"temperatures": np.linspace(0.35, 6, 32).tolist()}
    clean = np.asarray(world.run(spec)["values"])
    observation = world.run(spec, noise_key="replica")
    assert observation == world.run(spec, noise_key="replica")
    assert observation == World(19).run(spec, noise_key="replica")
    assert observation != world.run(spec, noise_key="new-replica")
    assert observation != World(20).run(spec, noise_key="replica")
    standardized = (np.asarray(observation["values"]) - clean) / world.noise_std
    assert abs(np.mean(standardized)) < 0.15
    assert 0.85 < np.std(standardized) < 1.15
    clamped = np.asarray(world.run(sweep(clamp=dict.fromkeys(NODES, 1)), noise_key="clamped")["values"])
    assert np.any(clamped > 1) and np.any(clamped < 1)
    for key in (True, 2, {}, "x" * 257, "\ud800"):
        with pytest.raises(ValueError):
            world.run(spec, noise_key=key)
    description = world.describe()
    assert description == World(51).describe()
    assert "seed" not in json.dumps(description)
    assert "_coefficients" not in json.dumps(description)
    for example in description["examples"]:
        world.validate(example)
    description["scales"][0] = 99
    assert world.describe()["scales"][0] == 1


def test_ising_connected_graph_and_parameter_diversity():
    worlds = [World(i) for i in range(24)]
    assert len({tuple(w._coefficients[6:] != 0) for w in worlds}) >= 12
    assert len({tuple(w._coefficients[:6]) for w in worlds}) == 24
    for world in worlds:
        reached = {0}
        for _ in range(6):
            for (i, j), strength in zip(PAIRS, world._coefficients[6:]):
                if strength and (i in reached or j in reached):
                    reached.update([i, j])
        assert len(reached) == 6
        nonzero = np.abs(world._coefficients[6:])
        nonzero = nonzero[nonzero > 0]
        assert np.all(nonzero >= 0.2) and np.all(nonzero <= 1.2)


def test_ising_panels_distinguish_conditions_from_interventions():
    world = World(71)
    for kind in ("development", "conditions", "interventions"):
        panel = world.panel(17, kind, count=8)
        assert panel == world.panel(17, kind, count=8)
        assert panel == World(72).panel(17, kind, count=8)
        assert panel != world.panel(18, kind, count=8)
        for spec in panel:
            assert world.validate(spec) == spec
            assert 2 <= world.cost(spec) <= 9
            assert np.isfinite(world.run(spec)["values"]).all()
            if kind == "conditions":
                assert not spec["clamp"] and not spec["suppress_bonds"]
                assert not any(spec["external_field"])
            elif kind == "interventions":
                assert spec["clamp"] or spec["suppress_bonds"] or any(spec["external_field"])
    for args in [(2, "bad", 8), (-1, "conditions", 8), (True, "conditions", 8), (2, "conditions", 0), (2, "conditions", 65), (2, "conditions", True)]:
        with pytest.raises(ValueError):
            world.panel(*args)


def test_ising_baseline_shapes_empty_records_and_private_independence(monkeypatch):
    spec = sweep(external_field=[0.2, -0.3, 0, 0, 0, 0], clamp={"F": -1})
    empty = np.asarray(baseline([], spec))
    means = np.tanh(np.asarray(spec["external_field"])[None, :] / np.asarray(spec["temperatures"])[:, None])
    means[:, 5] = -1
    expected = np.column_stack([means] + [means[:, i] * means[:, j] for i, j in PAIRS])
    np.testing.assert_allclose(empty, expected, atol=2e-15)
    invalid = [None, {}, {"spec": spec, "observation": {"channels": list(CHANNELS), "axis": [1], "values": [[0] * 21]}}]
    np.testing.assert_array_equal(baseline(invalid, spec), empty)
    with pytest.raises(ValueError):
        baseline([{}] * 257, spec)
    world = World(2)
    records = [{"spec": sweep(), "observation": world.run(sweep(), noise_key="training")}]
    original = copy.deepcopy(records)

    def forbidden(*args, **kwargs):
        raise AssertionError("public baseline must never construct a hidden World")

    monkeypatch.setattr(World, "__init__", forbidden)
    prediction = np.asarray(baseline(records, spec))
    assert prediction.shape == (8, 21) and np.isfinite(prediction).all()
    assert records == original


def test_ising_public_moment_fit_transfers_to_unseen_controls():
    world = World(7)
    records = []
    for i in range(4):
        field = [0.0] * 6
        if i:
            field[i - 1] = 0.5 * (-1) ** i
        spec = sweep(external_field=field)
        records.append({"spec": spec, "observation": world.run(spec, noise_key="training-%s" % i)})
    spec = {"temperatures": [0.42, 0.9, 1.8, 3.8], "external_field": [0, 0.4, -0.2, 0.1, 0, -0.1], "clamp": {"E": -1}, "suppress_bonds": [{"nodes": ["B", "C"], "fraction": 0.8}]}
    actual = np.asarray(world.run(spec)["values"])
    error = np.sqrt(np.mean((np.asarray(baseline(records, spec)) - actual) ** 2))
    empty_error = np.sqrt(np.mean((np.asarray(baseline([], spec)) - actual) ** 2))
    assert error < 0.01
    assert error < empty_error / 10


def test_ising_baseline_many_rows_is_finite_and_deterministic():
    world = World(16)
    records = []
    for i, spec in enumerate(world.panel(39, "development", count=12)):
        records.append({"spec": spec, "observation": world.run(spec, noise_key="train-%s" % i)})
    assert sum(len(record["spec"]["temperatures"]) for record in records) > 64
    target = sweep()
    first = baseline(records, target)
    assert first == baseline(records, target)
    assert np.isfinite(first).all()


def test_ising_metadata_and_public_examples_are_consistent():
    root = Path(__file__).parents[1]
    world = World(7)
    metadata = json.loads((root / "world.json").read_text())
    assert metadata["name"] == world.name
    assert metadata["version"] == world.version
    assert metadata["axis_field"] == world.axis_field
    assert metadata["channels"] == list(world.channels)
    assert metadata["scales"] == list(world.scales)
    assert metadata["noise_std"] == list(world.noise_std)
    plan = json.loads((root / "examples" / "experiments.json").read_text())
    assert len(plan) == 12
    assert sum(world.cost(spec) for spec in plan) == 36
    for spec in plan:
        world.validate(spec)
