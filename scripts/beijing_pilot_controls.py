"""Fixed descriptive controls for the Beijing observation pilot, without GT.

Both policies implement ``solve(context, act)`` and return a dossier for the
trusted EvidenceEpisodeSession to freeze and evaluate. They receive no bundle
path or environment handle. These are pipeline/predictability controls, not
reference scientific answers or a discovery capability score.

The pooled policy deliberately omits seasonal adjustment. Its numeric tolerance
is a heuristic fixed here before running the pilot, not a confidence interval.
Weekly aggregation does not establish independent observations, and the tool's
IID standard errors are never used. Independent scientific review remains open.
"""
import math


CONTROL_VERSION = "beijing-descriptive-controls-v1"
TOLERANCE_FLOOR = 10.0  # PM concentration units: micrograms per cubic metre.
RELATIVE_TOLERANCE = 0.5
PERSISTENCE_ID = "pooled_contrast_persists"
NEAR_ZERO_ID = "pooled_contrast_near_zero"
REPLICATION_ID = "sealed_pooled_contrast"

LIMITATIONS = (
    "Fixed strategy control of pipeline behavior and descriptive predictability; not a scientific reference answer.",
    "Only the pooled difference in weekly mean PM between SE-dominated and NW-dominated weeks is tested; mixed weeks are excluded.",
    "No seasonal adjustment, confounding control, causal identification, or claim of novelty is supplied.",
    "Replication uses a held-out period from the same source; temporal dependence and collection dependence remain unresolved.",
    "Prediction intervals are heuristic tolerances, not confidence intervals or calibrated uncertainty; tool IID standard errors are ignored.",
    "Scientific meaning, uncertainty adequacy, independence and generalization require independent review and remain unassessed.",
)


def _arguments(partition):
    return {"partition": partition, "column": "pm_mean", "statistic": "mean_difference",
            "group_column": "wind_regime", "group_values": [0, 1]}


def _act(act, request):
    result = act(request)
    if not isinstance(result, dict) or not result.get("ok"):
        raise ValueError("fixed control broker action failed")
    return result


def _no_finding(reason):
    return {"claims": [], "replication_tests": [],
            "limitations": list(LIMITATIONS) + [reason]}


def null_discovery(context, act):
    """Make no query and assert no finding; absence of claims is not failure."""
    return _no_finding("Null control: no measurements requested and no discovery asserted.")


def fixed_pooled(context, act):
    """Read one exploration contrast, then freeze a held-out predictive check.

    Precommitted algorithm: predict exploration contrast +/- max(10, |d|/2),
    competing with a near-zero contrast in [-10, 10]. Overlap is allowed and
    cannot earn discriminating support. Insufficient group samples produce a
    lawful no-finding dossier, without inventing a numerical prediction.
    """
    columns = context["problem"]["data_binding"]["columns"]
    if not {"pm_mean", "wind_regime"} <= {column["name"] for column in columns}:
        raise ValueError("Beijing pooled control requires pm_mean and wind_regime")
    response = _act(act, {"action": "experiment", "tool": "summarize",
                          "arguments": _arguments("exploration")})
    observation = response["observation"]
    if observation.get("status") == "insufficient_samples":
        return _no_finding(
            "Inconclusive: fewer than two exploration weeks in a compared wind group; "
            "no replication prediction is made. This is measurement availability, not a model capability failure.")
    contrast = observation.get("value")
    if (observation.get("status") != "observed" or isinstance(contrast, bool)
            or not isinstance(contrast, (int, float)) or not math.isfinite(contrast)):
        raise ValueError("invalid exploration contrast from broker")

    tolerance = max(TOLERANCE_FLOOR, abs(contrast) * RELATIVE_TOLERANCE)
    persistence = [contrast - tolerance, contrast + tolerance]
    near_zero = [-TOLERANCE_FLOOR, TOLERANCE_FLOOR]
    disjoint = persistence[1] < near_zero[0] or near_zero[1] < persistence[0]
    assumptions = [
        "Wind regime codes identify NW=0, SE=1, mixed=2 under the frozen weekly aggregation rule.",
        "PM concentration and weekly aggregation definitions are comparable across the two periods.",
        "The pooled contrast may change with season composition, measurement changes, confounding or temporal nonstationarity.",
    ]
    rationale = (
        "Exploration observation {} is descriptive only and selected the numeric persistence prediction; "
        "it provides no prospective support. The fixed tolerance rule is max(10, abs(contrast)*0.5), "
        "in concentration units and without a coverage interpretation."
    ).format(response["evidence_id"])
    descriptions = (
        (PERSISTENCE_ID,
         "The held-out pooled SE-minus-NW weekly PM contrast lies in the exploration-centered heuristic tolerance.",
         "The held-out contrast is near zero, or changes outside both stated tolerances."),
        (NEAR_ZERO_ID,
         "The held-out pooled SE-minus-NW weekly PM contrast lies between -10 and 10 micrograms per cubic metre.",
         "The descriptive exploration contrast persists, or changes outside both stated tolerances."),
    )
    for identifier, statement, alternative in descriptions:
        _act(act, {"action": "hypothesize", "hypothesis": {
            "id": identifier, "statement": statement, "rationale": rationale,
            "assumptions": list(assumptions), "alternatives": [alternative],
        }})
    _act(act, {"action": "plan_test", "test": {
        "id": REPLICATION_ID, "phase": "replication", "tool": "summarize",
        "arguments": _arguments("replication"),
        "rationale": "One frozen held-out descriptive contrast checks temporal predictability; overlapping predictions are inconclusive.",
        "measurement": {"path": ["value"], "reducer": "scalar"},
        "predictions": [
            {"hypothesis_id": PERSISTENCE_ID, "interval": persistence,
             "falsifiers": [near_zero] if disjoint else []},
            {"hypothesis_id": NEAR_ZERO_ID, "interval": near_zero,
             "falsifiers": [persistence] if disjoint else []},
        ],
    }})
    # No replication value exists at this point. Preserve the honest pre-test
    # verdict; the runtime separately reports post-test compatibility, which
    # can differ from this frozen inconclusive verdict without being an error.
    return {
        "claims": [{"hypothesis_id": identifier, "conclusion": "inconclusive",
                    "support": [], "counterevidence": [], "tests": [REPLICATION_ID],
                    "limitations": list(LIMITATIONS) + [
                        "Verdict frozen before held-out execution; runtime compatibility may differ from this pre-test inconclusive verdict.",
                        "Exploration evidence {} is retrospective description, not a support citation.".format(response["evidence_id"]),
                    ]} for identifier, _statement, _alternative in descriptions],
        "replication_tests": [REPLICATION_ID], "limitations": list(LIMITATIONS),
    }


EVIDENCE_POLICIES = {"fixed_pooled": fixed_pooled, "null": null_discovery}

# The standalone --program entry point runs the pooled control. Operators can
# select EVIDENCE_POLICIES['null'] when executing the second fixed control.
solve = fixed_pooled
