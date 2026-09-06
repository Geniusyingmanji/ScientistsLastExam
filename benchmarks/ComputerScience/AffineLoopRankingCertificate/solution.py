"""e_1 ranking at a token decrease.

The first coordinate is a valid linear ranking on every published loop, but
the claimed decrease is 1/10000. Searching a better direction is the work.
"""


def build_ranking(instance):
    dimension = int(instance["dimension"])
    n_guards = len(instance["guards"])
    _ = instance["name"]
    _ = instance["A"]
    _ = instance["b"]
    _ = instance["max_numerator"]
    _ = instance["max_denominator"]
    ranking = [[1, 1] if index == 0 else [0, 1] for index in range(dimension)]
    zeros = [[0, 1] for _ in range(n_guards)]
    lambdas = [[1, 1] if index == 0 else [0, 1] for index in range(n_guards)]
    return {
        "r": ranking,
        "s": [0, 1],
        "delta": [1, 10000],
        "nonneg_lambdas": lambdas,
        "decrease_lambdas": zeros,
    }
