"""Public-data refinement retains falsified programs and tests a new target."""
import copy

import numpy as np
import pytest

from env.hysteresis_material.prospective_demo import _cubic, comparison_request, source_specs
from env.hysteresis_material.refinement_demo import (choose_revision_test,
                                                     revise_cubic, revision_request)


def model(parameters):
    return {"kind": "cubic_memory", "parameters": parameters,
            "reset_response": {"negative": -1., "positive": 1.},
            "prior": "authored cubic fixture", "source_rmse": .1,
            "evidence_ids": ["source-1"]}


def test_public_counterexample_can_relax_positive_linear_prior():
    truth = model([.025, .001, -.08, .06, .07])
    original = model([0., 0., .08, .08, .07])
    specifications = source_specs() + [
        {"reset": reset, "preparation": [], "protocol": [{"time": 0., "field": 0.}],
         "times": [0., 300.]} for reset in ("negative", "positive")]
    records = []
    for i, spec in enumerate(specifications):
        initial = [truth["reset_response"][spec["reset"]]]
        fields = np.array([spec["protocol"][0]["field"]])
        values = _cubic(truth["parameters"], initial, fields, spec["times"])[0]
        records.append({"id": "public-%d" % i, "spec": spec,
                        "observation": {"axis": spec["times"], "channels": ["response"],
                                        "values": values[:, None].tolist()}})
    preserved = copy.deepcopy(records)
    revised = revise_cubic(records, original)
    assert records == preserved
    assert revised["optimizer_success"]
    assert revised["parameters"][2] < 0
    assert revised["weighted_residual_rmse"] < 1e-5
    # Check a field absent from fitting; parameter agreement alone is insufficient.
    target = _cubic(truth["parameters"], [-1., 1.], np.array([.45, .45]), [0., 30., 90.])
    forecast = _cubic(revised["parameters"], [-1., 1.], np.array([.45, .45]), [0., 30., 90.])
    assert forecast == pytest.approx(target, abs=1e-4)
    assert revised["evidence_ids"] == [r["id"] for r in records]


def test_revision_design_is_bounded_and_preserves_exact_refuted_program():
    original = model([0., 0., .09, .09, .07])
    revised = model([0., 0., -.09, .09, .07])
    revised["evidence_ids"] = ["source-1", "fresh-1", "fresh-2"]
    saved = copy.deepcopy((original, revised))
    design = choose_revision_test(original, revised)
    assert (original, revised) == saved
    assert len(design["grid"]) == 42
    assert design == choose_revision_test(original, revised)
    assert design["selection"]["prediction_separation"] == max(x["prediction_separation"] for x in design["grid"])
    request = comparison_request({"cubic_memory": original, "other": original})
    before = copy.deepcopy(request)
    followup = revision_request(request, {"test_id": "test-001"}, revised, design)
    assert request == before
    assert followup["rivals"][0] == request["rivals"][0]
    assert followup["rivals"][1]["evidence_ids"] == revised["evidence_ids"]
    assert followup["revision_of"] == "test-001"
    assert followup["replicates"] == request["replicates"] == 16
    assert all(x["tolerance"] == .07 for x in followup["rivals"])
    assert followup["experiments"][0]["spec"]["protocol"][0]["field"] != 0
