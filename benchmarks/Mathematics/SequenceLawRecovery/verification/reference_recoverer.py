"""Truth-blind reference: exact minimal-order solve with an ambiguity check. Calibration only.

Search orders from one upward. At each order the terms impose a linear system, and its ranks
decide the three cases:

    rank([A|b]) > rank(A)   inconsistent - no rule of this order
    rank(A) < order         underdetermined - the prefix does not pin one, so decline
    otherwise               a unique solution; accept it if it is integral

Ranks rather than exception handling on purpose. `gauss_jordan_solve` returns a different number
of values across SymPy releases, and a mis-unpacked call caught by a broad `except` is
indistinguishable from an inconsistent system - that exact mistake made an earlier version report
every order as impossible.

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
        if A.row_join(b).rank() > A.rank():
            continue
        if A.rank() < order:
            return {"abstain": True}
        solution = A.solve(b) if A.rows == A.cols else A.solve_least_squares(b)
        coefficients = [sympy.nsimplify(v) for v in solution]
        if all(getattr(c, "is_Integer", False) for c in coefficients):
            return {"coefficients": [int(c) for c in coefficients]}
    return {"abstain": True}
