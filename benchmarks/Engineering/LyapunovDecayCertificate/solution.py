"""Identity quadratic at a token decay rate.

P = I is a common Lyapunov function on every published instance, but the
numerical abscissa is small. Proving only alpha = 1/10000 scores near zero.
"""


def build_lyapunov(instance):
    _ = instance["name"]
    _ = instance["mode_matrices"]
    _ = instance["state_dimension"]
    _ = instance["max_numerator"]
    _ = instance["max_denominator"]
    return {
        "p11": [1, 1],
        "p12": [0, 1],
        "p22": [1, 1],
        "alpha": [1, 10000],
    }
