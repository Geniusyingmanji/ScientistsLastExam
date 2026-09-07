"""Weak legal baseline for active occupancy inference."""


def infer_occupancy(problem, survey):
    evidence = []
    for site in problem["site_descriptors"][:4]:
        row = survey(site["site_id"], "rapid")
        evidence.append(row["query_id"])
    return {
        "effect": "positive",
        "habitat_effect": 1.0,
        "mean_occupancy": 0.5,
        "confidence": 0.5,
        "evidence_query_ids": evidence,
        "abstain": False,
    }
