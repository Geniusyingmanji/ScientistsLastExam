import ast
import json
from pathlib import Path

import numpy as np
import pytest

from env.hysteresis_material.calibrate import calibrate
from env.hysteresis_material import World
from env.scoring import canonical_hash


def test_hysteresis_calibration_raw_replay_and_disjoint_panels():
    report = calibrate(seeds=[7, 1439])
    assert report["seeds"] == [7, 1439]
    assert len(report["instances"]) == 2
    assert {row["private_family"] for row in report["instances"]} == {"relaxation", "bistable"}
    for row in report["instances"]:
        world = World(row["development_seed"])
        assert len(row["training_records"]) == 12
        train_hashes = {canonical_hash(record["spec"]) for record in row["training_records"]}
        assert len(row["queries"]) == 16
        assert {query["kind"] for query in row["queries"]} == {"conditions", "interventions"}
        for query in row["queries"]:
            assert canonical_hash(query["spec"]) not in train_hashes
            assert world.run(query["spec"]) == query["clean"]
            assert set(query["methods"]) == {"0", "4", "12"}
            for metric in query["methods"].values():
                assert metric["normalized_rmse"] >= 0.0
                assert 0.0 <= metric["score"] <= 100.0
        for loop in row["diagnostics"]["loops"]:
            assert loop["clean"] == world.run(loop["spec"])
            assert loop["clean"] != loop["noisy"]
        diagnostic = row["diagnostics"]
        if row["private_family"] == "relaxation":
            assert abs(diagnostic["memory_difference"][-1]) < 1e-8
            assert diagnostic["slow_fast_area_ratio"] < 0.08
        else:
            assert diagnostic["memory_difference_snr"][-1] > 150.0
            assert diagnostic["loops"][-1]["clean_area"] > 0.8
    assert report["baseline_summary"]["0"]["score"]["count"] == 32
    assert report["baseline_summary"]["0"]["score"]["mean"] < 10
    json.dumps(report, allow_nan=False)


def test_hysteresis_baseline_calibration_bounds():
    for seeds in ([], [7, 7], [True], list(range(17)), "7"):
        with pytest.raises(ValueError):
            calibrate(seeds)


def test_hysteresis_python38_syntax_and_public_examples():
    directory = Path(__file__).resolve().parents[1]
    for source in directory.rglob("*.py"):
        ast.parse(source.read_text(), feature_version=(3, 8))
    for path in (directory / "examples").glob("*.json"):
        spec = json.loads(path.read_text())
        assert World(7).validate(spec)
        assert np.isfinite(World(1439).run(spec)["values"]).all()
    manifest = json.loads((directory / "world.json").read_text())
    assert manifest["axis_field"] == World.axis_field
    assert manifest["channels"] == list(World.channels)
    assert manifest["normalization_scales"] == list(World.scales)
    assert manifest["measurement_noise_std"] == list(World.noise_std)
    assert manifest["agent_public_files"] == []
