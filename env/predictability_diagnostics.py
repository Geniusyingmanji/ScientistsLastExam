"""Read-only paired error/headroom audit of archived episode reports.

No simulator, candidate, current scorer, network client or baseline is imported.
Stored normalized RMSE is squared once per original experiment. All outputs are
diagnostic subsets with visible failure denominators, never replacement scores.
"""

import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path
import re


PROTOCOL = "sle-paired-predictability-audit-0.1"
KINDS = ("conditions", "interventions")
BASELINE_MSE_FLOOR = 1e-12
_IDENTIFIER = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,159}\Z")
_EPISODE_CATEGORIES = ("completed", "invalid_predictor", "incomplete", "other_model_failure",
                       "infrastructure_failure", "missing_report", "unreadable_report")


def assumptions():
    return {
        "unit": "One stored private-panel experiment; equal weight per paired experiment, not per time sample or channel.",
        "pairing": "Same episode, panel kind and unique panel index. Baseline records lack specs in these archives; shared query identity relies on the frozen runner's index contract.",
        "eligible": "Candidate valid=true and baseline not explicitly invalid; both finite nonnegative normalized_rmse, finite original score in [0,100], and the same positive scored_rows.",
        "mse": "Mean of squared normalized_rmse over exactly the same paired experiments. The original public scaling and initial-row rule are inherited from the archived errors.",
        "skill": "1 - candidate_mean_mse/baseline_mean_mse; ratio of means, not mean of ratios. Undefined if baseline_mean_mse <= 1e-12 or no pairs.",
        "scores": "Means of original archived exponential prediction scores on that same paired subset; no recomputation and no claims/cross-kind/cross-cohort composite.",
        "failures": "All planned episodes and expected panels stay in denominator accounting. Valid pairs from partial/failed episodes are retained and explicitly counted by status. Invalid/missing errors are not converted to zero or silently omitted.",
        "scope": "Descriptive posthoc audit of a subset. Baselines may have different prior model-family information. Skill measures relative prediction error, not mechanism recovery, novelty or contamination resistance.",
        "uncertainty": "Panels within an episode are dependent; no panel-level significance test or confidence interval is claimed. Cohorts remain separate, including the one-episode interface smoke.",
    }


def _identifier(value):
    if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
        raise ValueError("invalid manifest identifier")
    return value


def _number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("invalid stored number")
    try:
        value = float(value)
    except (ValueError, OverflowError):
        raise ValueError("invalid stored number") from None
    if not math.isfinite(value):
        raise ValueError("invalid stored number")
    return value


def _metric(row, candidate):
    if row is None:
        return None, "missing"
    if row.get("valid") is False:
        return None, "invalid"
    if (candidate and row.get("valid") is not True) or ("valid" in row and type(row["valid"]) is not bool):
        return None, "malformed"
    try:
        error, score = _number(row.get("normalized_rmse")), _number(row.get("score"))
        mse = error * error
        if error < 0 or not math.isfinite(mse) or not 0 <= score <= 100:
            raise ValueError()
        count = row.get("scored_rows")
        if type(count) is not int or count < 1:
            raise ValueError()
    except ValueError:
        return None, "malformed"
    return {"normalized_rmse": error, "mse": mse, "original_score": score, "scored_rows": count}, "valid"


def _indexed(rows, expected):
    indexed = defaultdict(list)
    malformed, unexpected = 0, 0
    if not isinstance(rows, list):
        return {}, 1, 0
    for row in rows:
        if not isinstance(row, dict) or type(row.get("index")) is not int:
            malformed += 1
        elif not 0 <= row["index"] < expected:
            unexpected += 1
        else:
            indexed[row["index"]].append(row)
    return indexed, malformed, unexpected


def _panel_rows(report, field, kind):
    data = report.get(field, {})
    return data.get(kind, []) if isinstance(data, dict) else None


def _paired_panels(report, kind, expected):
    candidates, malformed_c, unexpected_c = _indexed(_panel_rows(report, "panels", kind), expected)
    baselines, malformed_b, unexpected_b = _indexed(_panel_rows(report, "baseline_panels", kind), expected)
    counts = {"expected_panels": expected, "paired_panels": 0,
              "candidate_valid_panels": 0, "baseline_valid_panels": 0,
              "malformed_candidate_rows": malformed_c, "malformed_baseline_rows": malformed_b,
              "unexpected_candidate_rows": unexpected_c, "unexpected_baseline_rows": unexpected_b}
    reasons, details, pairs = Counter(), [], []
    for index in range(expected):
        metrics, statuses = {}, {}
        for arm, indexed in (("candidate", candidates), ("baseline", baselines)):
            rows = indexed.get(index, [])
            if len(rows) > 1:
                metrics[arm], statuses[arm] = None, "duplicate_index"
            else:
                metrics[arm], statuses[arm] = _metric(rows[0] if rows else None, arm == "candidate")
            if statuses[arm] == "valid":
                counts[arm + "_valid_panels"] += 1
        reason = next((arm + "_" + statuses[arm] for arm in ("candidate", "baseline")
                       if statuses[arm] != "valid"), None)
        if reason is None and metrics["candidate"]["scored_rows"] != metrics["baseline"]["scored_rows"]:
            reason = "scored_rows_mismatch"
        detail = {"index": index, "candidate_status": statuses["candidate"],
                  "baseline_status": statuses["baseline"], "exclusion_reason": reason,
                  "candidate": metrics["candidate"], "baseline": metrics["baseline"]}
        details.append(detail)
        if reason is None:
            counts["paired_panels"] += 1
            pairs.append(metrics)
        else:
            reasons[reason] += 1
    counts["excluded_panels"] = expected - len(pairs)
    counts["exclusion_reasons"] = dict(sorted(reasons.items()))
    return counts, pairs, details


def _mean(values):
    return math.fsum(value / len(values) for value in values) if values else None


def _summary(pairs):
    candidate = _mean([pair["candidate"]["mse"] for pair in pairs])
    baseline = _mean([pair["baseline"]["mse"] for pair in pairs])
    reason = "no_valid_pairs" if not pairs else "baseline_near_zero" if baseline <= BASELINE_MSE_FLOOR else None
    skill = None if reason else 1.0 - candidate / baseline
    if skill is not None and not math.isfinite(skill):
        skill, reason = None, "nonfinite_ratio"
    return {"paired_panels": len(pairs), "candidate_mean_mse": candidate, "baseline_mean_mse": baseline,
            "candidate_pooled_nrmse": math.sqrt(candidate) if pairs else None,
            "baseline_pooled_nrmse": math.sqrt(baseline) if pairs else None,
            "skill": skill, "skill_undefined_reason": reason,
            "candidate_original_prediction_score_mean": _mean([p["candidate"]["original_score"] for p in pairs]),
            "baseline_original_prediction_score_mean": _mean([p["baseline"]["original_score"] for p in pairs]),
            "candidate_lower_error_panels": sum(p["candidate"]["mse"] < p["baseline"]["mse"] for p in pairs),
            "equal_error_panels": sum(p["candidate"]["mse"] == p["baseline"]["mse"] for p in pairs),
            "candidate_higher_error_panels": sum(p["candidate"]["mse"] > p["baseline"]["mse"] for p in pairs)}


def _category(report, error):
    if error:
        return "unreadable_report"
    if report is None:
        return "missing_report"
    if report.get("infrastructure_failure"):
        return "infrastructure_failure"
    if report.get("status") == "completed" and report.get("model_completed") is True:
        return "completed"
    if report.get("status") == "invalid_predictor":
        return "invalid_predictor"
    if report.get("status") in ("incomplete", "exploring", "frozen"):
        return "incomplete"
    return "other_model_failure"


def audit_reports(manifest, reports, *, report_errors=None):
    """Pure computation over existing JSON dictionaries. Returns private/public views."""
    cohort = _identifier(manifest.get("cohort"))
    instances = manifest.get("instances")
    expected = manifest.get("limits", {}).get("panel_count")
    if not isinstance(instances, list) or not instances or len(instances) > 1000 or type(expected) is not int or not 1 <= expected <= 64:
        raise ValueError("invalid frozen episode/panel count")
    if not isinstance(reports, dict) or (report_errors is not None and not isinstance(report_errors, dict)):
        raise ValueError("reports must be indexed by episode id")
    report_errors = report_errors or {}
    ids = [_identifier(row["episode_id"]) for row in instances]
    if len(set(ids)) != len(ids):
        raise ValueError("duplicate planned episode")
    groups, anonymous, private, episodes = {}, [], [], Counter()
    counters = Counter()
    for instance in instances:
        episode_id, environment = instance["episode_id"], _identifier(instance["environment"])
        counters[environment] += 1
        alias = "%s-E%02d" % (environment, counters[environment])
        report = reports.get(episode_id)
        error = report_errors.get(episode_id)
        if report is not None and (not isinstance(report, dict) or report.get("episode_id") != episode_id or
                                   report.get("environment") != environment or report.get("cohort", cohort) != cohort):
            error, report = "identity_or_object_mismatch", None
        category = _category(report, error)
        episodes[category] += 1
        for kind in KINDS:
            counts, pairs, details = _paired_panels(report or {}, kind, expected)
            group = groups.setdefault((environment, kind), {"counts": Counter(), "exclusions": Counter(),
                "episodes": Counter(), "paired_by_category": Counter(), "pairs": [], "episode_metrics": []})
            group["counts"].update({key: value for key, value in counts.items() if key != "exclusion_reasons"})
            group["exclusions"].update(counts["exclusion_reasons"])
            group["episodes"][category] += 1
            group["paired_by_category"][category] += len(pairs)
            group["pairs"].extend(pairs)
            metrics = _summary(pairs)
            group["episode_metrics"].append(metrics)
            anonymous.append(dict(cohort=cohort, environment=environment, instance=alias, panel_kind=kind,
                                  episode_category=category, counts=counts, paired_metrics=metrics))
            private.append(dict(episode_id=episode_id, environment=environment, instance=alias, panel_kind=kind,
                                report_error=error, archived_status=(report or {}).get("status"),
                                infrastructure_failure=(report or {}).get("infrastructure_failure"), panels=details))
    summaries = []
    for (environment, kind), group in sorted(groups.items()):
        counts = dict(group["counts"], exclusion_reasons=dict(sorted(group["exclusions"].items())))
        comparisons = Counter()
        for metric in group["episode_metrics"]:
            if not metric["paired_panels"]:
                comparisons["unavailable"] += 1
            elif metric["candidate_mean_mse"] < metric["baseline_mean_mse"]:
                comparisons["candidate_lower_error"] += 1
            elif metric["candidate_mean_mse"] > metric["baseline_mean_mse"]:
                comparisons["candidate_higher_error"] += 1
            else:
                comparisons["equal_error"] += 1
        summaries.append(dict(cohort=cohort, environment=environment, panel_kind=kind, counts=counts,
                              episode_counts={key: group["episodes"][key] for key in _EPISODE_CATEGORIES},
                              paired_panels_by_episode_category={key: group["paired_by_category"][key] for key in _EPISODE_CATEGORIES},
                              episode_mean_mse_comparison=dict(comparisons), paired_metrics=_summary(group["pairs"])))
    public = {"protocol": PROTOCOL, "cohort": cohort, "diagnostic_only": True, "formal_score_modified": False,
              "planned_episodes": len(ids), "episode_counts": {key: episodes[key] for key in _EPISODE_CATEGORIES},
              "unplanned_reports": len(set(reports) - set(ids)), "world_summaries": summaries, "anonymous_episode_rows": anonymous}
    return {"public": public, "private_episode_rows": private}


def _read(path, provenance):
    raw = path.read_bytes()
    provenance[str(path.resolve())] = hashlib.sha256(raw).hexdigest()
    return json.loads(raw)


def audit_cohort(directory):
    """Read one immutable archive, recording byte hashes and every planned report."""
    directory = Path(directory).resolve()
    provenance = {}
    manifest = _read(directory / "manifest-private.json", provenance)
    reports, errors = {}, {}
    for instance in manifest.get("instances", []):
        episode_id = _identifier(instance["episode_id"])
        path = directory / "episodes" / episode_id / "report.json"
        if path.exists():
            try:
                reports[episode_id] = _read(path, provenance)
            except (ValueError, UnicodeError, OSError) as error:
                errors[episode_id] = type(error).__name__
    planned = {instance["episode_id"] for instance in manifest.get("instances", [])}
    unplanned = sorted(str(path.resolve()) for path in (directory / "episodes").glob("*/report.json") if path.parent.name not in planned)
    result = audit_reports(manifest, reports, report_errors=errors)
    result["public"]["unplanned_reports"] = len(unplanned)
    result["private_provenance"] = {"input_sha256": provenance, "unplanned_report_paths": unplanned,
                                    "archived_source_sha256": manifest.get("source_sha256"),
                                    "archived_score_protocol": manifest.get("score_contract", {}).get("protocol")}
    verify_inputs(provenance)
    return result


def verify_inputs(provenance):
    for path, expected in provenance.items():
        if hashlib.sha256(Path(path).read_bytes()).hexdigest() != expected:
            raise ValueError("archived input changed during analysis")


def write_audit(cohorts, output, *, analysis_plan):
    """Write a new artifact directory; never overwrite an archive or prior audit."""
    output, plan = Path(output).resolve(), Path(analysis_plan).resolve()
    directories = [Path(path).resolve() for path in cohorts]
    if not directories or len(set(directories)) != len(directories):
        raise ValueError("select distinct cohort directories explicitly")
    for directory in directories:
        if output == directory or directory in output.parents or output in directory.parents:
            raise ValueError("audit output must be separate from source cohorts")
    plan_raw = plan.read_bytes()
    plan_value = json.loads(plan_raw)
    if plan_value.get("protocol") != PROTOCOL:
        raise ValueError("analysis plan protocol mismatch")
    results = [audit_cohort(directory) for directory in directories]
    if [result["public"]["cohort"] for result in results] != plan_value.get("cohorts"):
        raise ValueError("selected cohorts differ from prespecified plan")
    for result in results:
        verify_inputs(result["private_provenance"]["input_sha256"])
    public = {"protocol": PROTOCOL, "assumptions": assumptions(), "cohorts": [result["public"] for result in results]}
    private = {"protocol": PROTOCOL, "analysis_plan": plan_value,
               "analysis_plan_sha256": hashlib.sha256(plan_raw).hexdigest(),
               "analyzer_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), "cohorts": results}
    # Build and validate both serializations before creating any output file.
    encoded = {"public-summary.json": json.dumps(public, indent=2, sort_keys=True, allow_nan=False),
               "private-detail.json": json.dumps(private, indent=2, sort_keys=True, allow_nan=False)}
    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    for name, value in encoded.items():
        with (output / name).open("x", encoding="utf-8") as stream:
            stream.write(value + "\n")
        (output / name).chmod(0o600)
    return public


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cohort", action="append", required=True, help="Explicit existing cohort directory; repeat to retain separate batches")
    parser.add_argument("--analysis-plan", required=True)
    parser.add_argument("--output", required=True, help="New output directory outside the source cohorts")
    args = parser.parse_args()
    public = write_audit(args.cohort, args.output, analysis_plan=args.analysis_plan)
    print(json.dumps({"protocol": PROTOCOL, "cohorts": [row["cohort"] for row in public["cohorts"]]}))


if __name__ == "__main__":
    main()
