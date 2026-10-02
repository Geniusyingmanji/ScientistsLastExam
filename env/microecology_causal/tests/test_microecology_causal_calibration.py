import ast
import json
from pathlib import Path

import numpy as np

from env.microecology_causal import World
from env.microecology_causal.calibrate import calibrate
from env.microecology_causal.kernel import STRUCTURES
from env.scoring import canonical_hash


def test_causal_ecology_calibration_preserves_raw_evidence_and_disjoint_queries():
    report = calibrate()
    assert {row["development_seed"] for row in report["instances"]} == {7, 46, 1439, 8743}
    assert {row["private_structure"] for row in report["instances"]} == set(STRUCTURES)
    for row in report["instances"]:
        world = World(row["development_seed"])
        assert len(row["training_records"]) == 12 and len(row["queries"]) == 16
        hashes = {canonical_hash(record["spec"]) for record in row["training_records"]}
        for query in row["queries"]:
            assert canonical_hash(query["spec"]) not in hashes
            assert set(query["methods"]) == {"0", "4", "12"}
            assert all(0 <= metric["score"] <= 100 for metric in query["methods"].values())
        for experiment in row["experiments"].values():
            assert world.run(experiment["spec"]) == experiment["clean"]
            assert experiment["clean"] != experiment["noisy"]
        assert row["maximum_carbon_residual"] < 1e-8 and row["minimum_state"] >= 0
    assert len(report["boundaries"]["rows"]) == 24
    for row in report["boundaries"]["rows"]:
        assert row["minimum_state"] >= 0 and row["maximum_state"] <= 25
        assert row["maximum_carbon_residual"] < 1e-8
        delta = row["B_addition_delta_C_at_15h"]
        if row["private_structure"] == "feedback_cut":
            assert abs(delta) < 1e-7
        elif row["private_structure"] == "inhibitory_feedback":
            assert delta < -.1
        else:
            assert delta > .1
    assert report["baseline_summary"]["12"]["score"]["count"] == 64
    json.dumps(report, allow_nan=False)


def test_causal_ecology_manifest_examples_and_python38_syntax():
    directory = Path(__file__).resolve().parents[1]
    for path in directory.rglob("*.py"):
        ast.parse(path.read_text(), feature_version=(3, 8))
    for path in (directory / "examples").glob("*.json"):
        value = json.loads(path.read_text())
        assert World(46).validate(value)
        assert np.isfinite(World(7).run(value)["values"]).all()
    manifest = json.loads((directory / "world.json").read_text())
    assert manifest["status"] == "experimental"
    assert manifest["version"] == World.version
    assert manifest["axis_field"] == World.axis_field
    assert manifest["channels"] == list(World.channels)
    assert manifest["operator_strata"] == list(World.operator_strata)
    assert manifest["agent_public_files"] == []
