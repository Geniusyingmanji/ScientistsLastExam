"""Batch adapter regression and scientific invariants, without model calls."""
import copy
import json

import numpy as np
import pytest
from scipy.integrate import solve_ivp

from env.microecology.kernel import Mechanism, MicroecologyKernel
from env.microecology.world import World, baseline


def spec(**changes):
    value = {"initial": {"A": 0.06, "B": 0.05, "C": 0.04, "nutrient": 4.0},
             "temperature_c": 30.0, "times_h": [0.0, 4.0, 12.0, 24.0, 48.0], "events": []}
    value.update(changes)
    return value


def test_batch_matches_independent_integration_of_original_carbon_balanced_kernel():
    seed = 273
    world = World(seed)
    kernel = MicroecologyKernel(Mechanism.generate(seed))
    experiment = spec(temperature_c=32.0)
    initial = np.array([4.0, 0.06, 0.05, 0.04, 0.0, 0.0, 0.0, 0.0])
    integrated = solve_ivp(lambda t, y: kernel.derivative(t, y, 32.0), (0.0, 48.0), initial,
                           t_eval=experiment["times_h"], method="Radau", rtol=2e-10, atol=2e-12)
    assert integrated.success
    # The public anonymous channel permutation is deliberately instance-specific.
    expected = integrated.y[world._indices].T
    observed = np.asarray(world.run(experiment)["values"])
    np.testing.assert_allclose(observed, expected, rtol=3e-7, atol=1e-8)
    np.testing.assert_allclose(integrated.y.sum(axis=0), initial.sum(), rtol=0, atol=2e-9)
    assert observed.min() >= 0
    assert np.all(observed.sum(axis=1) <= initial.sum() + 1e-8)


def test_zero_inoculum_and_temperature_step_follow_exact_death_solution():
    world = World(21)
    experiment = spec(initial={"A": 0.0, "B": 0.4, "C": 0.0, "nutrient": 3.0},
                      times_h=[0, 4, 8, 16, 24],
                      events=[{"time_h": 8, "temperature_c": 40}, {"time_h": 8, "feed": 2}])
    result = np.asarray(world.run(experiment)["values"])
    time = np.asarray(experiment["times_h"])
    scaled_hours = np.minimum(time, 8) + 2 * np.maximum(time - 8, 0)
    expected_b = 0.4 * np.exp(-world._kernel.mechanism.death * scaled_hours)
    np.testing.assert_allclose(result[:, 1], expected_b, atol=2e-10)
    np.testing.assert_array_equal(result[:, [0, 2, 4, 5, 6]], 0)
    np.testing.assert_array_equal(result[:, 3], [3, 3, 5, 5, 5])


def test_event_at_observation_time_happens_before_measurement():
    world = World(22)
    control = spec(times_h=[0, 12])
    before = np.asarray(world.run(control)["values"])
    channel = world.channels[4 + int(np.argmax(before[-1, 4:]))]
    experiment = spec(times_h=[0, 12], events=[{"time_h": 12, "deplete": {"channel": channel, "fraction": 0.75}}])
    after = np.asarray(world.run(experiment)["values"])
    index = world.channels.index(channel)
    expected = before.copy()
    expected[-1, index] *= 0.25
    np.testing.assert_allclose(after, expected, rtol=0, atol=1e-10)
    fed = spec(times_h=[0], events=[{"time_h": 0, "feed": 2}])
    assert world.run(fed)["values"][0][3] == 6


def test_batch_reproducibility_clean_reset_noise_and_public_separation():
    world = World(23)
    experiment = spec()
    clean = world.run(experiment)
    assert clean == world.run(experiment) == World(23).run(experiment)
    assert clean != World(24).run(experiment)
    first = world.run(experiment, noise_key="replicate-a")
    assert first == world.run(experiment, noise_key="replicate-a")
    assert first != world.run(experiment, noise_key="replicate-b")
    assert set(first) == {"axis", "channels", "values"}
    assert world.describe() == World(24).describe()
    for forbidden in ("uptake_a", "half_x", "channel-permutation", "_seed"):
        assert forbidden not in json.dumps(world.describe())
    assert first["axis"] == experiment["times_h"]
    assert np.asarray(first["values"]).shape == (5, 7)
    assert np.min(first["values"]) >= 0
    with pytest.raises(ValueError):
        world.run(experiment, noise_key=123)


@pytest.mark.parametrize("change", [
    {"times_h": []}, {"times_h": [0, 0]}, {"times_h": [2, 1]}, {"times_h": [float("nan")]},
    {"times_h": [0] * 33}, {"times_h": [73]}, {"temperature_c": True}, {"temperature_c": 19},
    {"initial": {"A": -1, "B": 0, "C": 0, "nutrient": 1}},
    {"events": [{"time_h": 49, "feed": 1}]},
    {"events": [{"time_h": 0, "feed": 1, "temperature_c": 30}]},
    {"events": [{"time_h": 10, "feed": 1}, {"time_h": 5, "feed": 1}]},
    {"events": [{"time_h": 0, "deplete": {"channel": "unknown", "fraction": 1}}]},
    {"events": [{"time_h": 0, "deplete": {"channel": "peak-01", "fraction": 1.1}}]},
    {"events": [{"time_h": 0, "feed": 1}] * 5}, {"unknown": 1},
])
def test_batch_validation_rejects_bounded_work_and_shape_errors(change):
    world = World(25)
    with pytest.raises(ValueError):
        world.validate(spec(**change))


def test_batch_canonicalization_cost_and_baseline_public_record_shape():
    world = World(26)
    request = {"initial": {"A": 0.1, "B": 0, "C": 0, "nutrient": 3}, "times_h": [0, 12]}
    saved = copy.deepcopy(request)
    canonical = world.validate(request)
    assert request == saved
    assert canonical["temperature_c"] == 30 and canonical["events"] == []
    assert world.cost(request) == 11
    canonical["initial"]["A"] = 0.9
    assert request == saved
    observed = world.run(request)
    records = [{"spec": world.validate(request), "observation": observed}]
    np.testing.assert_allclose(baseline(records, request), observed["values"])
    assert np.shape(baseline([], request)) == (2, 7)
    assert np.isfinite(baseline([], request)).all()


def test_batch_panels_are_valid_reproducible_and_have_interventions():
    world = World(27)
    for kind in ("development", "conditions", "interventions"):
        first = world.panel(551, kind, 4)
        assert first == world.panel(551, kind, 4) == World(28).panel(551, kind, 4)
        assert first != world.panel(552, kind, 4)
        for item in first:
            assert world.validate(item) == item
            if kind == "interventions":
                assert item["events"]
    for kind, count in (("missing", 4), ("conditions", 0), ("conditions", 65), ("conditions", True)):
        with pytest.raises(ValueError):
            world.panel(1, kind, count)


def test_batch_huge_finite_json_integer_is_a_validation_error():
    world = World(28)
    with pytest.raises(ValueError):
        world.validate(spec(temperature_c=10**1000))
