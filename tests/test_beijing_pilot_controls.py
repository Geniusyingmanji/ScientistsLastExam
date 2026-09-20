"""Control behavior using hand-entered observations, never the sealed pilot."""
import copy
import hashlib
import json
from pathlib import Path

import pytest

from benchmarks.ComputerScience.MeasurementAudit.verification.episode import MeasurementEnvironment
from scripts.beijing_pilot_controls import (
    EVIDENCE_POLICIES, PERSISTENCE_ID, REPLICATION_ID, fixed_pooled, null_discovery,
)
from sle.evidence_episode import EvidenceEpisodeSession, run_discovery_policy
from sle.scientific_episode import validate_episode_report


def session(tmp_path, exploration_contrast=40, replication_contrast=40,
            exploration_group_size=2, replication_group_size=2):
    fixture = Path(__file__).resolve().parents[1] / "benchmarks/ComputerScience/MeasurementAudit/fixtures/protocol/manifest.json"
    manifest = json.loads(fixture.read_text())
    manifest["dataset_id"] = "hand-entered-beijing-control-test"
    manifest["columns"] = [
        {"name": "wind_regime", "unit": "category code", "description": "Hand-entered group, not real weather."},
        {"name": "pm_mean", "unit": "example units", "description": "Hand-entered value, not real PM."},
    ]
    rows = ["sample_id,partition,wind_regime,pm_mean"]
    for partition, contrast, count in (
            ("exploration", exploration_contrast, exploration_group_size),
            ("replication", replication_contrast, replication_group_size)):
        for group in (0, 1):
            for index in range(count):
                rows.append("{p}-{g}-{i},{p},{g},{v}".format(
                    p=partition, g=group, i=index, v=100 + contrast * group + index))
        rows.append("{p}-mixed,{p},2,777".format(p=partition))
    data = ("\n".join(rows) + "\n").encode()
    bundle = tmp_path.resolve() / "bundle"
    bundle.mkdir()
    (bundle / "measurements.csv").write_bytes(data)
    manifest["files"]["measurements.csv"] = hashlib.sha256(data).hexdigest()
    (bundle / "manifest.json").write_text(json.dumps(manifest))
    return EvidenceEpisodeSession(MeasurementEnvironment.from_bundle(bundle))


def test_control_runs_only_frozen_replication_after_commit(tmp_path):
    episode = session(tmp_path)
    dossier = fixed_pooled(episode.observation(), episode.step)
    before = [e for e in episode.events if e["kind"] == "native_observation"]
    assert len(before) == 1
    assert before[0]["payload"]["action"]["arguments"]["partition"] == "exploration"
    assert "test_id" not in before[0]["payload"]["action"]
    frozen = episode.ledger.get_test(REPLICATION_ID)
    assert frozen["predictions"][0]["interval"] == [20.0, 60.0]
    assert all(claim["support"] == [] for claim in dossier["claims"])
    assert episode.step({"action": "commit", "claim": dossier})["ok"]
    report = episode.report()
    native = [e for e in report["events"] if e["kind"] == "native_observation"]
    committed = next(e for e in report["events"] if e["kind"] == "commit")
    assert len(native) == 2
    assert native[1]["seq"] > committed["seq"]
    assert native[1]["payload"]["action"] == {
        "tool": frozen["tool"], "arguments": frozen["arguments"], "test_id": REPLICATION_ID}
    metrics = report["metrics"]
    assert len(metrics["checks"]) == 1
    assert metrics["checks"][0]["phase"] == "replication"
    assert metrics["checks"][0]["prospective"] is True
    assert metrics["claims"][0]["supporting_evidence"] == ["experiment-0002"]
    assert metrics["claims"][0]["evidence_status"] == "evidence-supported"
    assert metrics["ground_truth_used"] is False
    assert metrics["discovery_score"] is None
    assert metrics["semantic_review"]["status"] == "unassessed"
    assert all(axis["status"] == "unassessed" for axis in metrics["semantic_review"]["axes"])
    validate_episode_report(report)


def test_descriptive_exploration_cannot_gain_retrospective_prospective_credit(tmp_path):
    episode = session(tmp_path)
    dossier = fixed_pooled(episode.observation(), episode.step)
    retest = copy.deepcopy(episode.ledger.get_test(REPLICATION_ID))
    retest.pop("seq")
    retest.update(id="posthoc_exploration", phase="exploration")
    retest["arguments"]["partition"] = "exploration"
    assert episode.step({"action": "plan_test", "test": retest})["ok"]
    observed = episode.step({"action": "experiment", "tool": retest["tool"],
                             "arguments": retest["arguments"], "test_id": retest["id"]})
    dossier["replication_tests"] = []
    for claim in dossier["claims"]:
        claim["tests"] = [retest["id"]]
    dossier["claims"][0]["support"] = [observed["evidence_id"]]
    assert episode.step({"action": "commit", "claim": dossier})["ok"]
    report = episode.report()
    check = report["metrics"]["checks"][0]
    assert check["prospective"] is False
    assert check["preobserved_source"] == ["experiment-0001"]
    assert not any(h["discriminating_support"] for h in check["hypotheses"])
    assert report["metrics"]["claims"][0]["evidence_status"] == "unassessed"
    assert report["metrics"]["claims"][0]["unverified_support_citations"] == ["experiment-0002"]
    validate_episode_report(report)


def test_overlapping_tolerances_are_not_discriminating_success(tmp_path):
    report = run_discovery_policy(session(tmp_path, 5, 5), fixed_pooled)
    assert report["status"] == "completed"
    assert all(c["evidence_status"] == "inconclusive" for c in report["metrics"]["claims"])
    assert report["metrics"]["prospective_checks"]["discriminating_checks"]["numerator"] == 0
    validate_episode_report(report)


def test_insufficient_exploration_returns_lawful_inconclusive_no_finding(tmp_path):
    report = run_discovery_policy(session(tmp_path, exploration_group_size=1), fixed_pooled)
    assert report["status"] == "completed"
    assert report["resources"]["experiment_calls"] == 1
    assert report["metrics"]["null_discovery"] is True
    assert report["metrics"]["discovery_score"] is None
    assert report["claim"]["replication_tests"] == []
    assert any("measurement availability, not a model capability failure" in s for s in report["claim"]["limitations"])
    validate_episode_report(report)


def test_insufficient_replication_has_unassessed_measurement_not_false_rejection(tmp_path):
    report = run_discovery_policy(session(tmp_path, replication_group_size=1), fixed_pooled)
    assert report["status"] == "completed"
    assert report["metrics"]["checks"][0]["reason"] == "measurement_unavailable"
    assert all(c["evidence_status"] == "unassessed" for c in report["metrics"]["claims"])
    assert report["metrics"]["prospective_checks"]["replication_checks_assessed"] == 0
    validate_episode_report(report)


def test_null_control_does_not_query_or_invent_discovery(tmp_path):
    assert set(EVIDENCE_POLICIES) == {"fixed_pooled", "null"}
    report = run_discovery_policy(session(tmp_path), null_discovery)
    assert report["status"] == "completed"
    assert report["resources"]["experiment_calls"] == 0
    assert report["metrics"]["null_discovery"] is True
    assert report["metrics"]["discovery_score"] is None
    assert report["metrics"]["process"]["support_citation_verification"]["value"] is None
    validate_episode_report(report)


def test_heuristic_ignores_iid_standard_error(tmp_path):
    episode = session(tmp_path, exploration_contrast=-50)
    def misleading_diagnostic(request):
        response = episode.step(request)
        if "observation" in response:
            response["observation"]["std_error"] = 1e80
            for group in response["observation"]["groups"]:
                group["std_error"] = 1e80
        return response
    fixed_pooled(episode.observation(), misleading_diagnostic)
    frozen = episode.ledger.get_test(REPLICATION_ID)
    assert frozen["predictions"][0]["hypothesis_id"] == PERSISTENCE_ID
    assert frozen["predictions"][0]["interval"] == [-75.0, -25.0]


def test_control_rejects_unrelated_schema_before_query():
    def no_calls(request):
        pytest.fail("wrong-schema control should not query")
    with pytest.raises(ValueError, match="requires pm_mean and wind_regime"):
        fixed_pooled({"problem": {"data_binding": {"columns": []}}}, no_calls)
