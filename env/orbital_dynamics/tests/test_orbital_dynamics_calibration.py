"""Development diagnostics retain ambiguity, negative evidence and cost scope."""

import json

import numpy as np
import pytest

from env.orbital_dynamics import World
from env.orbital_dynamics.calibrate import DEVELOPMENT_SEEDS, calibrate, matched_law_diagnostics


def test_orbital_matched_circle_is_ambiguous_but_radius_and_impulse_probes_separate():
    result = matched_law_diagnostics()
    assert max(row["max_abs_normalized_difference"] for row in result["differences"]["single_circle"]) < 1e-9
    for probe in ("new_radius", "impulse_probe"):
        assert min(row["max_abs_normalized_difference"] for row in result["differences"][probe]) > .1
    assert result["drag_short_arc_max_difference_in_paired_noise_sd"] < 1
    assert result["drag_long_arc_max_difference_in_paired_noise_sd"] > 10
    assert "unique identification" in result["interpretation"]


def test_orbital_calibration_has_public_only_baseline_fixed_counts_and_independent_error():
    assert DEVELOPMENT_SEEDS == (7, 46, 1439, 8743)
    report = calibrate([7])
    json.dumps(report, allow_nan=False)
    instance = report["instances"][0]
    assert instance["training_experiments"] == 12
    assert instance["diagnostic_query_experiments"] == 12
    assert instance["training_public_cost"] == sum(World(7).cost(r["spec"]) for r in instance["training_records"])
    assert instance["reference"]["max_error_in_noise_sd"] < .001
    assert instance["reference"]["energy_work_balance_max_abs_error"] < 2e-7
    for record in instance["training_records"]:
        assert set(record) == {"spec", "observation"}
        assert set(record["observation"]) == {"axis", "channels", "values"}
    for query in instance["queries"]:
        assert set(query["methods"]) == {"0", "4", "12"}
        for result in query["methods"].values():
            assert result["zero_time_excluded"] and np.isfinite(result["normalized_rmse"])
            assert result["cells"] == 4*(len(query["spec"]["times"])-1)
            assert 0 <= result["score"] <= 100
        assert query["numerical_work"]["rhs_evaluations"] < report["maximum_rhs_evaluations_per_production_experiment"]
    assert sum(report["development_stratum_counts"].values()) == 1


@pytest.mark.parametrize("seeds", [[], [7, 7], [True], [-1], [2**63], "7"])
def test_orbital_calibration_rejects_invalid_seed_lists(seeds):
    with pytest.raises(ValueError):
        calibrate(seeds)
