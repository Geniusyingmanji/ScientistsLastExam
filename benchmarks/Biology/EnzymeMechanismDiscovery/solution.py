"""Legal weak baseline for the episode pilot; no private imports."""


def discover(problem, execute):
    ranges = problem["active_parameter_ranges"]
    parameters = {key: sum(ranges[key]) / 2 for key in ("kcat", "km", "k2")}
    parameters.update(ki=None, ks=None, kd=None)
    return {"decision": "discover", "mechanism": [], "parameters": parameters, "evidence_ids": []}
