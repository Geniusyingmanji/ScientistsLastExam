"""Weak feasible integer assignments. Returning them scores zero."""

BASELINES = {
    "gen-ip002": [0] * 41,
    "gen-ip021": [
        8, 4, 2, 1, 8, 2, 7, 0, 7, 7, 5, 8, 5, 2, 0, 8, 3, 4, 1, 7, 4, 0, 4, 8, 0,
        6, 1, 1, 5, 7, 1, 7, 8, 5, 0,
    ],
    "gen-ip054": [
        1, 0, 3, 3, 2, 2, 1, 1, 1, 1, 0, 2, 0, 3, 2, 1, 1, 2, 1, 3, 0, 3, 0, 3, 2,
        2, 2, 1, 1, 3,
    ],
}


def improve_primal(problem):
    """Return one dense integer assignment in frozen MPS column order."""
    return list(BASELINES[problem["name"]])
