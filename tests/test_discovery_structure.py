"""Handwritten observations only; no provider calls or real sealed fixtures."""
import copy
import math

import pytest

from sle.discovery_review import DiscoveryLedger
from sle.discovery_structure import pairwise_predictions, review_structures, validate_structures


def make_hypothesis(identifier):
    return {"id": identifier, "statement": "A stipulated bounded measurement for " + identifier,
            "rationale": "A manually constructed protocol fixture.",
            "assumptions": ["Measurement is descriptive."],
            "alternatives": ["Other registered numerical predictions."]}


def make_test(identifier, hypothesis_id, interval=None):
    return {"id": identifier, "phase": "replication", "tool": "measure",
            "arguments": {"sample": identifier}, "rationale": "A handwritten test plan.",
            "measurement": {"path": ["value"], "reducer": "scalar"},
            "predictions": [{"hypothesis_id": hypothesis_id, "interval": interval or [1, 2], "falsifiers": [[-2, -1]]},
                            {"hypothesis_id": "alternative", "interval": [-2, 0], "falsifiers": [[1, 2]]}]}


def make_structure(operator="all_of"):
    return [{"hypothesis_id": "compound", "operator": operator,
             "components": [{"id": identifier, "statement": "Condition " + identifier,
                             "hypothesis_id": identifier, "test_ids": ["t-" + identifier]}
                            for identifier in ("a", "b")]}]


def fixture(values=(1.5, 1.5), preobserved=False, shared_source=False):
    ledger = DiscoveryLedger("ManualFixture")
    hypotheses = [make_hypothesis(identifier) for identifier in ("compound", "a", "b", "alternative")]
    for hypothesis in hypotheses:
        ledger.append_hypothesis(hypothesis)
    tests = [make_test("t-" + identifier, identifier) for identifier in ("a", "b")]
    scope = {"sampling": "fixed_rows", "data_sha256": "handwritten-fixture", "partition": "fixture",
             "measured_columns": ["value"], "sample_ids": [1, 2]}
    if preobserved:
        ledger.record_observation("background", {"tool": "measure", "arguments": tests[0]["arguments"]},
                                  {"value": 1.5, "evidence_scope": scope})
    for test in tests:
        ledger.plan_test(test)
    for index, value in enumerate(values):
        observation = {"value": value}
        if (preobserved and index == 0) or shared_source:
            observation["evidence_scope"] = scope
        ledger.record_observation("e-" + str(index),
                                  {"tool": "measure", "arguments": tests[index]["arguments"], "test_id": tests[index]["id"]},
                                  observation)
    return hypotheses, tests, ledger._checks()


def compound_report(structures=None, **kwargs):
    hypotheses, tests, checks = fixture(**kwargs)
    report = review_structures(make_structure() if structures is None else structures, hypotheses, tests, checks)
    return report["claims"][0]


def test_all_of_necessary_failure_is_not_cancelled_by_other_compatible_component():
    claim = compound_report(values=(-1.5, 1.5))
    assert claim["operational_compatibility"] == "incompatible"
    assert claim["prospective_compatibility"] == "incompatible"
    assert claim["incompatible_component_ids"] == ["a"]
    assert claim["components"][0]["checks"][0]["explicit_falsifier_observed"] is True
    assert claim["components"][1]["operational_compatibility"] == "compatible"
    assert claim["requires_semantic_review"] is True


def test_background_failure_retained_without_granting_prospective_support():
    claim = compound_report(values=(-1.5, 1.5), preobserved=True)
    assert claim["operational_compatibility"] == "incompatible"
    assert claim["prospective_compatibility"] == "undetermined"
    background = claim["components"][0]["checks"][0]
    assert background["evidence_role"] == "background_observation"
    assert background["prospective"] is False
    assert background["explicit_falsifier_observed"] is True


def test_compatible_background_does_not_become_prospective_evidence():
    claim = compound_report(preobserved=True)
    assert claim["operational_compatibility"] == "compatible"
    assert claim["prospective_compatibility"] == "undetermined"


def test_missing_component_test_is_visible_and_blocks_all_of():
    structures = make_structure()
    structures[0]["components"][1]["test_ids"] = []
    claim = compound_report(structures=structures)
    assert claim["operational_compatibility"] == "undetermined"
    assert claim["prospective_compatibility"] == "undetermined"
    assert claim["missing_component_ids"] == ["b"]
    assert claim["components"][1]["unlinked_registered_test_ids"] == ["t-b"]


def test_pending_registered_test_is_missing_not_compatible():
    hypotheses, tests, checks = fixture(values=(1.5,))
    claim = review_structures(make_structure(), hypotheses, tests, checks)["claims"][0]
    assert claim["prospective_compatibility"] == "undetermined"
    assert claim["components"][1]["missing_test_ids"] == ["t-b"]


def test_unavailable_numeric_measurement_is_unassessed_not_passed():
    claim = compound_report(values=(1.5, None))
    assert claim["operational_compatibility"] == "undetermined"
    assert claim["components"][1]["unassessed_test_ids"] == ["t-b"]
    assert claim["components"][1]["checks"][0]["explicit_falsifier_observed"] is None


def test_any_of_exposes_missing_and_failed_alternatives_without_erasing_them():
    structures = make_structure("any_of")
    claim = compound_report(structures, values=(-1.5, 1.5))
    assert claim["operational_compatibility"] == "compatible"
    assert claim["incompatible_component_ids"] == ["a"]
    structures[0]["components"][0]["test_ids"] = []
    claim = compound_report(structures)
    assert claim["prospective_compatibility"] == "compatible"
    assert claim["missing_component_ids"] == ["a"]
    assert claim["requires_semantic_review"] is True


def test_all_compatible_predictions_never_produce_truth_or_a_score():
    hypotheses, tests, checks = fixture()
    report = review_structures(make_structure(), hypotheses, tests, checks)
    assert report["claims"][0]["prospective_compatibility"] == "compatible"
    assert report["ground_truth_used"] is False
    assert report["requires_semantic_review"] is True
    assert report["source_independence"] == "unassessed"
    assert "score" not in report and "scientific_truth" not in report


def test_no_structure_does_not_infer_support_from_compatible_tests():
    hypotheses, tests, checks = fixture()
    report = review_structures([], hypotheses, tests, checks)
    assert len(report["claims"]) == len(hypotheses)
    for claim in report["claims"]:
        assert claim["operational_compatibility"] == "undetermined"
        assert claim["prospective_compatibility"] == "undetermined"
        assert claim["review_reasons"] == ["missing_structure"]
        assert claim["requires_semantic_review"] is True


def test_reused_source_is_not_independent_even_when_both_plans_were_prospective():
    claim = compound_report(shared_source=True)
    assert claim["prospective_compatibility"] == "compatible"
    assert claim["source_independence"] == "not_independent"
    assert claim["reused_source_observations"] == ["e-0"]
    assert claim["components"][1]["checks"][0]["source_independence"] == "not_independent"


def test_same_evidence_used_in_two_components_is_listed_once_and_not_independent():
    structures = make_structure()
    structures[0]["components"][1].update({"hypothesis_id": "a", "test_ids": ["t-a"]})
    claim = compound_report(structures)
    assert claim["shared_evidence_ids"] == ["e-0"]
    assert claim["unique_evidence_ids"] == ["e-0"]
    assert claim["source_independence"] == "not_independent"


def test_omitted_test_of_component_prevents_selective_prospective_compatibility():
    hypotheses, tests, checks = fixture()
    tests.append(make_test("omitted", "a"))
    claim = review_structures(make_structure(), hypotheses, tests, checks)["claims"][0]
    assert claim["operational_compatibility"] == "compatible"
    assert claim["prospective_compatibility"] == "undetermined"
    assert claim["components"][0]["unlinked_registered_test_ids"] == ["omitted"]
    assert claim["components"][0]["test_coverage_complete"] is False


def test_same_component_cannot_vote_away_an_incompatible_registered_check():
    hypotheses, tests, checks = fixture(values=(-1.5, 1.5))
    tests[1]["predictions"][0]["hypothesis_id"] = "a"
    checks[1]["hypotheses"][0]["hypothesis_id"] = "a"
    structures = make_structure()
    structures[0]["components"] = [structures[0]["components"][0]]
    structures[0]["components"][0]["test_ids"] = ["t-a", "t-b"]
    claim = review_structures(structures, hypotheses, tests, checks)["claims"][0]
    assert claim["prospective_compatibility"] == "incompatible"
    assert [item["operational_compatibility"] for item in claim["components"][0]["checks"]] == ["incompatible", "compatible"]


def test_pairwise_predictions_keeps_identical_alternatives_when_third_differs():
    test = make_test("three-way", "a")
    test["predictions"].append({"hypothesis_id": "b", "interval": [1, 2], "falsifiers": []})
    pairs = pairwise_predictions([test])[0]["pairs"]
    assert len(pairs) == 3
    assert {(item["left_hypothesis_id"], item["right_hypothesis_id"]): item["relation"] for item in pairs} == {
        ("a", "alternative"): "disjoint", ("a", "b"): "identical", ("alternative", "b"): "disjoint"}


def test_pairwise_prediction_endpoints_are_closed_and_touching_is_overlap():
    test = make_test("touching", "a")
    test["predictions"][1].update({"interval": [2, 3], "falsifiers": []})
    assert pairwise_predictions([test])[0]["pairs"][0]["relation"] == "overlap"


@pytest.mark.parametrize("mutation", [
    lambda value: value[0].update({"hypothesis_id": "missing"}),
    lambda value: value.append(copy.deepcopy(value[0])),
    lambda value: value[0].update({"operator": "majority"}),
    lambda value: value[0].update({"components": []}),
    lambda value: value[0]["components"].append(copy.deepcopy(value[0]["components"][0])),
    lambda value: value[0]["components"][0].update({"hypothesis_id": "missing"}),
    lambda value: value[0]["components"][0].update({"hypothesis_id": "b"}),
    lambda value: value[0]["components"][0].update({"test_ids": ["missing"]}),
    lambda value: value[0]["components"][0].update({"test_ids": ["t-a", "t-a"]}),
    lambda value: value[0]["components"][0].update({"components": []}),
    lambda value: value[0]["components"][0].update({"statement": ""}),
    lambda value: value[0]["components"][0].update({"id": "bad\nidentifier"}),
])
def test_invalid_structure_and_unknown_references_are_rejected(mutation):
    hypotheses, tests, _ = fixture()
    structures = make_structure()
    mutation(structures)
    with pytest.raises(ValueError):
        validate_structures(structures, hypotheses, tests)


@pytest.mark.parametrize("mutation", [
    lambda value: value[0].update({"test_id": "missing"}),
    lambda value: value.append(copy.deepcopy(value[0])),
    lambda value: value[0].update({"value": math.nan}),
    lambda value: value[0].update({"value": True}),
    lambda value: value[0].update({"prospective": 1}),
    lambda value: value[0].update({"preregistered": False}),
    lambda value: value[0].update({"preobserved_source": ["earlier"]}),
    lambda value: value[0].update({"phase": "exploration"}),
    lambda value: value[0].update({"hypotheses": []}),
    lambda value: value[0]["hypotheses"][0].update({"compatible": False}),
    lambda value: value[0].update({"status": "unassessed"}),
])
def test_malformed_or_inconsistent_trusted_checks_are_rejected(mutation):
    hypotheses, tests, checks = fixture()
    mutation(checks)
    with pytest.raises(ValueError):
        review_structures(make_structure(), hypotheses, tests, checks)


def test_strict_json_rejects_python_tuples_integer_keys_and_excess_depth():
    hypotheses, tests, _ = fixture()
    for extra in ((1, 2), {1: "value"}, math.inf):
        altered = copy.deepcopy(hypotheses)
        altered[0]["unexpected"] = extra
        with pytest.raises(ValueError):
            validate_structures(make_structure(), altered, tests)
    nested = []
    for _ in range(34):
        nested = [nested]
    with pytest.raises(ValueError, match="structure limit"):
        validate_structures(nested, hypotheses, tests)


def test_bounds_fail_closed_instead_of_truncating_components_or_pairs():
    hypotheses, tests, _ = fixture()
    structures = make_structure()
    structures[0]["components"] *= 33
    with pytest.raises(ValueError, match="bounded list"):
        validate_structures(structures, hypotheses, tests)
    wide = make_test("wide", "a")
    wide["predictions"] = [{"hypothesis_id": "h-" + str(i), "interval": [i, i + 1], "falsifiers": []} for i in range(64)]
    many = [{**copy.deepcopy(wide), "id": str(i)} for i in range(9)]
    with pytest.raises(ValueError, match="pairwise prediction limit"):
        pairwise_predictions(many)


def test_empty_inputs_are_legal_and_outputs_never_alias_callers():
    assert review_structures([], [], [], [])["claims"] == []
    assert pairwise_predictions([]) == []
    hypotheses, tests, checks = fixture()
    structures = make_structure()
    original = copy.deepcopy((structures, hypotheses, tests, checks))
    normalized = validate_structures(structures, hypotheses, tests)
    report = review_structures(structures, hypotheses, tests, checks)
    pairs = pairwise_predictions(tests)
    normalized[0]["components"][0]["test_ids"].append("mutated")
    report["claims"][0]["components"][0]["checks"][0]["prediction_interval"][0] = -999
    pairs[0]["pairs"][0]["left_interval"][0] = -999
    assert (structures, hypotheses, tests, checks) == original
