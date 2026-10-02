import json

from env.progress_report import build_report


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
