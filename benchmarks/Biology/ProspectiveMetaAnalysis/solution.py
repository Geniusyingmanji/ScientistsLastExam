"""Valid weak baseline: abstain without selecting or running a new study."""


def synthesize_evidence(problem, confirm):
    del problem, confirm
    return {
        "confirmation_commit": None,
        "postconfirmation": {
            "intercept": 0.0,
            "moderator_slope": 0.0,
            "tau": 0.0,
            "confidence": 1.0,
            "abstain": True,
            "claim_beneficial": False,
        },
    }
