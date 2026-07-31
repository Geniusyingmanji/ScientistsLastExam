"""Weak valid baseline: standard damped mixing-length closure."""


def calibrate_rans():
    return {
        "kappa": 0.41,
        "A_plus": 26.0,
        "outer_linear": 0.0,
        "outer_quadratic": 0.0,
    }
