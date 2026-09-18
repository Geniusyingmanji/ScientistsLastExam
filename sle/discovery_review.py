"""Bounded review of a discovery record without a scientific ground truth.

``DiscoveryLedger`` is owned by the trusted episode runtime. Agents may propose
hypotheses and tests; only the runtime calls ``record_observation`` after a
successful native experiment. Analysis output and prose are never observations.
An evidence identifier or hash is not an authentication mechanism outside that
runtime. The ledger never imports an environment, executes candidate code,
consults hidden labels, or calls a judge model.

Hypothesis payload::

    {"id": "h1", "statement": "...", "rationale": "...",
     "assumptions": ["..."], "alternatives": ["..."]}

A revision has those fields plus ``revises`` and ``revision_reason`` and a new
ID. Old entries and their failed predictions remain in the record. A test::

    {"id": "t1", "phase": "exploration", "tool": "measure",
     "arguments": {"sample": "a"}, "rationale": "...",
     "measurement": {"path": ["values"], "reducer": "mean"},
     "predictions": [
       {"hypothesis_id": "h1", "interval": [1, 2], "falsifiers": [[-2, 0]]},
       {"hypothesis_id": "h2", "interval": [-2, 0], "falsifiers": [[1, 2]]}]}

Test phases are ``exploration`` or ``replication``. The episode runtime enforces
the immutable commit boundary and phase access. A registered test is used once,
only by an action explicitly naming its ``test_id``, with exactly its tool and
arguments. Matching exploratory observations do not receive retroactive credit.
Measurements use a bounded JSON path and a numeric reducer, never an expression.

A frozen dossier::

    {"claims": [{"hypothesis_id": "h1", "conclusion": "supported",
                 "support": ["experiment-0001"], "counterevidence": [],
                 "tests": ["t1", "t2"], "limitations": ["..."]}],
     "replication_tests": ["t2"], "limitations": ["..."]}

``validate_dossier`` supports validation before commit, including pending
replication plans. ``review_dossier`` is pure and can run after native replication
observations have been appended. ``snapshot`` and all returned objects are
detached. Review checks *every* completed registered test of a claimed hypothesis,
not merely the cited subset. Its statuses describe compatibility of operational
predictions with measurements, not truth, causality, novelty, or discovery quality.
Prediction uncertainty, measurement validity, and the plausibility of alternatives
still require scientific review. No combined discovery score is produced.
"""
from __future__ import annotations

import hashlib
import json
import math


MAX_ITEMS = 1024
MAX_JSON_BYTES = 2 * 1024 * 1024
MAX_LEDGER_BYTES = 32 * 1024 * 1024
REDUCERS = {"scalar", "mean", "sum", "min", "max"}
SEMANTIC_REVIEW_AXES = (
    ("scientific_question", "Is the question scientifically relevant and is its scope clear?",
     ["public_scientific_question", "hypothesis_ids", "domain_literature"]),
    ("hypothesis_operationalization", "Do the measurements and registered predictions actually test the stated hypotheses and assumptions?",
     ["hypothesis_ids", "test_ids", "measurement_definitions", "assumption_checks"]),
    ("competing_explanations", "Are the alternatives substantive, plausible explanations rather than convenient weak comparisons?",
     ["hypothesis_ids", "test_ids", "domain_literature"]),
    ("experimental_rationale", "Does the prospective design distinguish the alternatives while addressing confounding, calibration, and selection?",
     ["test_ids", "native_evidence_ids", "control_and_calibration_records"]),
    ("inference_warrant", "Is the inference supported by the cited observations, with contradictory results addressed and causal claims justified?",
     ["claim_hypothesis_ids", "native_evidence_ids", "test_ids", "revision_lineage", "causal_identification_argument_if_applicable"]),
    ("uncertainty_and_selection", "Are uncertainty, adaptive selection, repeated testing, and measurement error accounted for without overstating precision?",
     ["test_ids", "native_evidence_ids", "sampling_design", "uncertainty_and_multiple_testing_method"]),
    ("reproducibility", "Can an independent investigator reproduce the analysis, and are replication data sufficiently independent?",
     ["test_ids", "native_evidence_ids", "data_and_runtime_bindings", "analysis_artifacts", "replication_provenance"]),
    ("novelty_and_scope", "What is new relative to prior work, and what conditions limit the result or its generalization?",
     ["claim_hypothesis_ids", "domain_literature", "limitations", "external_validation_if_claimed"]),
)


def _copy(value):
    try:
        encoded = json.dumps(value, allow_nan=False, sort_keys=True,
                             separators=(",", ":"))
    except (TypeError, ValueError, RecursionError) as exc:
        raise ValueError("payload must be finite JSON") from exc
    if len(encoded.encode("utf-8")) > MAX_JSON_BYTES:
        raise ValueError("discovery payload exceeds size limit")
    return json.loads(encoded)


def _digest(value):
    return hashlib.sha256(json.dumps(value, allow_nan=False, sort_keys=True,
                                    separators=(",", ":")).encode("utf-8")).hexdigest()


def _keys(value, required, optional=()):
    if not isinstance(value, dict) or not set(required) <= set(value) or set(value) - set(required) - set(optional):
        raise ValueError("invalid discovery payload fields")


def _text(value, name, maximum=4096):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValueError(name + " must be a nonempty bounded string")
    return value


def _identifier(value):
    _text(value, "identifier", 128)
    if any(ord(character) < 32 for character in value):
        raise ValueError("identifier contains a control character")
    return value


def _strings(value, name, *, maximum=64):
    if not isinstance(value, list) or len(value) > maximum:
        raise ValueError(name + " must be a bounded list")
    return [_text(item, name) for item in value]


def _ids(value, name):
    if not isinstance(value, list) or len(value) > MAX_ITEMS:
        raise ValueError(name + " must be a bounded list")
    result = [_identifier(item) for item in value]
    if len(set(result)) != len(result):
        raise ValueError(name + " contains duplicates")
    return result


def _number(value):
    if isinstance(value, bool) or not isinstance(value, (float, int)):
        raise ValueError("measurement must be numeric")
    try:
        finite = math.isfinite(value)
    except (OverflowError, ValueError):
        finite = False
    if not finite:
        raise ValueError("measurement must be finite")
    return float(value)


def _interval(value):
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError("interval must contain two finite endpoints")
    result = [_number(item) for item in value]
    if result[0] > result[1]:
        raise ValueError("interval endpoints are reversed")
    return result


def _disjoint(left, right):
    return left[1] < right[0] or right[1] < left[0]


def _contains(interval, value):
    return interval[0] <= value <= interval[1]


def _ratio(numerator, denominator):
    return {"numerator": numerator, "denominator": denominator,
            "value": numerator / denominator if denominator else None}


def _evidence_scope(observation):
    """Read adapter-declared fixed-row provenance without inventing freshness."""
    if not isinstance(observation, dict):
        return None
    scope = observation.get("evidence_scope")
    if not isinstance(scope, dict) or scope.get("sampling") != "fixed_rows":
        return None
    if not all(isinstance(scope.get(field), str) and scope[field]
               for field in ("data_sha256", "partition")):
        return None
    columns, rows = scope.get("measured_columns"), scope.get("sample_ids")
    if (not isinstance(columns, list) or not isinstance(rows, list)
            or len(columns) > 100000 or len(rows) > 100000
            or any(not isinstance(column, str) for column in columns)
            or any(isinstance(row, bool) or not isinstance(row, (str, int)) for row in rows)):
        return None
    return scope


def _source_overlap(left, right):
    return bool(left and right
                and left["data_sha256"] == right["data_sha256"]
                and left["partition"] == right["partition"]
                and set(left["measured_columns"]) & set(right["measured_columns"])
                and set(left["sample_ids"]) & set(right["sample_ids"]))


def _extract(observation, measurement):
    value = observation
    for part in measurement["path"]:
        if isinstance(part, str):
            if not isinstance(value, dict) or part not in value:
                raise ValueError("measurement path is unavailable")
            value = value[part]
        else:
            if not isinstance(value, list) or part >= len(value):
                raise ValueError("measurement path is unavailable")
            value = value[part]
    reducer = measurement["reducer"]
    if reducer == "scalar":
        return _number(value)
    if not isinstance(value, list) or not value or len(value) > 100000:
        raise ValueError("reducer requires a bounded nonempty numeric list")
    values = [_number(item) for item in value]
    try:
        result = {"sum": lambda: math.fsum(values),
                  "mean": lambda: math.fsum(item / len(values) for item in values),
                  "min": lambda: min(values), "max": lambda: max(values)}[reducer]()
    except OverflowError as exc:
        raise ValueError("measurement reduction overflow") from exc
    return _number(result)


class DiscoveryLedger:
    """Append-only, in-memory runtime ledger; no hidden state is accepted."""

    def __init__(self, task_id):
        self.task_id = _identifier(task_id)
        self._hypotheses = {}
        self._tests = {}
        self._observations = {}
        self._events = []
        self._bytes = 0

    def _append(self, kind, payload):
        if len(self._events) >= MAX_ITEMS:
            raise ValueError("discovery ledger item limit reached")
        entry = {"seq": len(self._events), "kind": kind, "payload": _copy(payload),
                 "previous_sha256": self._events[-1]["sha256"] if self._events else None}
        entry["sha256"] = _digest(entry)
        size = len(json.dumps(entry).encode("utf-8"))
        if self._bytes + size > MAX_LEDGER_BYTES:
            raise ValueError("discovery ledger byte limit reached")
        self._events.append(entry)
        self._bytes += size
        return entry["seq"]

    def _hypothesis(self, payload, revision):
        payload = _copy(payload)
        required = {"id", "statement", "rationale", "assumptions", "alternatives"}
        if revision:
            required |= {"revises", "revision_reason"}
        _keys(payload, required)
        identifier = _identifier(payload["id"])
        if identifier in self._hypotheses:
            raise ValueError("hypothesis identifiers are immutable")
        for field in ("statement", "rationale"):
            _text(payload[field], field)
        for field in ("assumptions", "alternatives"):
            _strings(payload[field], field)
        if not payload["alternatives"]:
            raise ValueError("hypothesis must state at least one alternative")
        if revision:
            _identifier(payload["revises"])
            if payload["revises"] not in self._hypotheses:
                raise ValueError("revision refers to an unknown hypothesis")
            _text(payload["revision_reason"], "revision_reason")
        seq = self._append("hypothesis_revision" if revision else "hypothesis", payload)
        self._hypotheses[identifier] = {"seq": seq, **payload}
        return _copy(self._hypotheses[identifier])

    def append_hypothesis(self, payload):
        return self._hypothesis(payload, False)

    def revise_hypothesis(self, payload):
        return self._hypothesis(payload, True)

    def plan_test(self, payload):
        payload = _copy(payload)
        _keys(payload, {"id", "phase", "tool", "arguments", "rationale", "measurement", "predictions"})
        identifier = _identifier(payload["id"])
        if identifier in self._tests:
            raise ValueError("test identifiers are immutable")
        if not isinstance(payload["phase"], str) or payload["phase"] not in {"exploration", "replication"}:
            raise ValueError("unknown test phase")
        _text(payload["tool"], "tool", 128)
        _text(payload["rationale"], "rationale")
        if not isinstance(payload["arguments"], dict):
            raise ValueError("experiment arguments must be an object")
        measurement = payload["measurement"]
        _keys(measurement, {"path", "reducer"})
        path = measurement["path"]
        if not isinstance(path, list) or len(path) > 16:
            raise ValueError("measurement path is too long")
        for part in path:
            if isinstance(part, str):
                _text(part, "path component", 256)
            elif isinstance(part, bool) or not isinstance(part, int) or part < 0 or part > 100000:
                raise ValueError("invalid measurement path component")
        if not isinstance(measurement["reducer"], str) or measurement["reducer"] not in REDUCERS:
            raise ValueError("unknown measurement reducer")
        predictions = payload["predictions"]
        if not isinstance(predictions, list) or not 2 <= len(predictions) <= 64:
            raise ValueError("a test needs two or more competing predictions")
        seen = set()
        for prediction in predictions:
            _keys(prediction, {"hypothesis_id", "interval", "falsifiers"})
            hypothesis_id = _identifier(prediction["hypothesis_id"])
            if hypothesis_id not in self._hypotheses or hypothesis_id in seen:
                raise ValueError("predictions must refer to distinct known hypotheses")
            seen.add(hypothesis_id)
            prediction["interval"] = _interval(prediction["interval"])
            if not isinstance(prediction["falsifiers"], list) or len(prediction["falsifiers"]) > 32:
                raise ValueError("falsifiers must be a bounded list of intervals")
            prediction["falsifiers"] = [_interval(item) for item in prediction["falsifiers"]]
            if any(not _disjoint(prediction["interval"], interval) for interval in prediction["falsifiers"]):
                raise ValueError("falsifier overlaps its prediction")
        seq = self._append("test_plan", payload)
        self._tests[identifier] = {"seq": seq, **payload}
        return _copy(self._tests[identifier])

    def get_test(self, test_id):
        _identifier(test_id)
        if test_id not in self._tests:
            raise ValueError("unknown test identifier")
        return _copy(self._tests[test_id])

    def validate_experiment(self, action):
        """Validate exact binding before charging or executing a native tool."""
        action = _copy(action)
        _keys(action, {"tool", "arguments"}, {"action", "test_id"})
        if "action" in action and action["action"] != "experiment":
            raise ValueError("not an experiment action")
        _text(action["tool"], "tool", 128)
        if not isinstance(action["arguments"], dict):
            raise ValueError("experiment arguments must be an object")
        test_id = action.get("test_id")
        if test_id is not None:
            test = self.get_test(test_id)
            if any(item["test_id"] == test_id for item in self._observations.values()):
                raise ValueError("registered test has already been executed")
            if test["tool"] != action["tool"] or _digest(test["arguments"]) != _digest(action["arguments"]):
                raise ValueError("experiment differs from its registered plan")
        return {"tool": action["tool"], "arguments": action["arguments"], "test_id": test_id}

    def record_observation(self, evidence_id, action, observation):
        """Runtime-only: append a successful native observation, never analysis."""
        evidence_id = _identifier(evidence_id)
        if evidence_id in self._observations:
            raise ValueError("native evidence identifiers are immutable")
        action = self.validate_experiment(action)
        observation = _copy(observation)
        record = {"evidence_id": evidence_id, "action": action,
                  "test_id": action["test_id"], "observation": observation,
                  "observation_sha256": _digest(observation)}
        seq = self._append("native_observation", record)
        self._observations[evidence_id] = {"seq": seq, **record}
        return _copy(self._observations[evidence_id])

    def validate_dossier(self, dossier, allow_pending=True):
        dossier = _copy(dossier)
        _keys(dossier, {"claims", "replication_tests", "limitations"})
        _strings(dossier["limitations"], "limitations")
        replications = _ids(dossier["replication_tests"], "replication_tests")
        executed = {item["test_id"] for item in self._observations.values() if item["test_id"] is not None}
        for test_id in replications:
            test = self.get_test(test_id)
            if test["phase"] != "replication":
                raise ValueError("replication_tests must name replication plans")
            if not allow_pending and test_id not in executed:
                raise ValueError("replication plan has no native observation")
        claims = dossier["claims"]
        if not isinstance(claims, list) or len(claims) > 128:
            raise ValueError("claims must be a bounded list")
        seen = set()
        for claim in claims:
            _keys(claim, {"hypothesis_id", "conclusion", "support", "counterevidence", "limitations"}, {"tests"})
            hypothesis_id = _identifier(claim["hypothesis_id"])
            if hypothesis_id not in self._hypotheses or hypothesis_id in seen:
                raise ValueError("claims must reference distinct known hypotheses")
            seen.add(hypothesis_id)
            if not isinstance(claim["conclusion"], str) or claim["conclusion"] not in {"supported", "rejected", "inconclusive"}:
                raise ValueError("unknown claim conclusion")
            support = _ids(claim["support"], "support")
            counter = _ids(claim["counterevidence"], "counterevidence")
            if set(support) & set(counter):
                raise ValueError("evidence cannot be both support and counterevidence")
            if any(evidence not in self._observations for evidence in support + counter):
                raise ValueError("claim cites non-native or unknown evidence")
            _strings(claim["limitations"], "limitations")
            claim.setdefault("tests", [])
            for test_id in _ids(claim["tests"], "tests"):
                test = self.get_test(test_id)
                if hypothesis_id not in {item["hypothesis_id"] for item in test["predictions"]}:
                    raise ValueError("claim test does not test this hypothesis")
                if test_id not in executed and (not allow_pending or test_id not in replications):
                    raise ValueError("pending claim test must be a declared replication")
        return dossier

    def _checks(self):
        checks = []
        for evidence_id, observation in self._observations.items():
            test_id = observation["test_id"]
            if test_id is None:
                continue
            test = self._tests[test_id]
            scope = _evidence_scope(observation["observation"])
            earlier = [item for item in self._observations.values() if item["seq"] < observation["seq"]]
            reused = [item["evidence_id"] for item in earlier
                      if _source_overlap(scope, _evidence_scope(item["observation"]))]
            preobserved = [item["evidence_id"] for item in earlier if item["seq"] < test["seq"]
                           and _source_overlap(scope, _evidence_scope(item["observation"]))]
            prior_matching = [item["evidence_id"] for item in earlier
                              if item["seq"] < test["seq"] and scope is not None
                              and item["action"]["tool"] == test["tool"]
                              and _digest(item["action"]["arguments"]) == _digest(test["arguments"])
                              and (not _evidence_scope(item["observation"])
                                   or _evidence_scope(item["observation"])["data_sha256"] == scope["data_sha256"])]
            prospective = test["seq"] < observation["seq"] and not preobserved and not prior_matching
            check = {"test_id": test_id, "evidence_id": evidence_id, "phase": test["phase"],
                     "preregistered": test["seq"] < observation["seq"],
                     "prospective": prospective,
                     "prior_matching_observation": prior_matching,
                     "preobserved_source": preobserved,
                     "reused_source_observations": reused,
                     "source_freshness": ("preobserved" if preobserved or prior_matching else
                                          "not_previously_observed_in_ledger" if scope is not None else "unassessed"),
                     "source_independence": "unassessed",
                     "hypotheses": []}
            try:
                value = _extract(observation["observation"], test["measurement"])
            except ValueError:
                check.update({"status": "unassessed", "reason": "measurement_unavailable", "value": None})
                checks.append(check)
                continue
            check.update({"status": "assessed", "value": value})
            for prediction in test["predictions"]:
                compatible = _contains(prediction["interval"], value)
                distinguishable = [other["hypothesis_id"] for other in test["predictions"]
                                   if _disjoint(prediction["interval"], other["interval"])]
                check["hypotheses"].append({
                    "hypothesis_id": prediction["hypothesis_id"],
                    "compatible": compatible,
                    "prospective_contradiction": bool(prospective and not compatible),
                    "explicit_falsifier_observed": any(_contains(item, value) for item in prediction["falsifiers"]),
                    "distinguishable_alternatives": distinguishable,
                    "discriminating_support": bool(prospective and compatible and distinguishable),
                })
            checks.append(check)
        return checks

    def review_dossier(self, dossier):
        """Deterministic operational checks, with N=0 represented as null."""
        dossier = self.validate_dossier(dossier)
        checks = self._checks()
        claim_reports = []
        contradicted_citations = disclosed_citations = 0
        support_citations = verified_support_citations = 0
        for claim in dossier["claims"]:
            hypothesis_id = claim["hypothesis_id"]
            hypothesis_checks = []
            for check in checks:
                for hypothesis in check["hypotheses"]:
                    if hypothesis["hypothesis_id"] == hypothesis_id:
                        hypothesis_checks.append({**hypothesis, "test_id": check["test_id"],
                                                  "evidence_id": check["evidence_id"], "phase": check["phase"],
                                                  "prospective": check["prospective"]})
            supported = {item["evidence_id"] for item in hypothesis_checks if item["discriminating_support"]}
            contradicted = {item["evidence_id"] for item in hypothesis_checks if not item["compatible"]}
            prospective_contradicted = {item["evidence_id"] for item in hypothesis_checks if item["prospective_contradiction"]}
            compatible = {item["evidence_id"] for item in hypothesis_checks if item["compatible"]}
            if not any(item["prospective"] for item in hypothesis_checks):
                status = "unassessed"
            elif prospective_contradicted and supported:
                status = "inconclusive"
            elif prospective_contradicted:
                status = "rejected"
            elif supported:
                status = "evidence-supported"
            else:
                status = "inconclusive"
            # A replication mentioned before commit counts as disclosure even
            # though its evidence identifier cannot be known until execution.
            disclosed = set(claim["counterevidence"])
            disclosed |= {item["evidence_id"] for item in hypothesis_checks
                          if item["phase"] == "replication" and item["test_id"] in claim["tests"]}
            omitted = contradicted - disclosed
            unverified = set(claim["support"]) - supported
            misclassified_counter = set(claim["counterevidence"]) - contradicted
            contradicted_citations += len(contradicted)
            disclosed_citations += len(contradicted & disclosed)
            support_citations += len(claim["support"])
            verified_support_citations += len(set(claim["support"]) & supported)
            expected = {"supported": "evidence-supported", "rejected": "rejected", "inconclusive": "inconclusive"}[claim["conclusion"]]
            lineage = []
            current = self._hypotheses[hypothesis_id]
            while "revises" in current:
                lineage.append(current["revises"])
                current = self._hypotheses[current["revises"]]
            ancestor_checks = [{"hypothesis_id": item["hypothesis_id"],
                                "test_id": check["test_id"], "evidence_id": check["evidence_id"],
                                "compatible": item["compatible"]}
                               for check in checks for item in check["hypotheses"]
                               if item["hypothesis_id"] in lineage]
            claim_reports.append({
                "hypothesis_id": hypothesis_id, "declared_conclusion": claim["conclusion"],
                "evidence_status": status,
                "conclusion_matches_operational_checks": status == expected,
                "completed_checks": len(hypothesis_checks),
                "prospective_checks": sum(item["prospective"] for item in hypothesis_checks),
                "supporting_evidence": sorted(supported), "compatible_evidence": sorted(compatible),
                "contradicting_evidence": sorted(contradicted),
                "prospectively_contradicting_evidence": sorted(prospective_contradicted),
                "omitted_counterevidence": sorted(omitted),
                "unverified_support_citations": sorted(unverified),
                "misclassified_counterevidence_citations": sorted(misclassified_counter),
                "revision_ancestors": lineage,
                "revision_ancestor_checks": ancestor_checks,
                "limitations_disclosed": bool(claim["limitations"]),
            })
        assessed = [check for check in checks if check["status"] == "assessed"]
        prospective = [check for check in checks if check["prospective"]]
        prospectively_assessed = [check for check in assessed if check["prospective"]]
        executed_ids = {check["test_id"] for check in checks}
        claimed_ids = {claim["hypothesis_id"] for claim in dossier["claims"]}
        tested_ids = {item["hypothesis_id"] for check in prospectively_assessed for item in check["hypotheses"]}
        replication_checks = [check for check in prospectively_assessed if check["phase"] == "replication"]
        planned_discrimination = sum(
            any(_disjoint(left["interval"], right["interval"])
                for index, left in enumerate(test["predictions"])
                for right in test["predictions"][index + 1:])
            for test in self._tests.values())
        semantic_references = {"hypothesis_ids": sorted(self._hypotheses),
                               "claim_hypothesis_ids": sorted(claimed_ids),
                               "test_ids": sorted(self._tests),
                               "native_evidence_ids": sorted(self._observations)}
        result = {
            "schema_version": 1, "kind": "discovery_evidence_review", "task_id": self.task_id,
            "evaluation_basis": "native_observations_and_preregistered_predictions",
            "ground_truth_used": False, "judge_model_used": False, "discovery_score": None,
            "claims": claim_reports, "checks": checks,
            "process": {
                "hypotheses_registered": len(self._hypotheses), "tests_registered": len(self._tests),
                "native_observations": len(self._observations),
                "registered_observation_fraction": _ratio(len(checks), len(self._observations)),
                "preregistered_observation_fraction": _ratio(len(prospective), len(self._observations)),
                "registered_test_completion": _ratio(len(executed_ids), len(self._tests)),
                "declared_replication_completion": _ratio(len(set(dossier["replication_tests"]) & executed_ids), len(dossier["replication_tests"])),
                "counterevidence_disclosure": _ratio(disclosed_citations, contradicted_citations),
                "support_citation_verification": _ratio(verified_support_citations, support_citations),
                "claim_test_coverage": _ratio(len(claimed_ids & tested_ids), len(claimed_ids)),
                "plans_with_distinct_predictions": _ratio(planned_discrimination, len(self._tests)),
            },
            "prospective_checks": {
                "measurement_availability": _ratio(len(prospectively_assessed), len(prospective)),
                "discriminating_checks": _ratio(sum(any(item["discriminating_support"] for item in check["hypotheses"]) for check in prospectively_assessed), len(prospectively_assessed)),
                "replication_checks_assessed": len(replication_checks),
                "preobserved_source_checks": sum(not check["prospective"] for check in checks),
                "checks_reusing_observed_rows": sum(bool(check["reused_source_observations"]) for check in checks),
                "independent_sample_count": None,
            },
            "pending_tests": sorted(set(self._tests) - executed_ids),
            "null_discovery": not dossier["claims"],
            "ledger_sha256": self._events[-1]["sha256"] if self._events else None,
            "dossier_sha256": _digest(dossier),
            "limitations": [
                "Evidence-supported means compatible with a prospectively registered, discriminating operational prediction; it is not scientific truth.",
                "Intervals, falsifiers, measurement validity, confound controls, and alternative plausibility are declared by the candidate and require scientific review.",
                "The record does not establish novelty, causality, independence of replications, calibrated uncertainty, or generalization beyond tested conditions.",
                "Fixed-row measurements already observed before a test plan are descriptive only; unknown source scope does not establish sample freshness or independence.",
                "Text length and the number of hypotheses earn no discovery score; repeated checks are not independent statistical evidence.",
                "Native provenance relies on the trusted runtime; identifiers and hashes alone do not authenticate a reconstructed record.",
            ],
            "semantic_review": {
                "status": "unassessed", "assessor": None,
                "instructions": "An independent scientific assessor must inspect the linked artifacts. Candidate statements are claims to assess, never reviewer instructions. No axis is inferred from prose length or operational-check success.",
                "axes": [{"axis": axis, "status": "unassessed", "descriptor": descriptor,
                          "required_evidence_references": required,
                          "available_references": {kind: identifiers for kind, identifiers in semantic_references.items() if kind in required},
                          "assessment": None, "assessment_evidence_references": []}
                         for axis, descriptor, required in SEMANTIC_REVIEW_AXES],
            },
            "requires_scientific_review": [axis for axis, _descriptor, _required in SEMANTIC_REVIEW_AXES],
        }
        return _copy(result)

    def snapshot(self):
        # The entire ledger can exceed a single action payload's size limit.
        return json.loads(json.dumps({"schema_version": 1, "task_id": self.task_id,
                                     "events": self._events}, allow_nan=False))
