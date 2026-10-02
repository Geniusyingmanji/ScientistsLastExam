"""Independent numerical, material-balance and causal-structure checks."""

import ast
import copy
import json
from pathlib import Path

import numpy as np
import pytest
from scipy.integrate import solve_ivp

from env.microecology_causal import World, baseline
from env.microecology_causal.calibrate import culture, matched_structure_diagnostics
from env.microecology_causal.kernel import A, B, C, S, W, X, Y, Z, Kernel, Parameters, STRUCTURES
from env.microecology_causal.protocol import example


def _reference(world, spec):
    """Independent transfer-matrix RHS and DOP853 event/observation stepping."""
    p, structure = world._kernel.parameters, world.operator_stratum()
    matrix = np.zeros((8, 8))
    matrix[:, 0] = [-1, .4, 0, 0, .35, 0, .25, 0]
    matrix[:, 1] = [0, 0, .45, 0, -1, .55, 0, 0]
    matrix[C, 2], matrix[W, 2] = .5, .5
    matrix[Y if structure == "direct_toxin_detox" else Z, 2] = -1
    for col, pool in enumerate((A, B, C, X, Y), 3):
        matrix[pool, col], matrix[W, col] = -1, 1

    def derivative(time, raw, temperature):
        state = np.maximum(raw, 0)
        inhibition_a = state[Y] if structure == "direct_toxin_detox" else state[Z]
        substrate_c = state[Y] if structure == "direct_toxin_detox" else state[Z]
        consumer_factor = 1 / (1 + (state[Y] / p.inhibition_consumer)**2) if structure == "inhibitory_feedback" else 1
        rates = [p.uptake_a * state[A] * state[S] / (p.half_s + state[S]) / (1 + (inhibition_a / p.inhibition_producer)**2),
                 p.uptake_b * state[B] * state[X] / (p.half_x + state[X]),
                 p.uptake_c * state[C] * substrate_c / (p.half_consumer + substrate_c) * consumer_factor,
                 p.death * state[A], p.death * state[B], p.death * state[C], p.decay_x * state[X], p.decay_y * state[Y]]
        return matrix.dot(np.asarray(rates)) * 2**((temperature - 30) / 10)

    state = np.zeros(8)
    state[:4] = [spec["initial"][key] for key in ("nutrient", "A", "B", "C")]
    temperature, current, cursor, rows = spec["temperature_c"], 0.0, 0, []

    def advance(state, end, temp):
        if end == current:
            return state
        solution = solve_ivp(lambda t, y: derivative(t, y, temp), (current, end), state,
                             method="DOP853", rtol=2e-11, atol=2e-13, max_step=.1)
        assert solution.success
        return solution.y[:, -1]

    for target in spec["times_h"]:
        while cursor < len(spec["events"]) and spec["events"][cursor]["time_h"] <= target:
            event = spec["events"][cursor]
            state = advance(state, event["time_h"], temperature)
            current = event["time_h"]
            if "feed" in event:
                state[S] += event["feed"]
            elif "temperature_c" in event:
                temperature = event["temperature_c"]
            else:
                idx = world._indices[world.channels.index(event["deplete"]["channel"])]
                state[idx] *= 1 - event["deplete"]["fraction"]
            cursor += 1
        state = advance(state, target, temperature)
        current = target
        rows.append(state.copy())
    return np.asarray(rows)


@pytest.mark.parametrize("seed", [7, 46, 1439])
def test_causal_ecology_independent_transfer_matrix_and_events(seed):
    world = World(seed)
    spec = world.validate(culture(times=[0, 2, 6, 9, 12, 18, 24, 36, 48], events=[
        {"time_h": 0, "feed": 1}, {"time_h": 9, "deplete": {"channel": "peak-02", "fraction": .9}},
        {"time_h": 12, "temperature_c": 37}, {"time_h": 24, "feed": 2}]))
    actual, _, _ = world._trajectory(spec)
    np.testing.assert_allclose(actual, _reference(world, spec), atol=3e-7, rtol=3e-7)


@pytest.mark.parametrize("seed", [7, 46, 1439])
def test_causal_ecology_analytic_starvation_and_temperature_clock(seed):
    world = World(seed)
    spec = culture(a=.2, b=.4, c=.6, times=[0, 2, 6, 12, 24], events=[{"time_h": 6, "temperature_c": 40}])
    spec["initial"]["nutrient"] = 0
    state, _, _ = world._trajectory(world.validate(spec))
    effective = np.minimum(spec["times_h"], 6) + 2 * np.maximum(np.asarray(spec["times_h"]) - 6, 0)
    expected = np.asarray([.2, .4, .6])[None, :] * np.exp(-world._kernel.parameters.death * effective[:, None])
    np.testing.assert_allclose(state[:, [A, B, C]], expected, atol=2e-9)
    np.testing.assert_allclose(state[:, W], 1.2 - expected.sum(axis=1), atol=2e-9)
    np.testing.assert_array_equal(state[:, [S, X, Y, Z]], 0)


@pytest.mark.parametrize("structure", STRUCTURES)
def test_causal_ecology_carbon_flux_identity_and_inward_boundary(structure):
    kernel = Kernel(Parameters(), structure)
    rng = np.random.default_rng(134)
    for _ in range(50):
        state = rng.uniform(0, 8, 8)
        derivative = kernel.derivative(0, state, 40)
        assert abs(derivative.sum()) < 1e-12
        for pool in range(8):
            boundary = state.copy()
            boundary[pool] = 0
            assert kernel.derivative(0, boundary, 40)[pool] >= 0


def test_causal_ecology_consumer_removes_only_its_actual_substrate():
    p = Parameters()
    for structure in STRUCTURES:
        kernel = Kernel(p, structure)
        active = Y if structure == "direct_toxin_detox" else Z
        inactive = Z if active == Y else Y
        for concentration in (.01, .5, 4):
            state = np.zeros(8)
            state[C] = .3
            state[inactive] = concentration
            derivative = kernel.derivative(0, state, 30)
            assert derivative[C] == pytest.approx(-p.death * .3)
            expected_decay = -p.decay_y * concentration if inactive == Y else 0.0
            assert derivative[inactive] == pytest.approx(expected_decay)
            state[active] = concentration
            derivative = kernel.derivative(0, state, 30)
            assert derivative[C] > -p.death * .3
            assert derivative[inactive] == pytest.approx(expected_decay)
            assert derivative.sum() == pytest.approx(0, abs=1e-12)


@pytest.mark.parametrize("seed", [7, 46, 1439, 8743])
def test_causal_ecology_extreme_legal_material_accounting_and_nonnegativity(seed):
    world = World(seed)
    scenarios = [culture(a=1, b=1, c=1, times=np.linspace(0, 72, 32).tolist(), events=[
        {"time_h": 0, "feed": 3}, {"time_h": 12, "feed": 3}, {"time_h": 36, "feed": 3}, {"time_h": 72, "feed": 3}]),
        culture(a=1, b=0, c=1, times=[0, 6, 12, 24, 48, 72], events=[
            {"time_h": 12, "deplete": {"channel": "peak-01", "fraction": 1}},
            {"time_h": 24, "deplete": {"channel": "peak-02", "fraction": 1}},
            {"time_h": 48, "deplete": {"channel": "peak-03", "fraction": 1}}, {"time_h": 72, "feed": 3}])]
    for spec in scenarios:
        spec["initial"]["nutrient"] = 10
        spec["temperature_c"] = 40
        canonical = world.validate(spec)
        state, added, removed = world._trajectory(canonical)
        total = sum(canonical["initial"].values())
        assert np.isfinite(state).all() and state.min() >= 0 and state.max() <= 25
        np.testing.assert_allclose(state.sum(axis=1) + removed - added, total, atol=1e-8)
        assert np.all(np.diff(state[:, W]) >= -1e-8)
        if spec["initial"]["B"] == 0:
            np.testing.assert_array_equal(state[:, B], 0)


def test_causal_ecology_exact_event_observation_order_and_temperature_order():
    world = World(46)
    spec = culture(times=[0, 12, 18, 24])
    control = np.asarray(world.run(spec)["values"])
    depletion = copy.deepcopy(spec)
    depletion["events"] = [{"time_h": 12, "deplete": {"channel": "peak-01", "fraction": .75}},
                            {"time_h": 12, "deplete": {"channel": "peak-01", "fraction": .5}}, {"time_h": 12, "feed": 2}]
    treated = np.asarray(world.run(depletion)["values"])
    assert treated[1, 4] == pytest.approx(control[1, 4] * .25 * .5, abs=1e-8)
    assert treated[1, 3] == pytest.approx(control[1, 3] + 2, abs=1e-8)
    np.testing.assert_allclose(treated[1, [0, 1, 2, 5, 6]], control[1, [0, 1, 2, 5, 6]], atol=1e-8)
    first = copy.deepcopy(spec)
    first["events"] = [{"time_h": 0, "temperature_c": 20}, {"time_h": 0, "temperature_c": 40}]
    last = copy.deepcopy(spec)
    last["temperature_c"] = 40
    np.testing.assert_allclose(world.run(first)["values"], world.run(last)["values"], atol=1e-12)


def test_causal_ecology_structural_equivalence_has_explicit_restricted_scope():
    diagnosis = matched_structure_diagnostics()
    assert diagnosis["feedback_vs_cut_B_absent_max_abs_difference"] < 2e-7
    abc = [np.asarray(arm["ABC"]["values"]) for arm in diagnosis["arms"]]
    assert np.max(np.abs(abc[0] - abc[1])) > .1
    assert np.max(np.abs(abc[0] - abc[2])) > .1
    # In a short, shared-parameter experiment differences remain far below the
    # single paired observation noise; this is finite-information ambiguity.
    assert max(row["early_max_abs_difference_in_paired_noise_sd"] for row in diagnosis["early_pair_distances"]) < .1


@pytest.mark.parametrize("seed", [7, 46, 1439, 8743])
def test_causal_ecology_development_inoculum_contrasts_are_resolvable(seed):
    world = World(seed)
    abc = np.asarray(world.run(culture())["values"])
    ac = np.asarray(world.run(culture(b=0))["values"])
    difference = abc - ac
    at_15 = 6
    structure = world.operator_stratum()
    if structure == "feedback_cut":
        np.testing.assert_allclose(difference[:, [0, 2, 3]], 0, atol=1e-7)
    elif structure == "inhibitory_feedback":
        assert difference[at_15, 0] < -.1 and difference[at_15, 2] < -.1
        assert difference[-1, 2] > 0  # Late sign change is real, not a timeless edge label.
    else:
        assert difference[at_15, 2] > .1
        assert difference[4, 0] < -.02  # The transient direct inhibition is observable.


@pytest.mark.parametrize("seed", [7, 46, 1439, 8743])
def test_causal_ecology_fraction_depletion_resolves_direct_vs_mediated_effect(seed):
    world = World(seed)
    control = culture(c=0)
    reference = np.asarray(world.run(control)["values"])
    effects = {}
    for internal in (Y, Z):
        peak = world.channels[world._indices.index(internal)]
        treatment = culture(c=0, events=[{"time_h": 9, "deplete": {"channel": peak, "fraction": .9}}])
        effects[internal] = np.asarray(world.run(treatment)["values"])[5, 0] - reference[5, 0]
    # Read A three hours after depletion, never the directly removed channel.
    active = Y if world.operator_stratum() == "direct_toxin_detox" else Z
    inactive = Z if active == Y else Y
    assert effects[active] > .15
    assert abs(effects[inactive]) < 1e-7


def test_causal_ecology_public_description_same_across_structures_and_noise_replay():
    worlds = [World(seed) for seed in (7, 46, 1439, 8743)]
    assert {world.operator_stratum() for world in worlds} == set(STRUCTURES)
    descriptions = [world.describe() for world in worlds]
    assert all(description == descriptions[0] for description in descriptions)
    description = json.dumps(descriptions[0], allow_nan=False)
    for forbidden in STRUCTURES + ("_indices", "_seed", "operator_strata", "uptake_a", "inhibition_producer"):
        assert forbidden not in description
    for world in worlds:
        spec = example()
        assert world.run(spec) == World(world._seed).run(spec)
        assert world.run(spec, noise_key="same") == world.run(spec, noise_key="same")
        assert world.run(spec, noise_key="same") != world.run(spec, noise_key="other")
        observation = world.run(spec)
        assert set(observation) == {"axis", "channels", "values"}
        assert np.asarray(observation["values"]).shape == (len(spec["times_h"]), 7)
        assert observation["channels"] == list(world.channels)
        assert world.cost(spec) == 8 + len(spec["times_h"]) + 2 + 6
    assert worlds[0].run(example()) != worlds[1].run(example())


def test_causal_ecology_observation_grid_invariance_and_clipped_noise_scale():
    world = World(46)
    sparse = culture(times=[0, 6, 12, 24, 48], events=[{"time_h": 12, "feed": 1}])
    dense = dict(sparse, times_h=[0, 1, 3, 6, 9, 12, 15, 24, 36, 48])
    np.testing.assert_allclose(np.asarray(world.run(dense)["values"])[[dense["times_h"].index(t) for t in sparse["times_h"]]],
                               world.run(sparse)["values"], atol=1e-11)
    zero = culture(a=0, b=0, c=0, times=[0])
    zero["initial"]["nutrient"] = 0
    values = np.asarray([world.run(zero, noise_key="zero-%d" % i)["values"][0] for i in range(1024)])
    assert values.min() == 0
    np.testing.assert_allclose(values.mean(axis=0) / world.noise_std, 1 / np.sqrt(2 * np.pi), atol=.045)


@pytest.mark.parametrize("value", [True, None, "1", float("nan"), float("inf"), 10**1000, -1, 73])
def test_causal_ecology_rejects_nonfinite_bad_times(value):
    spec = culture(times=[value])
    with pytest.raises(ValueError):
        World(7).validate(spec)


@pytest.mark.parametrize("change", [
    lambda s: s.update(extra=1), lambda s: s.update(times_h=[]), lambda s: s.update(times_h=list(range(33))),
    lambda s: s.update(times_h=[0, 0]), lambda s: s["initial"].update(A=1.1),
    lambda s: s.update(temperature_c=41), lambda s: s.update(events=[{"time_h": 0, "feed": 1}] * 5),
    lambda s: s.update(events=[{"time_h": 73, "feed": 1}]),
    lambda s: s.update(events=[{"time_h": 0, "feed": 4}]),
    lambda s: s.update(events=[{"time_h": 0, "feed": 1, "temperature_c": 30}]),
    lambda s: s.update(events=[{"time_h": 12, "feed": 1}, {"time_h": 6, "feed": 1}]),
    lambda s: s.update(events=[{"time_h": 0, "deplete": {"channel": [], "fraction": .5}}]),
    lambda s: s.update(events=[{"time_h": 0, "deplete": {"channel": "A", "fraction": .5}}]),
    lambda s: s.update(events=[{"time_h": 0, "deplete": {"channel": "peak-01", "fraction": True}}]),
])
def test_causal_ecology_invalid_schema_and_work_bounds(change):
    spec = culture()
    change(spec)
    with pytest.raises(ValueError):
        World(7).validate(spec)


def test_causal_ecology_panels_private_seed_independent_and_baseline_public_only(monkeypatch):
    world = World(46)
    for kind in ("development", "conditions", "interventions"):
        panel = world.panel(123, kind, 8)
        assert panel == World(7).panel(123, kind, 8)
        assert panel != world.panel(124, kind, 8)
        assert all(world.validate(spec) == spec for spec in panel)
        assert all(np.isfinite(world.run(spec)["values"]).all() for spec in panel)
        if kind == "interventions":
            assert {next(key for key in spec["events"][0] if key != "time_h") for spec in panel} == {"deplete", "feed", "temperature_c"}
    spec = world.panel(1, "development", 1)[0]
    observation = world.run(spec, noise_key="public-baseline")
    record = {"spec": spec, "observation": observation}
    preserved = copy.deepcopy(record)
    monkeypatch.setattr(World, "run", lambda *args, **kwargs: pytest.fail("baseline cannot query a hidden world"))
    assert baseline([record], spec) == observation["values"]
    assert np.asarray(baseline([], spec)).shape == (len(spec["times_h"]), 7)
    assert record == preserved
    path = Path(__file__).resolve().parents[1] / "baseline.py"
    imports = [node.module for node in ast.walk(ast.parse(path.read_text())) if isinstance(node, ast.ImportFrom)]
    assert imports == ["protocol"]
    with pytest.raises(ValueError):
        baseline([{}], spec)


def test_causal_ecology_seed_noise_panel_validation():
    for seed in (True, -1, 2**63, .5, "1"):
        with pytest.raises(ValueError):
            World(seed)
    world = World(7)
    for key in (1, {}, "x" * 257):
        with pytest.raises(ValueError):
            world.run(culture(), noise_key=key)
    for count in (0, 65, True):
        with pytest.raises(ValueError):
            world.panel(1, "development", count)
    for kind in (None, [], "unknown"):
        with pytest.raises(ValueError):
            world.panel(1, kind)
