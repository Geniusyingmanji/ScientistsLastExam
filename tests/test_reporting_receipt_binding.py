"""Exercise reporter trust against real synthetic ledger receipts, including corruption."""
from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from scripts import report_admission_criterion as admission
from scripts import report_cross_model as cross
from scripts import report_discovery_triple as triple
from scripts.reporting_runtime import report_runtime_binding
from test_report_runtime_identity import write_verified_run


def fixture_run(tmp_path):
    run = tmp_path / "runs/cohort/run"
    run.mkdir(parents=True)
    write_verified_run(run, budget=1)
    return run, json.loads((run / "run_manifest.json").read_text())


def test_reporters_bind_validated_budget_and_exact_manifest(tmp_path):
    run, manifest = fixture_run(tmp_path)
    binding = report_runtime_binding(run, manifest)
    assert binding["trusted_evidence"] is True
    assert binding["proposal_budget"] == 1
    assert len(binding["run_manifest_sha256"]) == 64
    assert admission.RunCurve([.01], run, manifest).run["budget"] == 1
    assert cross.read_runs(tmp_path / "runs")[0]["trusted_evidence"] is True


def test_tampered_new_format_is_unusable_in_every_reporter(tmp_path):
    run, manifest = fixture_run(tmp_path)
    # Keep the trajectory score internally consistent, but break its durable receipt binding.
    path = run / "trajectory.jsonl"
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    rows[-1]["algorithm_metadata"]["evaluation_request_id"] = "0" * 64
    path.write_text("\n".join(map(json.dumps, rows)) + "\n")
    binding = report_runtime_binding(run, manifest)
    assert binding["trusted_evidence"] is False
    assert binding["verification_status"] == "unverified"
    assert binding["proposal_budget"] is None
    row = cross.read_runs(tmp_path / "runs")[0]
    assert row["trusted_evidence"] is False
    assert not cross.attributable_score_run(row)
    with contextlib.redirect_stdout(io.StringIO()), patch.object(triple, "discovery_task_names", return_value={"X"}), patch.object(triple, "current_contracts", return_value={}):
        output = tmp_path / "triple.json"
        triple.main(["--runs", str(tmp_path / "runs"), "--output", str(output)])
    triple_row = json.loads(output.read_text())["rows"][0]
    assert triple_row["status"] == "unverified_run"
    assert triple_row["trusted_evidence"] is False
    with contextlib.redirect_stdout(io.StringIO()):
        output = tmp_path / "admission.json"
        admission.main(["--runs", str(tmp_path / "runs"), "--output", str(output)])
    row = json.loads(output.read_text())["rows"][0]
    assert row["verdict"] == "unattributable_evidence"
    assert row["trusted_evidence"] is False


@pytest.mark.parametrize("descriptor", [None, {}, [], "invalid"])
def test_malformed_new_descriptor_never_falls_back_to_legacy(tmp_path, descriptor):
    run, manifest = fixture_run(tmp_path)
    manifest["trusted_evaluator_runtime"] = descriptor
    (run / "run_manifest.json").write_text(json.dumps(manifest))
    result = report_runtime_binding(run, manifest)
    assert result["verification_status"] == "unverified"
    assert result["trusted_evidence"] is False


def test_historical_diagnostics_never_acquire_runtime_or_budget(tmp_path):
    run, manifest = fixture_run(tmp_path)
    manifest.pop("trusted_evaluator_runtime")
    (run / "run_manifest.json").write_text(json.dumps(manifest))
    result = report_runtime_binding(run, manifest)
    assert result["verification_status"] == "legacy_format"
    assert result["trusted_evidence"] is False
    assert result["trusted_evaluator_runtime_sha256"] is None
    assert result["proposal_budget"] is None
