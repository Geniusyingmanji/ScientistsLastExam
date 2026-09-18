"""Protocol anchors over the public hand-entered fixture; not scientist baselines.

These anchors deliberately know the example actions. They establish pipeline
behavior, not discovery capability. Never use them to score a real data bundle.
"""
import copy
import json
from pathlib import Path


def _example(context):
    source = context["problem"]["data_binding"]
    if source["provenance"]["kind"] != "protocol_fixture":
        raise ValueError("protocol anchors are for the public fixture only")
    return json.loads((Path(__file__).resolve().parents[1] / "examples/discovery_actions.json").read_text())


def _execute(actions, act):
    for action in actions[:-1]:
        response = act(action)
        if not response.get("ok"):
            raise ValueError("protocol example action failed")
    return copy.deepcopy(actions[-1]["claim"])


def protocol(context, act):
    return _execute(_example(context), act)


def null_discovery(context, act):
    return {"claims": [], "replication_tests": [],
            "limitations": ["No finding is asserted and no measurement is made."]}


def fabricated_citation(context, act):
    claim = _execute(_example(context), act)
    claim["claims"][0]["support"] = ["invented-evidence-not-issued-by-the-broker"]
    return claim


def broad_predictions(context, act):
    actions = _example(context)
    for action in actions:
        if action["action"] == "plan_test":
            for prediction in action["test"]["predictions"]:
                prediction["interval"] = [-1e50, 1e50]
                prediction["falsifiers"] = []
    return _execute(actions, act)


def posthoc_retest(context, act):
    actions = _example(context)
    # Observe the fixed rows before the supposed preregistration. Requerying
    # identical data cannot turn this into a prospective test.
    first = copy.deepcopy(actions[3])
    first.pop("test_id")
    if not act(first).get("ok"):
        raise ValueError("exploration failed")
    actions = actions[:4] + [actions[-1]]
    claim = actions[-1]["claim"]
    claim["replication_tests"] = []
    claim["claims"][0]["tests"] = ["explore_difference"]
    claim["claims"][0]["support"] = ["experiment-0002"]
    return _execute(actions, act)


EVIDENCE_POLICIES = {"protocol": protocol, "null": null_discovery,
                     "fabricated_citation": fabricated_citation,
                     "broad_predictions": broad_predictions, "posthoc_retest": posthoc_retest}
