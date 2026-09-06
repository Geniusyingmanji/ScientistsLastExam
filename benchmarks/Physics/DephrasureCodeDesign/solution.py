"""Trivial valid pure-state baseline: zero coherent information."""


def design_code(problem):
    d = 2**problem["n"]
    return {"real": [[1.0]] + [[0.0] for _ in range(d-1)],
            "imag": [[0.0] for _ in range(d)]}
