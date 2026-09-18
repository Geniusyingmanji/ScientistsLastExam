"""Discovery evidence must be real, ordered, sealed and separate from outcome credit."""
from __future__ import annotations

import hashlib
import importlib.util
import shutil
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest

from _sandbox_tools import skip_unless_sandbox
from sle.discovery_profiles import PILOTS, profile_for
from sle.discovery_trace import (
    DiscoveryRecorder, checked_science_metrics, digest, evidence_report, validate_evidence,
)
from sle.evaluate import evaluate_candidate
from sle.metric_visibility import search_visible_metrics
from sle.registry import find_task, list_tasks
from sle.rpc_codec import decode
from sle.secure_eval import CandidateError, trusted_evaluate

ROOT = Path(__file__).resolve().parents[1]
SCM = "CausalDiscovery/InterventionalSCM"


def load(path):
    spec = importlib.util.spec_from_file_location("discovery_test_" + str(hash(str(path))), path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def recorder(candidate, task=SCM, **kwargs):
    return DiscoveryRecorder(candidate, task, candidate_sha256="a" * 64,
                             oracle_sha256="b" * 64, **kwargs)


def sample_evidence(*, max_bytes=100000):
    observed = np.asarray([[1.0, 2.0]])

    def candidate(n, observe, intervene, budget):
        value = observe(1)
        value[0, 0] = 900
        return {"adjacency": np.zeros((2, 2)), "confidence": 0.2, "abstain": True}

    capture = recorder(candidate, max_bytes=max_bytes)
    capture(2, lambda n: observed, lambda *args: None, 1)
    evidence = capture.finish({"per_world": [{"split": "unsplit", "world_index": 0,
                                             "valid": True, "mechanism_score": 0.0}]})
    return evidence


def metrics_for(evidence):
    rows = []
    for instance in evidence["instances"]:
        outcome = instance["outcome"]
        rows.append({**{k: outcome[k] for k in ("split", "world_index", "valid")},
                     **{k: v for values in outcome["axes"].values() for k, v in values.items()}})
    return {"discovery_evidence": evidence, "per_world": rows}


def rehash(evidence):
    for instance in evidence["instances"]:
        previous = None
        for seq, event in enumerate(instance["events"]):
            event.update(seq=seq, previous_sha256=previous)
            event.pop("sha256", None)
            event["sha256"] = digest(event)
            previous = event["sha256"]
    evidence.pop("sha256", None)
    evidence["sha256"] = digest(evidence)


def test_profiles_cover_inventory_without_inventing_levels():
    discovery = [s for s in list_tasks(None) if s.metadata.get("scientific_role") == "discovery"]
    assert len(discovery) > len(PILOTS)
    assert set(PILOTS) <= {s.task_id for s in discovery}
    for spec in discovery:
        profile = profile_for(spec)
        if spec.task_id not in PILOTS:
            assert profile["openness"] is None
            assert profile["assessment_status"] == "not_assessed"
        assert profile["field_novelty"] == "not_established"
        assert profile["independent_scientific_review"] == "pending"


def test_observations_are_detached_from_candidate_mutation():
    evidence = sample_evidence()
    validate_evidence(evidence, expected_candidate_sha256="a" * 64)
    events = evidence["instances"][0]["events"]
    assert [e["kind"] for e in events] == ["input", "callback_request", "callback_result", "submission"]
    assert decode(events[2]["payload"]["value"])[0, 0] == 1.0
    report = evidence_report(metrics_for(evidence))
    assert report["rows"][0]["process"]["available_evidence_seq"] == [0, 2]
    assert report["rows"][0]["discovery_certification"] == "not_assessed"
    assert "reasoning" not in events[0]["payload"]["value"]


def test_task_changes_do_not_silently_inherit_inspected_labels(tmp_path):
    spec = find_task(SCM, include_uncertified=True)
    for rel in ("Task.md", "TASK_CARD.yaml", "verification/evaluator.py"):
        destination = tmp_path / rel
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(spec.task_dir / rel, destination)
    changed = replace(spec, task_dir=tmp_path)
    assert profile_for(changed)["assessment_status"] == "source_inspected"
    (tmp_path / "Task.md").write_text("Different scientific question")
    profile = profile_for(changed)
    assert profile["assessment_status"] == "source_changed"
    assert profile["openness"] is None and profile["claim_types"] == []


def test_outcomes_cannot_be_joined_to_different_result_rows():
    evidence = sample_evidence()
    metrics = metrics_for(evidence)
    metrics["per_world"][0]["mechanism_score"] = 1.0
    with pytest.raises(ValueError, match="differs from oracle"):
        evidence_report(metrics)


def test_exact_science_comparison_keeps_all_original_fields_and_checks_trace():
    metrics = metrics_for(sample_evidence())
    metrics.update(combined_score=0.25, valid=1.0, raw_score=0.25)
    science = checked_science_metrics(metrics, expected_candidate_sha256="a" * 64)
    assert science == {k: v for k, v in metrics.items() if k != "discovery_evidence"}
    with pytest.raises(ValueError, match="complete discovery evidence"):
        checked_science_metrics(science)
    with pytest.raises(ValueError, match="complete discovery evidence"):
        checked_science_metrics(metrics_for(sample_evidence(max_bytes=10)))
    with pytest.raises(ValueError, match="another candidate"):
        checked_science_metrics(metrics, expected_candidate_sha256="c" * 64)


def test_missing_outcome_rows_and_duplicate_worlds_are_rejected():
    evidence = sample_evidence()
    with pytest.raises(ValueError, match="matching oracle"):
        evidence_report({"discovery_evidence": evidence})
    import copy
    extra = copy.deepcopy(evidence["instances"][0])
    extra["instance_id"] = "instance-0001"
    evidence["instances"].append(extra)
    rehash(evidence)
    with pytest.raises(ValueError, match="duplicate outcome"):
        validate_evidence(evidence)


def test_tampered_payload_and_wrong_candidate_fail():
    evidence = sample_evidence()
    with pytest.raises(ValueError, match="another candidate"):
        validate_evidence(evidence, expected_candidate_sha256="c" * 64)
    evidence["instances"][0]["events"][2]["payload"]["value"] = 99
    with pytest.raises(ValueError, match="digest mismatch"):
        validate_evidence(evidence)


def test_rehashed_observation_without_request_is_still_rejected():
    evidence = sample_evidence()
    evidence["instances"][0]["events"].pop(1)
    rehash(evidence)
    with pytest.raises(ValueError, match="preceding matching request"):
        validate_evidence(evidence)


def test_rehashed_submission_before_observation_is_rejected():
    evidence = sample_evidence()
    events = evidence["instances"][0]["events"]
    events[2], events[3] = events[3], events[2]
    rehash(evidence)
    with pytest.raises(ValueError, match="precedes callback"):
        validate_evidence(evidence)


def test_size_limit_preserves_evaluation_but_never_claims_complete_trace():
    evidence = sample_evidence(max_bytes=10)
    validate_evidence(evidence)
    assert not evidence["capture_complete"]
    assert evidence_report(metrics_for(evidence))["rows"][0]["process"]["capture_status"] == "incomplete"


def test_caught_callback_failure_is_recorded():
    def bad_observation(n):
        raise ValueError("fixture")

    def candidate(n, observe, intervene, budget):
        try:
            observe(-1)
        except ValueError:
            pass
        return {}

    capture = recorder(candidate)
    capture(2, bad_observation, lambda *args: None, 1)
    evidence = capture.finish({"per_world": [{"split": "unsplit", "world_index": 0, "valid": False}]})
    validate_evidence(evidence)
    report = evidence_report(metrics_for(evidence))
    assert report["rows"][0]["process"]["failed_callbacks"] == 1
    assert report["rows"][0]["result"]["valid"] is False


def test_commit_is_recorded_before_result_and_cannot_be_rewritten_by_alias():
    task = "EvidenceSynthesis/ProspectiveMetaAnalysis"

    def candidate(problem, confirm):
        commit = {"forecast": 1.0}
        confirm(commit)
        commit["forecast"] = 9.0
        return {"confirmation_commit": commit}

    capture = recorder(candidate, task)
    capture({}, lambda commit: {"effect": 3.0})
    evidence = capture.finish({"per_world": [{"split": "development", "world_index": 0, "valid": False}]})
    validate_evidence(evidence)
    events = evidence["instances"][0]["events"]
    assert events[1]["payload"]["value"]["args"][0]["forecast"] == 1.0
    assert events[3]["payload"]["value"]["confirmation_commit"]["forecast"] == 9.0
    assert evidence_report(metrics_for(evidence))["rows"][0]["process"]["pre_result_commit_request_seq"] == [1]


def test_legacy_and_sealed_visibility_do_not_invent_evidence():
    assert evidence_report({"combined_score": 1})["status"] == "not_recorded"
    metrics = {"combined_score": 0.5, "valid": 1.0, "discovery_evidence": sample_evidence()}
    assert "discovery_evidence" not in search_visible_metrics(metrics)
    metrics["infrastructure_failure"] = 1.0
    assert evidence_report(metrics)["status"] == "infrastructure_failure"


@pytest.mark.parametrize("task_id", list(PILOTS))
def test_four_real_oracles_preserve_baseline_scores_and_link_every_world(task_id):
    spec = find_task(task_id, include_uncertified=True)
    oracle = load(spec.task_dir / "verification/evaluator.py")
    candidate = getattr(load(spec.initial_program_path), spec.entrypoint)
    direct = oracle.evaluate(candidate)
    capture = recorder(candidate, task_id)
    observed = oracle.evaluate(capture)
    assert observed == direct
    evidence = capture.finish(observed)
    validate_evidence(evidence)
    assert len(evidence["instances"]) == len(observed["per_world"])
    assert evidence["capture_complete"]
    assert all(r["discovery_certification"] == "not_assessed"
               for r in evidence_report(metrics_for(evidence))["rows"])


def test_trusted_entrypoint_records_candidate_failure_without_changing_public_error():
    spec = find_task(SCM, include_uncertified=True)

    class BrokenProxy:
        failure = None

        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def reset_session(self):
            if self.failure:
                raise self.failure

        def __call__(self, *args):
            self.failure = CandidateError("candidate call failed")
            raise self.failure

    with patch("sle.secure_eval.CandidateProxy", BrokenProxy), \
            patch("sle.secure_eval.read_candidate_packages", return_value=[]):
        metrics = trusted_evaluate(spec.task_dir, spec.initial_program_path, spec.entrypoint, "clipped", 10)
    assert metrics["valid"] == 0.0
    evidence = metrics["discovery_evidence"]
    validate_evidence(evidence)
    assert not evidence["evaluation_complete"]
    assert any(e["kind"] == "candidate_error" for i in evidence["instances"] for e in i["events"])
    assert "discovery_evidence" not in search_visible_metrics(metrics)


@skip_unless_sandbox("bwrap")
@pytest.mark.parametrize("task_id", list(PILOTS))
def test_real_sandbox_records_sealed_evidence(task_id):
    spec = find_task(task_id, include_uncertified=True)
    metrics = evaluate_candidate(spec, spec.initial_program_path, timeout_s=180)
    assert metrics["valid"] == 1.0, metrics
    evidence = metrics["discovery_evidence"]
    validate_evidence(evidence, expected_candidate_sha256=hashlib.sha256(spec.initial_program_path.read_bytes()).hexdigest())
    assert evidence["evaluation_complete"] and evidence["capture_complete"]
    assert "discovery_evidence" not in search_visible_metrics(metrics)
