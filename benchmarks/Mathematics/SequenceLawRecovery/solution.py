"""Baseline: assume the sequence satisfies a second-order recurrence and fit it.

Solves for two coefficients from the last few terms. Valid by construction and deliberately weak:
it never checks whether order two actually fits, and never considers that the prefix might not
determine a rule at all.
"""


def recover_law(observation):
    terms = observation["terms"]
    if len(terms) < 4:
        return {"coefficients": [1, 0]}
    a, b, c, d = terms[-4], terms[-3], terms[-2], terms[-1]
    det = b * b - a * c
    if det == 0:
        return {"coefficients": [1, 0]}
    p = (c * b - a * d) // det if (c * b - a * d) % det == 0 else 1
    q = (b * d - c * c) // det if (b * d - c * c) % det == 0 else 0
    return {"coefficients": [p, q]}
