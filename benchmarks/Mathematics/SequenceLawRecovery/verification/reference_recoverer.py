"""Truth-blind reference: minimal-order exact solve, tolerant of a few bad terms. Calibration only.

The procedure, in the order a careful person would try it:

1. Solve exactly at each order from one upward. Ranks decide the three cases - inconsistent, so
   no rule of this order; rank-deficient, so the prefix does not pin one; otherwise unique.
2. If no order yields a rule, the prefix may contain transcription errors. Drop one term, then
   two, and retry. A rule that explains all but a few terms is the standard reading of a table
   with typos in it.
3. Declare ambiguity only when a *clean* prefix is rank-deficient, not when a corrupted one is
   inconsistent. Conflating those was the first version's mistake: it abstained on half the
   determined worlds and scored below the trivial baseline.

Ranks rather than exception handling throughout, because `gauss_jordan_solve` returns a different
number of values across SymPy releases and a mis-unpacked call caught by a broad `except` looks
exactly like an inconsistent system.
"""

from __future__ import annotations

from itertools import combinations

MAX_ORDER = 6
MAX_DROPPED = 2


def _fits(terms, coefficients):
    order = len(coefficients)
    if len(terms) <= order:
        return False
    return all(
        terms[n] == sum(coefficients[k] * terms[n - 1 - k] for k in range(order))
        for n in range(order, len(terms))
    )


def _solve(sympy, terms, order):
    """(coefficients, status) where status is 'unique', 'ambiguous' or 'none'."""
    if len(terms) < 2 * order:
        return None, "ambiguous"
    rows = [[terms[n - 1 - k] for k in range(order)] for n in range(order, len(terms))]
    rhs = [terms[n] for n in range(order, len(terms))]
    A, b = sympy.Matrix(rows), sympy.Matrix(rhs)
    if A.row_join(b).rank() > A.rank():
        return None, "none"
    if A.rank() < order:
        return None, "ambiguous"
    solution = A.solve(b) if A.rows == A.cols else A.solve_least_squares(b)
    coefficients = [sympy.nsimplify(v) for v in solution]
    if not all(getattr(c, "is_Integer", False) for c in coefficients):
        return None, "none"
    return [int(c) for c in coefficients], "unique"


def recover_law(observation):
    import sympy

    terms = [int(t) for t in observation["terms"]]
    limit = min(MAX_ORDER, len(terms) // 2)

    ambiguous_on_clean = False
    for order in range(1, limit + 1):
        coefficients, status = _solve(sympy, terms, order)
        if status == "unique":
            return {"coefficients": coefficients}
        if status == "ambiguous":
            ambiguous_on_clean = True
            break

    # No rule fits every term. Assume a few are wrong and look for one that explains the rest.
    for dropped in range(1, MAX_DROPPED + 1):
        best = None
        for removed in combinations(range(len(terms)), dropped):
            kept = [t for i, t in enumerate(terms) if i not in removed]
            for order in range(1, min(MAX_ORDER, len(kept) // 2) + 1):
                coefficients, status = _solve(sympy, kept, order)
                if status == "unique" and _fits(kept, coefficients):
                    # Prefer the lowest order, and among those the earliest removal.
                    if best is None or order < best[0]:
                        best = (order, coefficients)
                    break
        if best is not None:
            return {"coefficients": best[1]}

    return {"abstain": True} if ambiguous_on_clean else {"abstain": True}
