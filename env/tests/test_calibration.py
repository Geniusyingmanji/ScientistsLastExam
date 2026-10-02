"""Calibration checks using a transparent synthetic world and a real smoke run."""
import hashlib
import json
from collections import Counter
from unittest.mock import patch

import numpy as np
import pytest

from env.calibration import _initial, _panel_seed, calibrate


class CalibrationWorld:
    name, version, axis_field = "heat_transport", "calibration-test-1", "times"
    channels, scales, noise_std = ("a", "b"), (2.0, 4.0), (0.01, 0.02)

    def __init__(self, seed):
        self.seed, self.calls = seed, []

    def validate(self, spec):
        return dict(spec)

    def cost(self, spec):
        return 2

    def panel(self, panel_seed, kind, count):
        return [{"times": [0.0, 1.0, 2.0], "initial_temperature": 2.0,
                 "control": 0.5 + (panel_seed % 17) / 20.0 + index / 10.0,
                 "kind_marker": kind} for index in range(count)]

    def run(self, spec, *, noise_key=None):
        self.calls.append(noise_key)
        coefficient = 0.5 + (self.seed % 7) / 10.0
        values = 2.0 + np.outer(spec["times"], [coefficient, 2 * coefficient]) * spec["control"]
        if noise_key is not None:
            seed = int.from_bytes(hashlib.sha256(noise_key.encode()).digest()[:8], "big")
            values += np.random.default_rng(seed).normal(size=values.shape) * self.noise_std
        return {"axis": spec["times"], "channels": list(self.channels), "values": values.tolist()}


def run_fake(*, fail_four=False, max_seconds=120):
    worlds, record_counts = [], []

    def public_baseline(records, spec):
        record_counts.append(len(records))
        if fail_four and len(records) == 4:
            raise ValueError("deliberate baseline failure")
        estimates = [(np.array(record["observation"]["values"])[-1] - 2.0) /
                     (record["spec"]["times"][-1] * record["spec"]["control"]) for record in records]
        slopes = np.mean(estimates, axis=0) if estimates else np.zeros(2)
        return (2.0 + np.outer(spec["times"], slopes) * spec["control"]).tolist()

    def loader(name, seed):
        assert name == "heat_transport"
        world = CalibrationWorld(seed)
        worlds.append(world)
        return world, public_baseline

    with patch("env.calibration.load_world", loader), patch("env.calibration.source_digest", return_value="a" * 64):
        result = calibrate(["heat_transport"], seeds=(7,), panel_count=2, max_seconds=max_seconds)
    return result, worlds, record_counts


def test_calibration_nested_noisy_prefixes_disjoint_panels_and_reproducible_metrics():
    result, worlds, counts = run_fake()
    assert result["status"] == "complete" and result["source_stable"]
    assert result["completed_instances"] == result["planned_instances"] == 1
    assert Counter(counts) == {0: 4, 4: 4, 12: 4}
    assert len(worlds[0].calls) == 16
    assert len(set(key for key in worlds[0].calls if key is not None)) == 12
    assert worlds[0].calls.count(None) == 4
    row = result["instances"][0]
    assert row["training_cost_by_record_count"] == {"0": 0, "4": 8, "12": 24}
    training = {record["spec_sha256"] for record in row["training_records"]}
    assert not training & {query["spec_sha256"] for query in row["queries"]}
    assert len(set(row["panel_seeds"].values())) == 3
    methods = result["summary"]["heat_transport"]["methods"]
    assert methods["public_12"]["score"]["mean"] > methods["public_0"]["score"]["mean"]
    for query in row["queries"]:
        assert query["methods"]["public_0"]["scored_rows"] == 2
        assert query["signal"]["active_signal_to_noise"] > 1
        assert len(query["methods"]["public_12"]["channel_rmse_raw"]) == 2
    repeated, _, _ = run_fake()
    assert repeated["instances"] == result["instances"]
    assert repeated["summary"] == result["summary"]
    json.dumps(result, allow_nan=False)


def test_failed_public_baseline_is_visible_and_counts_zero_in_score_denominator():
    result, _, _ = run_fake(fail_four=True)
    summary = result["summary"]["heat_transport"]
    item = summary["methods"]["public_4"]
    assert item["requested_predictions"] == item["invalid_predictions"] == 4
    assert item["valid_predictions"] == 0 and item["score"]["mean"] == 0
    assert item["normalized_rmse"]["count"] == 0
    assert "baseline_runtime_or_output_failure" in summary["flags"]


def test_public_initial_reference_never_uses_ising_equilibrium_truth():
    assert _initial("ising_spin", {"temperatures": [0.4, 1.0]}, ["m_A"]) is None
    assert _initial("microecology", {"initial": {"A": .1, "B": .2, "C": .3, "nutrient": 4},
                                    "events": [{"time_h": 0, "feed": 2}]}, range(7)) == [.1, .2, .3, 6, 0, 0, 0]
    assert _initial("coupled_oscillators", {"initial_position": [1, 0, 0, 0],
                                           "initial_velocity": [0, 0, 0, 0]}, range(8)) == [1, 0, 0, 0, 0, 0, 0, 0]


def test_experimental_microecology_initial_adapter_uses_only_declared_preparation():
    spec = {"initial": {"A": .1, "B": .2, "C": .3, "nutrient": 4},
            "events": [{"time_h": 0, "feed": 2}, {"time_h": 0, "feed": 1},
                       {"time_h": 0, "deplete": {"channel": "peak-01", "fraction": 1}},
                       {"time_h": 3, "feed": 3}]}
    expected = [.1, .2, .3, 7, 0, 0, 0]
    assert _initial("microecology_causal", spec, range(7)) == expected
    assert _initial("microecology", spec, range(7)) == expected
    assert spec["initial"]["nutrient"] == 4


def test_experimental_world_requires_explicit_selection_and_generic_calibration_runs():
    from env.claim_calibration import NULL_ENVIRONMENTS
    assert len(NULL_ENVIRONMENTS) == 7 and "microecology_causal" not in NULL_ENVIRONMENTS
    result = calibrate(["microecology_causal"], seeds=(7,), panel_count=1, max_seconds=20)
    assert result["status"] == "complete"
    assert len(result["instances"]) == 1
    assert set(result["summary"]) == {"microecology_causal"}
    methods = result["summary"]["microecology_causal"]["methods"]
    for method in ("zero", "initial", "public_0", "public_4", "public_12"):
        assert methods[method]["valid_predictions"] == 2
        assert methods[method]["invalid_predictions"] == 0


def test_panel_seeds_are_stable_and_namespaced_by_purpose_world_and_family():
    assert _panel_seed("heat_transport", 7, "conditions") == _panel_seed("heat_transport", 7, "conditions")
    values = [_panel_seed(name, seed, kind) for name in ("heat_transport", "ising_spin")
              for seed in (7, 46) for kind in ("development", "conditions", "interventions")]
    assert len(set(values)) == len(values)
    assert all(0 <= value < 2**63 for value in values)


def test_budget_exhaustion_is_explicit_not_a_successful_empty_calibration():
    with patch("env.calibration.time.monotonic", side_effect=[0.0, 1.0, 1.0]):
        result, worlds, _ = run_fake(max_seconds=.5)
    assert not worlds and result["status"] == "budget_exhausted"
    assert result["completed_instances"] == 0 and result["planned_instances"] == 1
    assert result["summary"]["heat_transport"]["methods"]["public_12"]["score"]["mean"] is None


def test_training_eval_overlap_is_rejected():
    world = CalibrationWorld(7)
    identical = {"times": [0.0, 1.0], "initial_temperature": 2.0, "control": 1.0}
    world.panel = lambda seed, kind, count: [dict(identical) for _ in range(count)]
    with patch("env.calibration.load_world", return_value=(world, lambda records, spec: [])), patch("env.calibration.source_digest", return_value="a" * 64):
        with pytest.raises(ValueError, match="overlap"):
            calibrate(["heat_transport"], seeds=(7,), panel_count=1)


@pytest.mark.parametrize("kwargs", [
    {"names": []}, {"names": ["unknown"]}, {"names": ["heat_transport", "heat_transport"]},
    {"names": [[]]}, {"seeds": ()}, {"seeds": (True,)}, {"seeds": (-1,)}, {"seeds": (7, 7)},
    {"panel_count": 0}, {"panel_count": 9}, {"panel_count": True},
    {"max_seconds": 0}, {"max_seconds": float("nan")}, {"max_seconds": 10**1000},
])
def test_calibration_work_limits(kwargs):
    arguments = dict(names=["heat_transport"], seeds=(7,), panel_count=1)
    arguments.update(kwargs)
    with pytest.raises(ValueError):
        calibrate(**arguments)


def test_real_registry_heat_smoke_uses_all_baselines_and_finite_json():
    result = calibrate(["heat_transport"], seeds=(7,), panel_count=1, max_seconds=10)
    assert result["status"] == "complete"
    assert result["summary"]["heat_transport"]["queries"] == 2
    assert all(summary["valid_predictions"] == 2 for summary in result["summary"]["heat_transport"]["methods"].values())
    json.dumps(result, allow_nan=False)
