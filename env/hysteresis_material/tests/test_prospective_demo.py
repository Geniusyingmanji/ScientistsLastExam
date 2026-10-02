import ast
import copy

import numpy as np
import pytest

from env.hysteresis_material.prospective_demo import (
    SOURCE_TIMES, _cubic, comparison_request, fit_candidates, predictor_code,
    source_specs,
)
from env.hysteresis_material.world import World


def test_cubic_reference_integrator_matches_analytic_zero_field_flow():
    # Independent closed form for y' = a*y - b*y^3, including both signs.
    a, b = .1, .08
    initial = np.array([.2, -.6])
    times = np.array([0., .5, 2., 10., 40.])
    expected = (initial[:, None] * np.exp(a * times)[None, :] /
                np.sqrt(1. + (b / a) * initial[:, None] ** 2 * np.expm1(2 * a * times)[None, :]))
    actual = _cubic([0., 0., a, b, .05], initial, np.zeros(2), times)
    np.testing.assert_allclose(actual, expected, atol=5e-6, rtol=2e-5)


@pytest.mark.parametrize("seed", [7, 1439])
def test_reference_policy_fits_public_source_and_reserves_new_target(seed):
    world = World(seed)
    records = [{"id": "source-%d" % index, "spec": world.validate(spec),
                "observation": world.run(spec, noise_key="reference-test-%d" % index)}
               for index, spec in enumerate(source_specs())]
    prior = copy.deepcopy(records)
    models = fit_candidates(records)
    assert records == prior
    assert set(models) == {"relaxation", "cubic_memory"}
    for model in models.values():
        assert model["source_rmse"] < .02
        assert np.isfinite(model["parameters"]).all()
        code = predictor_code(model)
        ast.parse(code)
        assert "world_seed" not in code and "._" not in code
    request = comparison_request(models)
    assert request["replicates"] * len(request["experiments"]) + len(records) == 40
    for experiment in request["experiments"]:
        target = world.validate(experiment["spec"])
        assert target["protocol"][0]["field"] == 0
        assert all(r["spec"]["protocol"] != target["protocol"] for r in records)
    assert all(r["observation"]["axis"] == SOURCE_TIMES for r in records)
    assert request["revision_of"] is None


def test_reference_fit_rejects_changed_design_instead_of_silently_reordering():
    with pytest.raises(ValueError, match="eight source"):
        fit_candidates([])
    world = World(7)
    records = [{"id": str(index), "spec": world.validate(spec), "observation": world.run(spec)}
               for index, spec in enumerate(source_specs())]
    records[0], records[-1] = records[-1], records[0]
    with pytest.raises(ValueError, match="fixed design"):
        fit_candidates(records)
