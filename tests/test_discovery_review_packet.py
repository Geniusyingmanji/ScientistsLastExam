"""Review preparation indexes manual evidence; it never runs candidate code."""
import copy
import hashlib
import json
import stat
from pathlib import Path

import pytest

from sle.discovery_review import SEMANTIC_REVIEW_AXES
from sle.discovery_review_packet import build_review_packet, prepare_review_packet
from sle.evidence_episode import EvidenceEpisodeSession
from sle.posttest_episode import PostTestEvidenceSession, run_posttest_policy
from sle.scientific_episode import digest
from tests.test_evidence_episode import ObservationsOnly, completed, register, dossier
from tests.test_posttest_episode import frozen, complete


@pytest.mark.parametrize("version", [1, 2])
def test_index_is_detached_all_references_resolve_and_no_science_is_scored(version):
    report = completed().report() if version == 1 else complete(frozen())
    original = copy.deepcopy(report)
    packet = build_review_packet(report)
    assert report == original
    assert packet["source"]["report_sha256"] == report["sha256"]
    assert packet["source"]["file_sha256"] is None
    assert packet["scientific_score"] is None and packet["status"] == "unassessed"
    assert packet["process_check"]["scientific_validity"] == "not_assessed"
    assert len(packet["stages"]) == 6 and len(packet["semantic_axes"]) == 8
    expected_axes = {row[0] for row in SEMANTIC_REVIEW_AXES}
    assert {row["axis"] for row in packet["semantic_axes"]} == expected_axes
    assert {axis for stage in packet["stages"] for axis in stage["semantic_axes"]} == expected_axes
    for row in packet["stages"] + packet["semantic_axes"]:
        assert row["judgment"]["status"] == "unassessed"
        assert row["judgment"]["rationale"] is None
        assert row["judgment"]["evidence_references"] == []
    for stage in packet["stages"]:
        for ref in stage["available_record_references"]:
            index = int(ref["report_pointer"].split("/")[-1])
            assert report["events"][index]["sha256"] == ref["event_sha256"]
            assert report["events"][index]["kind"] == ref["event_kind"]
    assert all(value is None for value in packet["reviewer"].values())
    assert packet["sha256"] == digest({k: v for k, v in packet.items() if k != "sha256"})
    packet["semantic_axes"][0]["judgment"]["status"] = "manual-edit"
    assert report == original


def test_v1_posttest_absence_is_protocol_unavailable_not_scientific_failure():
    packet = build_review_packet(completed().report())
    assert packet["posttest_interpretation"] == {
        "record_availability": "not_available_in_protocol",
        "absence_is_scientific_failure": False, "conclusion_timing": "pretest"}
    conclusions = packet["stages"][-1]
    assert {ref["event_kind"] for ref in conclusions["available_record_references"]} == {"commit"}
    assert conclusions["judgment"]["status"] == "unassessed"


def test_v2_missing_interpretation_is_recorded_as_missing_without_invented_judgment():
    session = frozen()
    session.stop("incomplete_delivery")
    packet = build_review_packet(session.report())
    assert packet["posttest_interpretation"]["record_availability"] == "not_recorded"
    assert packet["source"]["episode_status"] == "incomplete_delivery"
    assert packet["stages"][-1]["record_availability"] == "not_recorded"
    assert all(row["judgment"]["status"] == "unassessed" for row in packet["stages"])


def test_null_discovery_has_recorded_final_interpretation_without_invented_hypotheses():
    def manual_policy(context, act):
        result = act({"action": "commit", "claim": {"claims": [], "replication_tests": [], "limitations": []}})
        return {"plan_sha256": result["plan_sha256"], "results_sha256": result["results_sha256"],
                "test_responses": [], "conclusions": [], "posthoc_hypotheses": [], "limitations": []}
    report = run_posttest_policy(PostTestEvidenceSession(ObservationsOnly()), manual_policy)
    packet = build_review_packet(report)
    assert packet["posttest_interpretation"]["record_availability"] == "recorded"
    assert packet["stages"][1]["record_availability"] == "not_recorded"
    assert packet["stages"][-1]["record_availability"] == "recorded"
    assert packet["scientific_score"] is None


def test_analysis_failures_are_indexed_without_copying_or_executing_private_material(monkeypatch):
    session = EvidenceEpisodeSession(ObservationsOnly(),
        binding={"task_id": "Test/NoGroundTruth", "private_canary": "DO_NOT_COPY_BINDING"},
        analysis=lambda *_: {"ok": False, "error": "MANUAL_PRIVATE_ERROR"})
    register(session, exploration=False)
    session.step({"action": "analyze", "code": "raise Exception('NEVER_EXECUTE_PRIVATE_CODE')"})
    session.step({"action": "commit", "claim": dossier()})
    report = session.report()
    # The recorded code is only a string. Reading this artifact must not invoke
    # any new experiment, analysis, environment or model transport.
    monkeypatch.setattr(ObservationsOnly, "experiment", lambda *_: pytest.fail("unexpected measurement"))
    monkeypatch.setattr("urllib.request.urlopen", lambda *_a, **_k: pytest.fail("unexpected API"))
    packet = build_review_packet(report)
    rendered = json.dumps(packet)
    for private in ("DO_NOT_COPY_BINDING", "MANUAL_PRIVATE_ERROR", "NEVER_EXECUTE_PRIVATE_CODE"):
        assert private not in rendered
    evidence = next(row for row in packet["stages"] if row["stage"] == "evidence")
    assert "observation" in {ref["event_kind"] for ref in evidence["available_record_references"]}
    assert evidence["judgment"]["status"] == "unassessed"


@pytest.mark.parametrize("corruption", ["digest", "event", "oracle", "binding"])
def test_rejects_corrupt_or_non_evidence_reports(corruption):
    report = completed().report()
    if corruption == "digest": report["sha256"] = "0" * 64
    if corruption == "event": report["events"][1]["payload"] = {"fabricated": True}
    if corruption == "oracle": report["binding"]["evaluation_mode"] = "oracle_diagnostic"
    if corruption == "binding": report["binding"] = "invalid"
    with pytest.raises(ValueError):
        build_review_packet(report)


def test_private_exclusive_output_binds_original_bytes_and_never_rewrites_source(tmp_path):
    source = tmp_path / "episode.json"
    raw = (json.dumps(completed().report(), indent=3) + "\n").encode()
    source.write_bytes(raw)
    directory = tmp_path.resolve() / "review"
    output = prepare_review_packet(source, directory)
    packet = json.loads(output.read_text())
    assert packet["source"]["file_sha256"] == hashlib.sha256(raw).hexdigest()
    assert stat.S_IMODE(directory.stat().st_mode) == 0o700
    assert stat.S_IMODE(output.stat().st_mode) == 0o600
    original_output = output.read_bytes()
    with pytest.raises(FileExistsError):
        prepare_review_packet(source, directory)
    assert output.read_bytes() == original_output and source.read_bytes() == raw


def test_output_cannot_be_in_git_or_alongside_original_episode(tmp_path):
    source = tmp_path.resolve() / "original" / "episode.json"
    source.parent.mkdir(mode=0o700)
    source.write_text(json.dumps(completed().report()))
    with pytest.raises(ValueError):
        prepare_review_packet(source, source.parent)
    checkout = tmp_path.resolve() / "checkout"
    (checkout / ".git").mkdir(parents=True)
    with pytest.raises(ValueError):
        prepare_review_packet(source, checkout / "review")
    assert not (checkout / "review").exists()


def test_cli_rejects_invalid_input_without_printing_private_content(tmp_path, capsys):
    from scripts.prepare_discovery_review import main
    source = tmp_path / "invalid.json"
    source.write_text("PRIVATE_CORRUPT_TEXT")
    assert main(["--episode", str(source), "--output-dir", str(tmp_path / "review")]) == 2
    captured = capsys.readouterr()
    assert "PRIVATE_CORRUPT_TEXT" not in captured.out + captured.err
    assert not (tmp_path / "review").exists()
