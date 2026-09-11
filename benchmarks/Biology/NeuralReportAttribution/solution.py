"""Legal weak baseline: mistakes sensor propagation for strong neural feedback."""


def infer_circuit(problem, experiment):
    experiment({"kind": "response", "report": 1, "frequency": 0, "units": 1})
    return {"model": "recurrent", "feedback": 1.2, "report_feedback": 1.2,
            "confidence": .95, "abstain": False}
