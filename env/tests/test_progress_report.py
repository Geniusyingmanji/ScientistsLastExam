import json
from copy import deepcopy

import pytest

from env.progress_report import build_report, _evidence_matrix, EVIDENCE_COLUMNS


def test_public_export_includes_failures_but_excludes_private_targets(tmp_path):
    private = tmp_path / "operator"
    private.mkdir()
    manifest = {"cohort": "test", "environments": ["microecology"], "source_sha256": "a" * 64,
                "world_seed": "OPERATOR_SECRET_SENTINEL", "instances": [{"episode_id": "a"}, {"episode_id": "b"}],
                "score_contract": {"protocol": "test-score"}, "limits": {"rounds": 4}}
    (private / "manifest-private.json").write_text(json.dumps(manifest))
    for identifier, score, status in (("a", 80, "completed"), ("b", 0, "invalid_predictor")):
        directory = private / "episodes" / identifier
        directory.mkdir(parents=True)
        report = {"episode_id": identifier, "environment": "microecology", "status": status,
                  "score": score, "subscores": {"conditions": score, "interventions": score, "claims": score},
                  "model_completed": status == "completed", "infrastructure_failure": None,
                  "operator_private": "OPERATOR_SECRET_SENTINEL", "panels": {}, "history": []}
        (directory / "started.json").write_text(json.dumps({"episode_id": identifier, "environment": "microecology"}))
        (directory / "report.json").write_text(json.dumps(report))
    # Public export must not rewrite frozen operator summaries or reports.
    (private / "summary.json").write_text('{"frozen": true}\n')
    (private / "index.html").write_text("frozen operator report\n")
    before = {path.relative_to(private): path.read_bytes()
              for path in private.rglob("*") if path.is_file()}
    output = tmp_path / "public"
    data = build_report([("formal", private)], {"summary": "<script>unsafe()</script>"}, output)
    assert data["cohorts"][0]["macro_score"] == 40
    assert data["cohorts"][0]["model_completion"]["denominator"] == 2
    for path in (output / "index.html", output / "data.json"):
        assert "OPERATOR_SECRET_SENTINEL" not in path.read_text()
        assert "manifest-private" not in path.read_text()
    page = (output / "index.html").read_text()
    assert "<script>unsafe()" not in page and "&lt;script&gt;unsafe()" in page
    assert "data.json" in page
    after = {path.relative_to(private): path.read_bytes()
             for path in private.rglob("*") if path.is_file()}
    assert before == after


def _sample():
    return {"selection": "Fixed first-indexed sample, not a population estimate.",
            "review_scope": "same-family / provisional; external chronology unverified",
            "rows": [{"case": "<script>case</script>",
                      "assessments": {key: "unassessable" for key, _ in EVIDENCE_COLUMNS},
                      "limitation": "Unobserved intervals remain <unknown>."}]}


def test_manual_evidence_display_preserves_unknown_and_does_not_infer_depth():
    sample = _sample()
    sample["rows"][0]["assessments"].update(quantitative_model="supported",
        prospective_test="partial", meaningful_rival="not_demonstrated")
    before = deepcopy(sample)
    page = _evidence_matrix(sample)
    assert sample == before and _evidence_matrix(None) == ""
    for label in ("支持", "部分支持", "未展示", "无法判断", "不生成深度等级或发现率"):
        assert label in page
    assert "<script>" not in page and "&lt;script&gt;case&lt;/script&gt;" in page
    assert "same-family / provisional" in page and "&lt;unknown&gt;" in page
    assert "D4" not in page and "100%" not in page


@pytest.mark.parametrize("mutation", [
    lambda sample: sample.update(private_targets={"sentinel": 1}),
    lambda sample: sample["rows"][0].update(depth="D4"),
    lambda sample: sample["rows"][0]["assessments"].update(prospective_test="passed"),
    lambda sample: sample["rows"][0]["assessments"].pop("empirical_boundary"),
    lambda sample: sample.update(rows=[]),
])
def test_bad_manual_evidence_is_rejected_before_any_public_write(tmp_path, mutation):
    sample = _sample()
    mutation(sample)
    destination = tmp_path / "public"
    with pytest.raises(ValueError, match="curated"):
        build_report([], {"evidence_sample": sample}, destination)
    assert not destination.exists()
