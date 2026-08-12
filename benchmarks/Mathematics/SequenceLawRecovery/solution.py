"""Baseline: guess the Fibonacci rule.

a[n] = a[n-1] + a[n-2], regardless of what the terms actually do. Valid by construction and
deliberately trivial - it is a guess, not a method.

An earlier baseline fitted order two from the last four terms and scored level with the shipped
reference, which made it a competitor rather than a floor.
"""


def recover_law(observation):
    return {"coefficients": [1, 1]}
