"""Small interface example for --program, not a strong scientific baseline.

The host runs this only through the existing Linux CandidateProxy sandbox.
It learns a numeric contrast from public measurements, freezes a prediction,
and interprets the fresh results. It has no imports or private-world access.
"""


def solve(description, act):
    counter = 0

    def call(operation, arguments):
        nonlocal counter
        counter += 1
        response = act({"request_id": "candidate-%d" % counter, "operation": operation, "arguments": arguments})
        if not response["ok"]:
            raise ValueError(response["error"])
        return response

    initial = {"biomass": {"A": .06, "B": .04, "C": .06}, "nutrient": 4,
               "volume_ml": 10, "temperature_c": 30}
    control = call("create", initial)["observation"]["vessel_id"]
    treatment = call("create", initial)["observation"]["vessel_id"]
    call("advance", {"hours": 16})
    call("feed", {"vessel_id": treatment, "amount_mmol": .02})
    call("advance", {"hours": 8})
    observations = [call("measure", {"vessel_id": vessel, "instrument": "counts"})["observation"]
                    for vessel in (control, treatment)]
    effect = observations[1]["values"]["A"] - observations[0]["values"]["A"]
    claim = {"id": "nutrient-pulse-effect", "statement": "Predict the A biomass difference after a nutrient pulse.",
             "initial": initial, "control": [],
             "treatment": [{"at_h": 16, "operation": "feed", "arguments": {"amount_mmol": .02}}],
             "readout": {"species": "A", "time_h": 24}, "expected_difference": [effect - .03, effect + .03],
             "replicates": 8, "evidence_ids": [o["observation_id"] for o in observations]}
    result = call("commit", {"claims": [claim]})
    status = result["verification"]["results"][0]["status"]
    call("interpret", {"claim_sha256": result["claim_sha256"],
                       "text": "Fresh measurement result: " + status + ". This checks the stated numerical contrast only; the causal mechanism and generalization remain unresolved."})
