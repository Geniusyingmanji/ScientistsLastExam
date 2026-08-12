"""Truth-blind reference: exact minimal-order solve with an ambiguity check. Calibration only.

Search orders from one upward. At each order, set up the linear system the terms impose and solve
it exactly over the rationals. If the system is inconsistent, that order is impossible; if it has
a free parameter, the prefix does not pin a rule of that order and the honest answer is to
decline; if it has a unique integer solution, that is the minimal rule.

This is the same procedure the evaluator uses to decide whether a world is determined, which is
deliberate: the reference should be the method the task is built around, so that beating it means
doing something the standard approach does not.
"""

from __future__ import annotations

MAX_ORDER = 6


def recover_law(observation):
    import sympy

    terms = [int(t) for t in observation["terms"]]
    for order in range(1, min(MAX_ORDER, len(terms) // 2) + 1):
        rows = [[terms[n - 1 - k] for k in range(order)] for n in range(order, len(terms))]
        rhs = [terms[n] for n in range(order, len(terms))]
        A, b = sympy.Matrix(rows), sympy.Matrix(rhs)
        try:
            solution, params = A.gauss_jordan_solve(b, freevar=True)
        except Exception:  # noqa: BLE001 - inconsistent at this order
            continue
        if params:
            return {"abstain": True}
        coefficients = [sympy.nsimplify(v) for v in solution]
        if all(getattr(c, "is_Integer", False) for c in coefficients):
            return {"coefficients": [int(c) for c in coefficients]}
    return {"abstain": True}
