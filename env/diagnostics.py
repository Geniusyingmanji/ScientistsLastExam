"""Trace-derived process diagnostics, separate from scientific scoring/depth."""
from collections import Counter


def trace_diagnostics(reports):
    """Count recorded events only; do not infer causes from missing outcomes.

    A failed batch may already have produced valid experiments. Therefore action
    errors and the experiment count are separate quantities, not complements.
    No free-text claim, private specification, observation or code is exported.
    """
    actions, analysis_errors, action_errors, stops = Counter(), Counter(), Counter(), Counter()
    api_attempts = rounds = experiments = 0
    error_runs = analysis_error_runs = analysis_exhausted = 0
    for report in reports:
        api_attempts += (report.get("transport") or {}).get("attempts", 0)
        rounds += len(report.get("rounds", []))
        experiments += report.get("experiment_count", 0)
        stops[str(report.get("stop_reason", "unknown"))] += 1
        has_error, has_analysis_error = False, False
        for turn in report.get("history", []):
            outcome = turn.get("outcome", "unknown")
            actions[outcome] += 1
            if outcome == "invalid_action":
                # Only fixed validation classes or public parsing errors; the
                # detailed user/model text remains in the private raw trace.
                error = str(turn.get("error", "unknown"))
                if error.startswith(("Expecting ", "Extra data:", "Invalid ", "Unterminated ")):
                    category = "json_parse_error"
                elif error == "expected_note_and_exactly_one_of_experiments_analyze_submit":
                    category = "action_schema_error"
                elif "exhausted" in error:
                    category = "experiment_budget_exhausted"
                elif error == "submission_required_in_closing_phase":
                    category = "ignored_submission_phase"
                else:
                    category = "public_spec_or_submission_validation"
                action_errors[category] += 1
                has_error = True
            if outcome == "analysis_failed":
                error = (turn.get("analysis") or {}).get("error", "unknown")
                category = error.get("candidate_failure_kind", "candidate_failure") if isinstance(error, dict) else str(error)
                analysis_errors[category] += 1
                has_analysis_error = True
        error_runs += has_error
        analysis_error_runs += has_analysis_error
        remaining = report.get("analysis_seconds_remaining")
        analysis_exhausted += remaining is not None and remaining <= 0
    return {"reports": len(reports), "model_requests_started": api_attempts,
            "recorded_model_rounds": rounds, "successful_experiments": experiments,
            "action_outcomes": dict(actions), "invalid_action_categories": dict(action_errors),
            "analysis_error_types": dict(analysis_errors), "stop_reasons": dict(stops),
            "runs_with_invalid_actions": error_runs, "runs_with_analysis_errors": analysis_error_runs,
            "runs_with_exhausted_analysis_allowance": analysis_exhausted,
            "interpretation": "Recorded process events; not a causal attribution or discovery-depth score."}
