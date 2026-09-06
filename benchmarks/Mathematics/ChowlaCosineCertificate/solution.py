"""Trivial valid baseline: n + sum cos(ax) = sum |1+z^a|^2 / 2."""


def build_certificate(problem):
    frequencies = list(range(1, problem["n_terms"] + 1))
    return {"frequencies": frequencies, "bound": [problem["n_terms"], 1],
            "factors": [{"weight": [1, 2], "terms": [[0, 1], [a, 1]]}
                        for a in frequencies]}
