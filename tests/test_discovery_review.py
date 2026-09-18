"""Adversarial controls for operational evidence review without an oracle."""
import copy
import math

import pytest

from sle.discovery_review import DiscoveryLedger


def hypothesis(identifier="effect"):
    return {"id": identifier, "statement": "The measured shift exceeds the reference range.",
            "rationale": "An independently checked calibration distinguishes the predictions.",
            "assumptions": ["The assay retains the stated calibration."],
            "alternatives": ["A reference-compatible result or calibration drift."]}


def test_plan(identifier="test-1", phase="exploration", intervals=None):
    intervals = intervals or [[1.0, 2.0], [-0.5, 0.5]]
    return {"id": identifier, "phase": phase, "tool": "measure",
            "arguments": {"sample": identifier}, "rationale": "A prospectively chosen discriminating measurement.",
            "measurement": {"path": ["values"], "reducer": "mean"},
            "predictions": [{"hypothesis_id": key, "interval": bounds, "falsifiers": []}
                            for key, bounds in zip(["effect", "null"], intervals)]}


# This helper is data, not a pytest test.
test_plan.__test__ = False


def ledger():
    result = DiscoveryLedger("MeasurementAudit")
    result.append_hypothesis(hypothesis())
    result.append_hypothesis(hypothesis("null"))
    return result


def execute(record, plan, observation=None, evidence_id="experiment-0001"):
    return record.record_observation(evidence_id,
                                     {"tool": plan["tool"], "arguments": plan["arguments"], "test_id": plan["id"]},
                                     {"values": [1.25, 1.75]} if observation is None else observation)


def dossier(hypothesis_id="effect", conclusion="supported", support=None, counter=None, tests=None, replications=None):
    return {"claims": [{"hypothesis_id": hypothesis_id, "conclusion": conclusion,
                         "support": ["experiment-0001"] if support is None else support,
                         "counterevidence": [] if counter is None else counter,
                         "tests": [] if tests is None else tests,
                         "limitations": ["This is an operational prediction, not a causal identification."]}],
            "replication_tests": [] if replications is None else replications,
            "limitations": ["Novelty requires external scientific review."]}


def test_discriminating_prospective_evidence_is_not_a_truth_or_text_score():
    record = ledger()
    plan = test_plan()
    record.plan_test(plan)
    execute(record, plan)
    report = record.review_dossier(dossier())
    assert report["claims"][0]["evidence_status"] == "evidence-supported"
    assert report["ground_truth_used"] is False
    assert report["judge_model_used"] is False
    assert report["discovery_score"] is None
    assert report["process"]["preregistered_observation_fraction"]["value"] == 1
    assert report["requires_scientific_review"]


def test_semantic_rubric_requires_independent_artifact_grounded_assessment():
    record = ledger()
    plan = test_plan()
    record.plan_test(plan)
    execute(record, plan)
    report = record.review_dossier(dossier())
    rubric = report["semantic_review"]
    assert rubric["status"] == "unassessed"
    assert rubric["assessor"] is None
    assert {axis["axis"] for axis in rubric["axes"]} == {
        "scientific_question", "hypothesis_operationalization", "competing_explanations",
        "experimental_rationale", "inference_warrant", "uncertainty_and_selection",
        "reproducibility", "novelty_and_scope"}
    for axis in rubric["axes"]:
        assert axis["status"] == "unassessed"
        assert axis["assessment"] is None
        assert axis["assessment_evidence_references"] == []
        assert axis["required_evidence_references"]
    inference = next(axis for axis in rubric["axes"] if axis["axis"] == "inference_warrant")
    assert inference["available_references"]["native_evidence_ids"] == ["experiment-0001"]


def test_null_discovery_is_valid_but_no_observation_yields_no_perfect_score():
    record = DiscoveryLedger("MeasurementAudit")
    report = record.review_dossier({"claims": [], "replication_tests": [], "limitations": []})
    assert report["null_discovery"] is True
    assert report["claims"] == []
    assert all(metric["value"] is None for metric in report["process"].values() if isinstance(metric, dict))
    assert report["prospective_checks"]["discriminating_checks"]["value"] is None


def test_posthoc_plan_cannot_relabel_an_existing_exploratory_observation():
    record = ledger()
    plan = test_plan()
    record.record_observation("experiment-0001", {"tool": "measure", "arguments": plan["arguments"]}, {"values": [1.5]})
    record.plan_test(plan)
    report = record.review_dossier(dossier())
    assert report["claims"][0]["evidence_status"] == "unassessed"
    assert report["claims"][0]["unverified_support_citations"] == ["experiment-0001"]
    assert report["process"]["preregistered_observation_fraction"]["value"] == 0
    with pytest.raises(ValueError, match="immutable"):
        execute(record, plan)


def scoped(values=None, rows=None, columns=None, partition="exploration"):
    return {"values": [1.5] if values is None else values,
            "evidence_scope": {"data_sha256": "a" * 64, "partition": partition,
                               "measured_columns": ["response"] if columns is None else columns,
                               "sample_ids": ["row-1"] if rows is None else rows,
                               "sampling": "fixed_rows"}}


def test_raw_read_then_planned_summary_of_same_rows_is_descriptive_only():
    record = ledger()
    record.record_observation("raw-read", {"tool": "read", "arguments": {"columns": ["response"]}}, scoped())
    plan = test_plan()
    record.plan_test(plan)
    execute(record, plan, scoped())
    report = record.review_dossier(dossier())
    assert report["claims"][0]["evidence_status"] == "unassessed"
    check = report["checks"][0]
    assert check["preregistered"] is True
    assert check["prospective"] is False
    assert check["preobserved_source"] == ["raw-read"]
    assert check["hypotheses"][0]["compatible"] is True
    assert check["hypotheses"][0]["discriminating_support"] is False
    assert report["process"]["preregistered_observation_fraction"]["value"] == 0


def test_repeating_fixed_query_after_seeing_result_is_not_prospective():
    record = ledger()
    plan = test_plan()
    record.record_observation("first", {"tool": plan["tool"], "arguments": plan["arguments"]}, scoped())
    record.plan_test(plan)
    execute(record, plan, scoped())
    report = record.review_dossier(dossier())
    assert report["checks"][0]["prior_matching_observation"] == ["first"]
    assert report["claims"][0]["evidence_status"] == "unassessed"


def test_pending_replication_plans_can_share_rows_but_are_not_independent_samples():
    record = ledger()
    first, second = test_plan("first", "replication"), test_plan("second", "replication")
    record.plan_test(first)
    record.plan_test(second)
    execute(record, first, scoped(partition="replication"))
    execute(record, second, scoped(partition="replication"), "experiment-0002")
    report = record.review_dossier(dossier(tests=["first", "second"], replications=["first", "second"]))
    assert all(check["prospective"] for check in report["checks"])
    assert report["checks"][1]["reused_source_observations"] == ["experiment-0001"]
    assert report["prospective_checks"]["checks_reusing_observed_rows"] == 1
    assert report["prospective_checks"]["independent_sample_count"] is None


@pytest.mark.parametrize("change", [{"rows": ["new-row"]}, {"columns": ["new-response"]}, {"partition": "replication"}])
def test_nonoverlapping_declared_sources_are_not_falsely_marked_preobserved(change):
    record = ledger()
    record.record_observation("raw", {"tool": "read", "arguments": {}}, scoped())
    plan = test_plan()
    record.plan_test(plan)
    execute(record, plan, scoped(**change))
    report = record.review_dossier(dossier())
    assert report["checks"][0]["preobserved_source"] == []
    assert report["claims"][0]["evidence_status"] == "evidence-supported"


def test_descriptive_counterevidence_still_requires_disclosure():
    record = ledger()
    record.record_observation("raw", {"tool": "read", "arguments": {}}, scoped(values=[0]))
    plan = test_plan()
    record.plan_test(plan)
    execute(record, plan, scoped(values=[0]))
    report = record.review_dossier(dossier(support=[]))
    assert report["claims"][0]["evidence_status"] == "unassessed"
    assert report["claims"][0]["omitted_counterevidence"] == ["experiment-0001"]


@pytest.mark.parametrize("identifier", ["analysis-0001", "made-up", "experiment-9999"])
def test_fabricated_or_selfreported_citations_are_rejected(identifier):
    with pytest.raises(ValueError, match="non-native"):
        ledger().review_dossier(dossier(support=[identifier]))


def test_binding_and_single_execution_are_enforced_before_native_call():
    record = ledger()
    plan = test_plan()
    record.plan_test(plan)
    with pytest.raises(ValueError, match="differs"):
        record.validate_experiment({"tool": "measure", "arguments": {"sample": "other"}, "test_id": plan["id"]})
    execute(record, plan)
    with pytest.raises(ValueError, match="already"):
        execute(record, plan, evidence_id="experiment-0002")
    with pytest.raises(ValueError, match="unknown"):
        record.validate_experiment({"tool": "measure", "arguments": {}, "test_id": "unknown"})


def test_broad_overlapping_predictions_do_not_earn_discriminating_support():
    record = ledger()
    plan = test_plan(intervals=[[-1e6, 1e6], [-1e6, 1e6]])
    record.plan_test(plan)
    execute(record, plan)
    report = record.review_dossier(dossier())
    assert report["claims"][0]["evidence_status"] == "inconclusive"
    assert report["prospective_checks"]["discriminating_checks"]["value"] == 0
    assert report["process"]["support_citation_verification"]["value"] == 0


def test_broad_hypothesis_does_not_borrow_other_hypotheses_discrimination():
    record = ledger()
    record.append_hypothesis(hypothesis("third"))
    plan = test_plan(intervals=[[-1e6, 1e6], [-0.5, 0.5]])
    plan["predictions"].append({"hypothesis_id": "third", "interval": [1, 2], "falsifiers": []})
    record.plan_test(plan)
    execute(record, plan)
    report = record.review_dossier(dossier())
    assert report["claims"][0]["evidence_status"] == "inconclusive"
    assert report["claims"][0]["supporting_evidence"] == []


def test_uncited_contradictory_measurements_cannot_be_cherry_picked_away():
    record = ledger()
    first = test_plan()
    second = test_plan("test-2")
    record.plan_test(first)
    record.plan_test(second)
    execute(record, first)
    execute(record, second, {"values": [0.0]}, "experiment-0002")
    report = record.review_dossier(dossier(tests=["test-1"]))
    claim = report["claims"][0]
    assert claim["evidence_status"] == "inconclusive"
    assert claim["completed_checks"] == 2
    assert claim["omitted_counterevidence"] == ["experiment-0002"]
    assert report["process"]["counterevidence_disclosure"]["value"] == 0


def test_negative_findings_and_explicit_falsifiers_are_first_class():
    record = ledger()
    plan = test_plan()
    plan["predictions"][0]["falsifiers"] = [[-0.5, 0.5]]
    record.plan_test(plan)
    execute(record, plan, {"values": [0.0]})
    report = record.review_dossier(dossier(conclusion="rejected", support=[], counter=["experiment-0001"]))
    assert report["claims"][0]["evidence_status"] == "rejected"
    assert report["claims"][0]["conclusion_matches_operational_checks"]
    assert report["checks"][0]["hypotheses"][0]["explicit_falsifier_observed"]
    assert report["process"]["counterevidence_disclosure"]["value"] == 1


def test_replication_can_be_referenced_before_its_native_evidence_exists():
    record = ledger()
    plan = test_plan("replicate", "replication")
    record.plan_test(plan)
    frozen = dossier(support=[], tests=["replicate"], replications=["replicate"])
    record.validate_dossier(frozen)
    with pytest.raises(ValueError, match="no native observation"):
        record.validate_dossier(frozen, allow_pending=False)
    before = record.review_dossier(frozen)
    assert before["claims"][0]["evidence_status"] == "unassessed"
    execute(record, plan, {"values": [0.0]})
    record.validate_dossier(frozen, allow_pending=False)
    after = record.review_dossier(frozen)
    assert after["claims"][0]["evidence_status"] == "rejected"
    assert after["claims"][0]["omitted_counterevidence"] == []
    assert after["process"]["declared_replication_completion"]["value"] == 1


def test_pending_exploration_cannot_be_promoted_to_replication():
    record = ledger()
    record.plan_test(test_plan())
    with pytest.raises(ValueError, match="replication plans"):
        record.validate_dossier(dossier(support=[], tests=["test-1"], replications=["test-1"]))
    with pytest.raises(ValueError, match="pending claim"):
        record.validate_dossier(dossier(support=[], tests=["test-1"]))


def test_revisions_are_immutable_and_do_not_erase_failed_ancestors():
    record = ledger()
    plan = test_plan()
    record.plan_test(plan)
    execute(record, plan, {"values": [0.0]})
    revised = hypothesis("revised")
    revised.update(revises="effect", revision_reason="The first prediction was contradicted.")
    record.revise_hypothesis(revised)
    report = record.review_dossier(dossier("revised", "inconclusive", support=[]))
    assert report["claims"][0]["evidence_status"] == "unassessed"
    assert report["claims"][0]["revision_ancestors"] == ["effect"]
    assert report["claims"][0]["revision_ancestor_checks"][0]["compatible"] is False
    assert report["checks"][0]["hypotheses"][0]["compatible"] is False
    with pytest.raises(ValueError, match="immutable"):
        record.append_hypothesis(hypothesis())


def test_limited_measurement_coverage_is_visible_not_counted_as_scientific_failure():
    record = ledger()
    first, second = test_plan(), test_plan("test-2")
    record.plan_test(first)
    record.plan_test(second)
    execute(record, first, {"values": []})
    report = record.review_dossier(dossier())
    assert report["claims"][0]["evidence_status"] == "unassessed"
    assert report["checks"][0]["reason"] == "measurement_unavailable"
    assert report["process"]["registered_test_completion"]["value"] == 0.5
    assert report["process"]["claim_test_coverage"]["value"] == 0
    assert report["prospective_checks"]["measurement_availability"]["value"] == 0


@pytest.mark.parametrize("measurement", [
    {"path": ["x"], "reducer": "eval"},
    {"path": ["x"], "reducer": "scalar", "code": "open('/etc/passwd').read()"},
    {"path": [True], "reducer": "scalar"},
    {"path": [-1], "reducer": "scalar"},
    {"path": ["x"] * 17, "reducer": "scalar"},
])
def test_measurement_language_is_bounded_and_contains_no_code(measurement):
    record = ledger()
    plan = test_plan()
    plan["measurement"] = measurement
    with pytest.raises(ValueError):
        record.plan_test(plan)


@pytest.mark.parametrize("value", [True, "1.5", None, {}, [False], [1, "2"]])
def test_non_numeric_measurements_are_unassessed(value):
    record = ledger()
    plan = test_plan()
    record.plan_test(plan)
    execute(record, plan, {"values": value})
    assert record.review_dossier(dossier())["claims"][0]["evidence_status"] == "unassessed"


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
def test_nonfinite_payloads_are_rejected(value):
    record = ledger()
    with pytest.raises(ValueError, match="finite JSON"):
        record.record_observation("bad", {"tool": "measure", "arguments": {}}, {"value": value})


def test_overlapping_falsifier_and_prediction_is_an_invalid_contract():
    record = ledger()
    plan = test_plan()
    plan["predictions"][0]["falsifiers"] = [[1, 1.5]]
    with pytest.raises(ValueError, match="overlaps"):
        record.plan_test(plan)


def test_return_values_and_input_mutation_cannot_change_the_record():
    record = ledger()
    plan = test_plan()
    result = record.plan_test(plan)
    plan["arguments"]["sample"] = "tampered"
    result["arguments"]["sample"] = "tampered"
    original = record.get_test("test-1")
    assert original["arguments"]["sample"] == "test-1"
    observation = {"values": [1.5]}
    execute(record, original, observation)
    observation["values"][0] = 0
    snapshot = record.snapshot()
    snapshot["events"].clear()
    assert record.review_dossier(dossier())["claims"][0]["evidence_status"] == "evidence-supported"
    assert record.snapshot()["events"]


def test_review_is_pure_and_does_not_consume_or_mutate_dossier():
    record = ledger()
    plan = test_plan()
    record.plan_test(plan)
    execute(record, plan)
    candidate = dossier()
    initial = copy.deepcopy(candidate)
    first = record.review_dossier(candidate)
    second = record.review_dossier(candidate)
    assert first == second
    assert candidate == initial


@pytest.mark.parametrize("reducer,values,expected", [("mean", [1, 2], 1.5), ("sum", [0.5, 1], 1.5),
                                                    ("min", [1.5, 2], 1.5), ("max", [1, 1.5], 1.5)])
def test_declared_reducers_extract_native_numeric_data(reducer, values, expected):
    record = ledger()
    plan = test_plan()
    plan["measurement"]["reducer"] = reducer
    record.plan_test(plan)
    execute(record, plan, {"values": values})
    assert record.review_dossier(dossier())["checks"][0]["value"] == expected


def test_indexed_scalar_measurement_and_overflow_are_explicit():
    record = ledger()
    plan = test_plan()
    plan["measurement"] = {"path": ["rows", 0, "result"], "reducer": "scalar"}
    record.plan_test(plan)
    execute(record, plan, {"rows": [{"result": 1.5}]})
    assert record.review_dossier(dossier())["checks"][0]["value"] == 1.5
    second = test_plan("test-2")
    second["measurement"]["reducer"] = "sum"
    record.plan_test(second)
    execute(record, second, {"values": [1e308, 1e308]}, "experiment-0002")
    assert record.review_dossier(dossier())["checks"][1]["status"] == "unassessed"
