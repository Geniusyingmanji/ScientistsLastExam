"""Private, posthoc prediction diagnostics; never replace the formal score.

Only stored JSON matrices and certified public oscillator/Ising semantics are
accepted. No candidate, simulator, model API, filesystem, or legacy-output
reconstruction is invoked. Removing a publicly assigned cell does not establish
that the remaining cells measure a mechanism or independent scientific content.
"""
from collections import Counter
import math
import numbers

from .prediction_semantics import PROTOCOL as SEMANTICS_PROTOCOL
from .prediction_semantics import SUPPORTED, classify_cells, summarize_cells


PROTOCOL = "private-prediction-residual-diagnostic-0.1"
ERROR_SCALE = 0.1
# Public instrument scales, aligned with each certified contract's channel order.
_SCALES = {"coupled_oscillators": (1.0,) * 4 + (2.0,) * 4, "ising_spin": (1.0,) * 21}
_CLEAN_CONSTANT_TOLERANCE = 1e-9


def _result(status, reason):
    return {"protocol": PROTOCOL, "semantics_protocol": SEMANTICS_PROTOCOL,
            "status": status, "reason": reason, "diagnostic_only": True,
            "formal_score_modified": False, "mechanism_certified": False,
            "cell_counts": None, "original_metrics_recomputed": None,
            "direct_control_metrics": None, "residual_metrics": None,
            "residual_minus_original_exponential_score": None,
            "channel_residual_metrics": None}


def _number(value):
    if isinstance(value, bool) or not isinstance(value, numbers.Real):
        raise ValueError("invalid numeric cell")
    try:
        value = float(value)
    except (ValueError, OverflowError):
        raise ValueError("invalid numeric cell") from None
    if not math.isfinite(value) or abs(value) > 1e12:
        raise ValueError("invalid numeric cell")
    return value


def _matrix(value, rows, columns):
    if not isinstance(value, (list, tuple)) or len(value) != rows:
        raise ValueError("invalid matrix shape")
    matrix = []
    for row in value:
        if not isinstance(row, (list, tuple)) or len(row) != columns:
            raise ValueError("invalid matrix shape")
        matrix.append([_number(cell) for cell in row])
    return matrix


def _metrics(errors):
    if not errors:
        return None
    rmse = math.sqrt(math.fsum(error * error for error in errors) / len(errors))
    return {"cells": len(errors), "normalized_rmse": rmse,
            "exponential_score": 100.0 * math.exp(-rmse / ERROR_SCALE)}


def diagnose_panel(environment, world_version, panel, *, prediction_record=None):
    """Diagnose one private runner panel, optionally using its baseline record.

    ``panel`` supplies spec and clean_truth. By default it also supplies the
    stored prediction_values. For a baseline, pass the corresponding record from
    baseline_panels as prediction_record; its index must match panel.index.
    No value is reconstructed from a score, RMSE, source program or baseline.
    Return status/reason rather than treating unavailable/invalid data as zero.
    """
    result = _result("unknown", "not_computed")
    if not isinstance(panel, dict) or (prediction_record is not None and not isinstance(prediction_record, dict)):
        return _result("invalid", "invalid_panel_record")
    prediction = panel if prediction_record is None else prediction_record
    if prediction.get("valid") is False:
        return _result("invalid", "recorded_prediction_invalid")
    if "valid" in prediction and type(prediction["valid"]) is not bool:
        return _result("invalid", "invalid_prediction_validity_flag")
    if prediction_record is not None and (type(panel.get("index")) is not int or
                                           type(prediction.get("index")) is not int or
                                           prediction["index"] != panel["index"]):
        return _result("invalid", "prediction_record_index_mismatch")
    if not isinstance(environment, str) or not isinstance(world_version, str):
        return _result("unknown", "missing_or_invalid_environment_version")
    if environment not in _SCALES:
        return _result("unknown", "unsupported_environment")
    rule = SUPPORTED[environment]
    if world_version != rule["version"]:
        return _result("unknown", "unsupported_world_version")
    if "spec" not in panel or "clean_truth" not in panel:
        return _result("unknown", "missing_public_spec_or_clean_target")
    truth = panel["clean_truth"]
    if not isinstance(truth, dict):
        return _result("invalid", "invalid_clean_target_record")
    if not {"axis", "channels", "values"}.issubset(truth):
        return _result("unknown", "missing_clean_target_fields")
    if not isinstance(truth["channels"], (list, tuple)) or tuple(truth["channels"]) != rule["channels"]:
        return _result("invalid", "channel_contract_mismatch")
    try:
        classification = classify_cells(environment, panel["spec"], truth["channels"], rule["axis"], world_version=world_version)
        counts = summarize_cells(classification)
        if (not isinstance(truth["axis"], (list, tuple)) or
                [_number(value) for value in truth["axis"]] != classification["axis"]):
            return _result("invalid", "clean_target_axis_mismatch")
    except (ValueError, TypeError, KeyError, OverflowError):
        return _result("invalid", "invalid_public_spec_or_axis")
    result["cell_counts"] = {
        "all_cells": counts["all_cells"], "legacy_scored_rows": counts["scored_rows"],
        "legacy_scored_cells": counts["scored_cells"], "excluded_initial_cells": counts["excluded_initial_cells"],
        "direct_control_cells": counts["directly_known_scored_cells"], "residual_cells": counts["unknown_scored_cells"],
        "direct_fraction_of_legacy_cells": counts["direct_fraction_scored_cells"]}
    if "prediction_values" not in prediction or prediction["prediction_values"] is None:
        result.update(status="unknown", reason="missing_prediction_values")
        return result
    rows, columns = len(classification["axis"]), len(rule["channels"])
    try:
        predicted = _matrix(prediction["prediction_values"], rows, columns)
    except (ValueError, TypeError, OverflowError):
        result.update(status="invalid", reason="invalid_prediction_matrix")
        return result
    try:
        target = _matrix(truth["values"], rows, columns)
    except (ValueError, TypeError, OverflowError):
        result.update(status="invalid", reason="invalid_clean_target_matrix")
        return result
    scales = _SCALES[environment]
    # This check cannot change the mask: the mask was already fixed by the public
    # spec. It rejects observable contradictions with clean constants instead
    # of silently treating them as outcomes of the certified instrument.
    for row in range(rows):
        for column, scale in enumerate(scales):
            known = classification["known_values"][row][column]
            if known is not None and abs(target[row][column] - known) > _CLEAN_CONSTANT_TOLERANCE * scale:
                result.update(status="invalid", reason="clean_target_conflicts_with_public_control")
                return result
    original, direct, residual = [], [], []
    per_channel = [[] for _ in range(columns)]
    for row in counts["scored_row_indices"]:
        for column, scale in enumerate(scales):
            error = (predicted[row][column] - target[row][column]) / scale
            original.append(error)
            if classification["known_mask"][row][column]:
                direct.append(error)
            else:
                residual.append(error)
                per_channel[column].append(error)
    result["original_metrics_recomputed"] = _metrics(original)
    result["direct_control_metrics"] = _metrics(direct)
    result["channel_residual_metrics"] = [
        {"channel": channel, "cells": len(errors), "normalized_rmse": _metrics(errors)["normalized_rmse"] if errors else None}
        for channel, errors in zip(rule["channels"], per_channel)]
    if not residual:
        result.update(status="no_scientific_cells", reason="all_legacy_cells_publicly_assigned")
        return result
    result.update(status="ok", reason="computed_on_cells_not_directly_assigned")
    result["residual_metrics"] = _metrics(residual)
    result["residual_minus_original_exponential_score"] = (
        result["residual_metrics"]["exponential_score"] - result["original_metrics_recomputed"]["exponential_score"])
    return result


def diagnose_report(report):
    """Read candidate and baseline matrices from a private runner report.

    This pure transformation preserves all panel attempts and reports status
    counts. It produces no aggregate replacement score and performs no reruns.
    Baselines are matched by panel kind and index, not by list position.
    """
    if not isinstance(report, dict) or not isinstance(report.get("panels"), dict):
        return {"protocol": PROTOCOL, "status": "invalid", "reason": "invalid_report", "formal_score_modified": False}
    baseline_panels = report.get("baseline_panels", {})
    if not isinstance(baseline_panels, dict):
        return {"protocol": PROTOCOL, "status": "invalid", "reason": "invalid_baseline_catalog", "formal_score_modified": False}
    if set(baseline_panels) - set(report["panels"]):
        return {"protocol": PROTOCOL, "status": "invalid", "reason": "unmatched_baseline_panel_kind", "formal_score_modified": False}
    output = {"protocol": PROTOCOL, "status": "completed", "diagnostic_only": True,
              "formal_score_modified": False, "aggregate_replacement_score": None,
              "episode_id": report.get("episode_id"), "environment": report.get("environment"),
              "world_version": report.get("world_version"), "panels": {}, "baseline_panels": {}}
    for kind, panels in report["panels"].items():
        baselines = baseline_panels.get(kind, [])
        for entries in (panels, baselines):
            if (not isinstance(entries, list) or len(entries) > 128 or
                    any(not isinstance(entry, dict) or type(entry.get("index")) is not int or entry["index"] < 0 for entry in entries) or
                    len({entry["index"] for entry in entries}) != len(entries)):
                return {"protocol": PROTOCOL, "status": "invalid", "reason": "invalid_or_duplicate_panel_index", "formal_score_modified": False}
        baseline_by_index = {entry["index"]: entry for entry in baselines}
        if set(baseline_by_index) - {entry["index"] for entry in panels}:
            return {"protocol": PROTOCOL, "status": "invalid", "reason": "unmatched_baseline_index", "formal_score_modified": False}
        output["panels"][kind], output["baseline_panels"][kind] = [], []
        for panel in panels:
            arguments = (report.get("environment"), report.get("world_version"), panel)
            candidate = diagnose_panel(*arguments)
            baseline = diagnose_panel(*arguments, prediction_record=baseline_by_index.get(panel["index"], {"index": panel["index"]}))
            output["panels"][kind].append(dict(candidate, index=panel["index"]))
            output["baseline_panels"][kind].append(dict(baseline, index=panel["index"]))
    output["status_counts"] = {catalog: dict(Counter(item["status"] for entries in output[catalog].values() for item in entries))
                               for catalog in ("panels", "baseline_panels")}
    return output
