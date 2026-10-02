from env.diagnostics import trace_diagnostics


def test_invalid_partial_batch_keeps_successful_experiments_and_separate_errors():
    rows = [{"transport": {"attempts": 4}, "rounds": [{}, {}, {}, {}],
             "experiment_count": 3, "analysis_seconds_remaining": 0,
             "stop_reason": "verified", "history": [
                 {"outcome": "invalid_action", "error": "experiment_count_exhausted", "observations": [{}, {}]},
                 {"outcome": "analysis_failed", "analysis": {"error": "TypeError"}},
                 {"outcome": "analysis_failed", "analysis": {"error": {"candidate_failure_kind": "candidate_timeout"}}},
                 {"outcome": "submission_frozen"}]}]
    result = trace_diagnostics(rows)
    assert result["successful_experiments"] == 3
    assert result["runs_with_analysis_errors"] == 1
    assert result["runs_with_invalid_actions"] == 1
    assert result["runs_with_exhausted_analysis_allowance"] == 1
    assert result["analysis_error_types"] == {"TypeError": 1, "candidate_timeout": 1}
    assert result["model_requests_started"] == 4


def test_diagnostics_export_does_not_copy_private_free_text():
    result = trace_diagnostics([{"history": [{"outcome": "invalid_action", "error": "private-payload-secret"}],
                                 "records": [{"private": "private-payload-secret"}]}])
    assert "private-payload-secret" not in str(result)
    assert result["invalid_action_categories"] == {"public_spec_or_submission_validation": 1}
    assert trace_diagnostics([])["runs_with_exhausted_analysis_allowance"] == 0
