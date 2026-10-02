"""Public-data PDE baseline checks, including external operator smoke data."""
import ast
import copy
import json
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest

from env.heat_transport import strong_baseline as strong
from env.registry import load_world


def spec(**updates):
    result = {"times": [0, .5, 1, 2, 4, 8, 16, 30], "probes": [.2, .5, .8],
              "initial_temperature": 20, "boundary_temperatures": [20, 20],
              "ambient_temperature": 20, "heaters": [{"position": .3, "power": 4, "width": .08}],
              "flow": 0, "cooling": 1}
    result.update(updates)
    return result


def public_records(seed=7, count=12):
    world, _ = load_world("heat_transport", seed)
    return [{"spec": experiment, "observation": world.run(experiment, noise_key="strong-test-%d" % index)}
            for index, experiment in enumerate(world.panel(817, "development", count))]


@pytest.fixture(autouse=True)
def clean_cache():
    strong.clear_fit_cache()
    yield
    strong.clear_fit_cache()


def test_no_record_prior_is_finite_detached_and_respects_known_initial_equilibrium():
    fit = strong.fit_public_records([])
    assert fit["model"] == "public_prior" and fit["records_used"] == 0
    output = strong.predict_fitted(fit, spec(heaters=[], flow=1, cooling=3))
    np.testing.assert_allclose(output, 20, atol=1e-9)
    fit["parameters"]["loss"] = 999
    assert strong.fit_public_records([])["parameters"]["loss"] <= .08
    heated = strong.baseline([], spec())
    assert np.asarray(heated).shape == (8, 3) and np.isfinite(heated).all()
    np.testing.assert_array_equal(heated[0], [20] * 3)


def test_public_forward_solver_matches_continuum_slab_solution():
    fit = strong.fit_public_records([])
    fit["parameters"].update(diffusivity_left=.023, diffusivity_right=.023)
    experiment = spec(heaters=[], flow=0, cooling=0, initial_temperature=40,
                      boundary_temperatures=[0, 0], times=[.5, 2, 8, 20])
    modes = np.arange(1, 601, 2, dtype=float)
    exact = (160 / np.pi * np.exp(-.023 * np.pi**2 * np.outer(experiment["times"], modes**2)).dot(
        np.sin(np.pi * np.outer(modes, experiment["probes"])) / modes[:, None]))
    np.testing.assert_allclose(strong.predict_fitted(fit, experiment), exact, atol=.018, rtol=.002)


def test_fitted_model_uses_public_records_only_and_generalizes_without_world_access():
    records = public_records()
    heldout_world, _ = load_world("heat_transport", 7)
    queries = heldout_world.panel(918, "conditions", 3) + heldout_world.panel(918, "interventions", 3)
    truths = [np.asarray(heldout_world.run(query)["values"]) for query in queries]
    before = copy.deepcopy(records)
    with patch("env.heat_transport.world.World", side_effect=AssertionError("No operator construction allowed")):
        fit = strong.fit_public_records(records)
        predictions = [np.asarray(strong.predict_fitted(fit, query)) for query in queries]
        assert np.shape(strong.baseline(records, queries[0])) == truths[0].shape
    assert records == before
    assert fit["records_used"] == 12 and fit["training_rmse"] < .08
    assert fit["identifiability"]["parameter_count"] in (3, 5)
    assert max(np.sqrt(np.mean(((predicted[1:] - truth[1:]) / 20)**2))
               for predicted, truth in zip(predictions, truths)) < .01
    json.dumps(fit, allow_nan=False)


def test_identical_public_data_reuses_fit_regardless_of_metadata_and_query():
    records = public_records(count=4)
    first = strong.fit_public_records(records)
    with patch.object(strong, "least_squares", side_effect=AssertionError("Unexpected refit")):
        altered = copy.deepcopy(records)
        for record in altered:
            record.update(world_seed="must-not-be-read", id="irrelevant")
        second = strong.fit_public_records(altered)
        strong.baseline(altered, spec(flow=.75))
    assert first == second


def test_absent_control_excitation_is_reported_as_local_rank_deficiency():
    # Public records generated from an explicitly declared uniform candidate,
    # with flow and cooling disabled: gain/loss cannot be identified here.
    truth_fit = strong.fit_public_records([])
    records = []
    for position in (.2, .4, .6, .8):
        experiment = spec(flow=0, cooling=0, heaters=[{"position": position, "power": 4, "width": .08}])
        observation = {"axis": experiment["times"], "channels": list(strong.CHANNELS),
                       "values": strong.predict_fitted(truth_fit, experiment)}
        records.append({"spec": experiment, "observation": observation})
    fit = strong.fit_public_records(records)
    assert fit["model"] == "uniform"
    assert fit["identifiability"]["local_scaled_jacobian_rank"] < fit["identifiability"]["parameter_count"]
    assert fit["identifiability"]["approximate_95_percent_halfwidth"] is None
    assert "Not identified" in fit["identifiability"]["interface_position"]


def test_malformed_records_are_ignored_and_work_bound_is_enforced():
    invalid = {"spec": spec(), "observation": {"axis": [0], "channels": list(strong.CHANNELS), "values": [[float("nan")]*3]}}
    assert strong.fit_public_records([None, {}, invalid])["model"] == "public_prior"
    with pytest.raises(ValueError):
        strong.fit_public_records([{}] * 257)
    with pytest.raises(ValueError):
        strong.fit_public_records({})
    records = public_records(count=1) * 20
    fit = strong.fit_public_records(records)
    assert fit["records_used"] == strong.MAX_FIT_RECORDS == 16


@pytest.mark.parametrize("updates", [
    {"times": []}, {"times": [0]*26}, {"times": [float("nan")]}, {"times": [True]},
    {"probes": [.2, .5]}, {"flow": 2}, {"cooling": -1}, {"initial_temperature": 10**1000},
    {"heaters": [{"position": .3, "power": 8, "width": .08}]*2}, {"unknown": 1},
])
def test_query_schema_validation(updates):
    with pytest.raises(ValueError):
        strong.baseline([], spec(**updates))


def test_module_imports_no_operator_or_world_code():
    tree = ast.parse(Path(strong.__file__).read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            assert node.level == 0 and node.module in ("scipy.linalg", "scipy.optimize")
        if isinstance(node, ast.Import):
            assert all(alias.name in {"functools", "json", "math", "numbers", "time", "numpy"}
                       for alias in node.names)
