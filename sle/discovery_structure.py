"""Pure, bounded operational review of explicitly decomposed discovery claims.

Inputs are registered hypothesis/test payloads and trusted ``DiscoveryLedger``
checks, not candidate-supplied observations. These functions authenticate neither
their inputs nor a scientific claim's faithful operationalization. A compatible
numeric interval is not scientific truth, causal identification or independent
replication. All reports require semantic review and contain no science score.

Structures are flat: a component names a registered hypothesis and its tests;
it never evaluates another structure. All listed tests of a component are
necessary operational checks. ``all_of`` requires every component; ``any_of``
requires one component but still exposes missing and incompatible components.
Background incompatibility remains visible, but only prospective numeric checks
can yield prospective compatibility. No old ledger or report is mutated.
"""
from __future__ import annotations

import json
import math
from collections import Counter


MAX_ITEMS = 1024
MAX_COMPONENTS = 1024
MAX_REFERENCES = 8192
MAX_PAIRS = 16384
MAX_JSON_BYTES = 32 * 1024 * 1024


def _copy_json(value, maximum=MAX_JSON_BYTES):
    nodes = 0

    def visit(item, depth):
        nonlocal nodes
        nodes += 1
        if depth > 32 or nodes > 250000:
            raise ValueError("JSON structure limit exceeded")
        if item is None or type(item) in (str, bool, int):
            return
        if type(item) is float:
            if not math.isfinite(item):
                raise ValueError("JSON numbers must be finite")
        elif type(item) is list:
            for child in item:
                visit(child, depth + 1)
        elif type(item) is dict:
            if any(type(key) is not str for key in item):
                raise ValueError("JSON object keys must be strings")
            for child in item.values():
                visit(child, depth + 1)
        else:
            raise ValueError("inputs must be strict JSON values")

    visit(value, 0)
    try:
        encoded = json.dumps(value, allow_nan=False, ensure_ascii=False)
        if len(encoded.encode("utf-8")) > maximum:
            raise ValueError("JSON byte limit exceeded")
        return json.loads(encoded)
    except (UnicodeError, OverflowError, RecursionError) as exc:
        raise ValueError("invalid or oversized JSON input") from exc


def _list(value, name, maximum=MAX_ITEMS):
    if not isinstance(value, list) or len(value) > maximum:
        raise ValueError(name + " must be a bounded list")
    return value


def _text(value, name, maximum=16384):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValueError(name + " must be a nonempty bounded string")
    return value


def _id(value):
    _text(value, "identifier", 128)
    if any(ord(char) < 32 for char in value):
        raise ValueError("identifier contains a control character")
    return value


def _ids(value, name):
    result = [_id(item) for item in _list(value, name)]
    if len(result) != len(set(result)):
        raise ValueError(name + " contains duplicates")
    return result


def _number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("measurement must be numeric")
    try:
        if math.isfinite(value):
            return float(value)
    except (OverflowError, ValueError):
        pass
    raise ValueError("measurement must be finite")


def _interval(value):
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError("interval needs two endpoints")
    result = [_number(item) for item in value]
    if result[0] > result[1]:
        raise ValueError("interval endpoints are reversed")
    return result


def _disjoint(left, right):
    return left[1] < right[0] or right[1] < left[0]


def _index_hypotheses(hypotheses):
    result = {}
    for hypothesis in _list(hypotheses, "hypotheses"):
        if not isinstance(hypothesis, dict):
            raise ValueError("hypothesis must be an object")
        identifier = _id(hypothesis.get("id"))
        _text(hypothesis.get("statement"), "hypothesis statement")
        if identifier in result:
            raise ValueError("duplicate hypothesis identifier")
        result[identifier] = hypothesis
    return result


def _index_tests(tests, hypotheses=None):
    result = {}
    for test in _list(tests, "tests"):
        if not isinstance(test, dict):
            raise ValueError("test must be an object")
        identifier = _id(test.get("id"))
        if identifier in result:
            raise ValueError("duplicate test identifier")
        if test.get("phase") not in ("exploration", "replication"):
            raise ValueError("invalid test phase")
        predictions = _list(test.get("predictions"), "predictions", 64)
        if len(predictions) < 2:
            raise ValueError("test needs competing predictions")
        seen = set()
        for prediction in predictions:
            if not isinstance(prediction, dict):
                raise ValueError("prediction must be an object")
            hypothesis_id = _id(prediction.get("hypothesis_id"))
            if hypothesis_id in seen or (hypotheses is not None and hypothesis_id not in hypotheses):
                raise ValueError("predictions need distinct registered hypotheses")
            seen.add(hypothesis_id)
            prediction["interval"] = _interval(prediction.get("interval"))
            prediction["falsifiers"] = [_interval(item) for item in
                                        _list(prediction.get("falsifiers"), "falsifiers", 32)]
            if any(not _disjoint(prediction["interval"], item) for item in prediction["falsifiers"]):
                raise ValueError("falsifier overlaps its prediction")
        result[identifier] = test
    return result


def _validate_structures(structures, hypotheses, tests):
    seen, total_components, total_references = set(), 0, 0
    for structure in _list(structures, "structures"):
        if not isinstance(structure, dict) or set(structure) != {"hypothesis_id", "operator", "components"}:
            raise ValueError("invalid structure fields")
        identifier = _id(structure["hypothesis_id"])
        if identifier not in hypotheses or identifier in seen:
            raise ValueError("structures need distinct registered hypotheses")
        seen.add(identifier)
        if structure["operator"] not in ("all_of", "any_of"):
            raise ValueError("invalid structure operator")
        components = _list(structure["components"], "components", 64)
        if not components:
            raise ValueError("structure needs at least one component")
        total_components += len(components)
        component_ids = set()
        for component in components:
            if not isinstance(component, dict) or set(component) != {"id", "statement", "hypothesis_id", "test_ids"}:
                raise ValueError("invalid component fields; nested structures are not supported")
            component_id = _id(component["id"])
            if component_id in component_ids:
                raise ValueError("duplicate component identifier")
            component_ids.add(component_id)
            _text(component["statement"], "component statement")
            hypothesis_id = _id(component["hypothesis_id"])
            if hypothesis_id not in hypotheses:
                raise ValueError("component references unknown hypothesis")
            test_ids = _ids(component["test_ids"], "component test_ids")
            total_references += len(test_ids)
            for test_id in test_ids:
                if test_id not in tests:
                    raise ValueError("component references unknown test")
                if hypothesis_id not in {item["hypothesis_id"] for item in tests[test_id]["predictions"]}:
                    raise ValueError("component test does not predict its hypothesis")
        if total_components > MAX_COMPONENTS or total_references > MAX_REFERENCES:
            raise ValueError("component or test reference limit exceeded")
    return structures


def validate_structures(structures, hypotheses, tests):
    """Return a detached validated flat structure list, without observing data."""
    structures = _copy_json(structures, 2 * 1024 * 1024)
    registered = _index_hypotheses(_copy_json(hypotheses))
    plans = _index_tests(_copy_json(tests), registered)
    return _validate_structures(structures, registered, plans)


def _index_checks(checks, tests):
    result, evidence_ids = {}, set()
    for check in _list(checks, "checks"):
        if not isinstance(check, dict):
            raise ValueError("check must be an object")
        test_id, evidence_id = _id(check.get("test_id")), _id(check.get("evidence_id"))
        if test_id not in tests or test_id in result or evidence_id in evidence_ids:
            raise ValueError("checks need unique registered tests and evidence")
        evidence_ids.add(evidence_id)
        if check.get("phase") != tests[test_id]["phase"]:
            raise ValueError("check phase differs from registered test")
        if type(check.get("prospective")) is not bool or type(check.get("preregistered")) is not bool:
            raise ValueError("check timing fields must be boolean")
        for field in ("preobserved_source", "prior_matching_observation", "reused_source_observations"):
            _ids(check.get(field), field)
        if check["prospective"] and (not check["preregistered"] or check["preobserved_source"] or check["prior_matching_observation"]):
            raise ValueError("inconsistent prospective check")
        if check.get("status") not in ("assessed", "unassessed"):
            raise ValueError("invalid check status")
        outcomes = _list(check.get("hypotheses"), "check hypotheses", 64)
        if check["status"] == "unassessed":
            if check.get("value") is not None or outcomes:
                raise ValueError("unassessed check cannot contain measured predictions")
        else:
            value = _number(check.get("value"))
            predictions = {item["hypothesis_id"]: item for item in tests[test_id]["predictions"]}
            seen = set()
            for outcome in outcomes:
                if not isinstance(outcome, dict):
                    raise ValueError("check hypothesis must be an object")
                hypothesis_id = _id(outcome.get("hypothesis_id"))
                if hypothesis_id not in predictions or hypothesis_id in seen:
                    raise ValueError("check predictions differ from registered test")
                seen.add(hypothesis_id)
                interval = predictions[hypothesis_id]["interval"]
                if type(outcome.get("compatible")) is not bool or outcome["compatible"] != (interval[0] <= value <= interval[1]):
                    raise ValueError("check compatibility differs from numeric prediction")
            if seen != set(predictions):
                raise ValueError("check omits a registered prediction")
        result[test_id] = check
    return result


def _combine(states, operator):
    if operator == "all_of":
        if "incompatible" in states:
            return "incompatible"
        return "compatible" if states and all(item == "compatible" for item in states) else "undetermined"
    if "compatible" in states:
        return "compatible"
    return "incompatible" if states and all(item == "incompatible" for item in states) else "undetermined"


def _component_report(component, tests, checks, hypothesis_test_ids):
    outcomes, states, prospective_states = [], [], []
    for test_id in component["test_ids"]:
        check = checks.get(test_id)
        outcome = {"test_id": test_id, "status": "missing", "evidence_id": None,
                   "evidence_role": None, "operational_compatibility": "undetermined",
                   "prospective": False, "explicit_falsifier_observed": None,
                   "reused_source_observations": [], "source_independence": "unassessed"}
        if check is not None:
            outcome.update({"status": check["status"], "evidence_id": check["evidence_id"],
                            "prospective": check["prospective"],
                            "evidence_role": "prospective_prediction_check" if check["prospective"] else "background_observation",
                            "reused_source_observations": check["reused_source_observations"],
                            "source_independence": "not_independent" if check["reused_source_observations"] else "unassessed"})
            if check["status"] == "assessed":
                prediction = next(item for item in tests[test_id]["predictions"]
                                  if item["hypothesis_id"] == component["hypothesis_id"])
                value = check["value"]
                compatible = prediction["interval"][0] <= value <= prediction["interval"][1]
                outcome.update({"value": value, "prediction_interval": prediction["interval"],
                                "operational_compatibility": "compatible" if compatible else "incompatible",
                                "explicit_falsifier_observed": any(item[0] <= value <= item[1] for item in prediction["falsifiers"])})
        outcomes.append(outcome)
        states.append(outcome["operational_compatibility"])
        prospective_states.append(outcome["operational_compatibility"] if outcome["prospective"] else "undetermined")
    selected = set(component["test_ids"])
    unlinked = [identifier for identifier in hypothesis_test_ids.get(component["hypothesis_id"], [])
                if identifier not in selected]
    # An omitted test of the same hypothesis cannot be silently excluded when
    # labelling the component prospectively compatible. It still requires a
    # semantic reviewer to decide whether the declared mappings are faithful.
    if unlinked:
        prospective_states.append("undetermined")
    return {**component, "operational_compatibility": _combine(states, "all_of"),
            "prospective_compatibility": _combine(prospective_states, "all_of"),
            "checks": outcomes, "missing_test_ids": [item["test_id"] for item in outcomes if item["status"] == "missing"],
            "unassessed_test_ids": [item["test_id"] for item in outcomes if item["status"] == "unassessed"],
            "unlinked_registered_test_ids": unlinked, "test_coverage_complete": bool(component["test_ids"]) and not unlinked,
            "has_registered_tests": bool(component["test_ids"]),
            "requires_semantic_review": True}


def review_structures(structures, hypotheses, tests, checks):
    """Review necessary conditions; never infer science quality from agreement.

    Every registered hypothesis receives a report, including those without a
    declared structure. Unlinked tests are exposed for completeness review, not
    silently treated as tests of a candidate's stated component. Distinct tests
    or evidence IDs never establish independent sources.
    """
    hypotheses = _index_hypotheses(_copy_json(hypotheses))
    tests = _index_tests(_copy_json(tests), hypotheses)
    structures = _validate_structures(_copy_json(structures, 2 * 1024 * 1024), hypotheses, tests)
    checks = _index_checks(_copy_json(checks), tests)
    structures_by_id = {item["hypothesis_id"]: item for item in structures}
    hypothesis_test_ids = {}
    for test_id, test in tests.items():
        for prediction in test["predictions"]:
            hypothesis_test_ids.setdefault(prediction["hypothesis_id"], []).append(test_id)
    claims = []
    for hypothesis_id in hypotheses:
        structure = structures_by_id.get(hypothesis_id)
        components = [_component_report(item, tests, checks, hypothesis_test_ids) for item in structure["components"]] if structure else []
        evidence = [check["evidence_id"] for component in components for check in component["checks"] if check["evidence_id"] is not None]
        reused = sorted({item for component in components for check in component["checks"] for item in check["reused_source_observations"]})
        shared = sorted(item for item, count in Counter(evidence).items() if count > 1)
        operator = structure["operator"] if structure else None
        claims.append({"hypothesis_id": hypothesis_id, "structure_registered": structure is not None,
                       "operator": operator, "components": components,
                       "operational_compatibility": _combine([item["operational_compatibility"] for item in components], operator) if structure else "undetermined",
                       "prospective_compatibility": _combine([item["prospective_compatibility"] for item in components], operator) if structure else "undetermined",
                       "missing_component_ids": [item["id"] for item in components if not item["has_registered_tests"] or item["missing_test_ids"]],
                       "undetermined_component_ids": [item["id"] for item in components if item["operational_compatibility"] == "undetermined"],
                       "incompatible_component_ids": [item["id"] for item in components if item["operational_compatibility"] == "incompatible"],
                       "unique_evidence_ids": sorted(set(evidence)), "shared_evidence_ids": shared,
                       "reused_source_observations": reused,
                       "source_independence": "not_independent" if shared or reused else "unassessed",
                       "requires_semantic_review": True,
                       "review_reasons": ["claim_structure_and_operationalization_unassessed", "uncertainty_and_scope_unassessed"] if structure else ["missing_structure"]})
    return _copy_json({"schema_version": 1, "evaluation_basis": "declared_flat_structure_and_operational_predictions",
                       "ground_truth_used": False, "claims": claims, "requires_semantic_review": True,
                       "source_independence": "unassessed"})


def pairwise_predictions(tests):
    """Return every within-test pair, not an 'any alternative separated' ratio.

    Closed intervals sharing an endpoint overlap. Disjoint prediction intervals
    alone do not establish empirical or scientific identifiability.
    """
    tests = _index_tests(_copy_json(tests))
    pair_count = sum(len(test["predictions"]) * (len(test["predictions"]) - 1) // 2 for test in tests.values())
    if pair_count > MAX_PAIRS:
        raise ValueError("pairwise prediction limit exceeded")
    reports = []
    for test_id, test in tests.items():
        pairs = []
        for index, left in enumerate(test["predictions"]):
            for right in test["predictions"][index + 1:]:
                relation = "identical" if left["interval"] == right["interval"] else "disjoint" if _disjoint(left["interval"], right["interval"]) else "overlap"
                pairs.append({"left_hypothesis_id": left["hypothesis_id"], "right_hypothesis_id": right["hypothesis_id"],
                              "left_interval": left["interval"], "right_interval": right["interval"], "relation": relation})
        reports.append({"test_id": test_id, "pairs": pairs, "requires_semantic_review": True})
    return _copy_json(reports)
