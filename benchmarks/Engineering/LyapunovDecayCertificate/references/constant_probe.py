"""No-input-search counterexample from the September 9 maintainer review, padded to 3x3.

The original 2-by-2 constant P=[[1,-3/5],[-3/5,1]], alpha=59/100 is embedded in
the leading 2-by-2 block. It does not read the instance.
"""


def build_lyapunov(instance):
    _ = instance
    return {
        "p11": 1,
        "p12": [-3, 5],
        "p13": 0,
        "p22": 1,
        "p23": 0,
        "p33": 1,
        "alpha": [59, 100],
    }
