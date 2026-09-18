"""Legal no-evidence control for the episode pilot, not a certified baseline."""


def solve(problem, experiment):
    del problem, experiment
    return {"abstain": True, "confidence": 0.0}
