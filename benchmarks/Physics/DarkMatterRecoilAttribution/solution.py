"""Legal weak baseline: treats any recoil spectrum as a light contact candidate."""


def infer_recoil(problem, experiment):
    experiment({"target": 0, "units": 1})
    return {"model": "contact", "mass_gev": 10.0, "confidence": 0.95, "abstain": False}
