"""Recover the rule generating an integer sequence, and know when the terms do not fix it.

The problem. Given the first terms of a sequence, state the linear recurrence that produced it.
This is the everyday inference behind sequence identification, and it has a sharp version of the
issue every discovery task faces: a finite prefix never determines an infinite object. A prefix of
length L is consistent with every recurrence of order greater than L/2, so the honest answer
depends on how many terms you were shown.

The oracle is SymPy, used to verify a proposed recurrence exactly over the integers and to solve
for the unique minimal recurrence a prefix admits. Exact arithmetic matters here: a
floating-point fit to an integer recurrence silently accepts wrong coefficients.

Three axes, reported separately and never averaged:

    mechanism   the proposed recurrence reproduces the held-out continuation exactly
    fdr         a recurrence claimed for a sequence that admits none of the searched order
    refusal     some prefixes are too short to determine a unique minimal recurrence: at least two
                distinct rules of the same order fit every term shown and disagree afterwards.
                The honest answer is to decline rather than to pick one.
"""

from __future__ import annotations

import math
import random

DIFFICULTY = 1

# Difficulty is the order of the recurrence and how many terms are shown relative to what pinning
# it needs. A prefix comfortably longer than twice the order is a linear solve; a prefix barely
# long enough is where the identification question bites.
_LADDER = {
    1: {"order": (2, 3), "shown": 12, "coeff": 4, "horizon": 6, "count": 5, "seed": 20260812},
    2: {"order": (3, 4), "shown": 12, "coeff": 5, "horizon": 6, "count": 5, "seed": 20260813},
    3: {"order": (4, 5), "shown": 13, "coeff": 6, "horizon": 6, "count": 5, "seed": 20260814},
}

_SEALED_LADDER = {
    1: {"order": (2, 3), "shown": 11, "coeff": 4, "horizon": 6, "count": 3, "seed": 993101},
    2: {"order": (3, 4), "shown": 12, "coeff": 5, "horizon": 6, "count": 3, "seed": 993102},
    3: {"order": (4, 5), "shown": 12, "coeff": 6, "horizon": 6, "count": 3, "seed": 993103},
}

# Orders the evaluator itself searches when deciding whether a sequence admits any rule and
# whether that rule is unique. A claim of higher order than this is out of scope, not wrong.
MAX_SEARCH_ORDER = 6

_CACHE: dict = {}


def _sympy():
    import sympy

    return sympy


def _profile(ladder, level):
    level = int(level)
    if level not in ladder:
        raise ValueError(
            "difficulty %d has no entry; measure its anchor before adding one" % level
        )
    return ladder[level]


def _extend(seed_terms, coefficients, count):
    """a[n] = sum_k c[k] * a[n-1-k], over the integers."""
    terms = list(seed_terms)
    order = len(coefficients)
    for _ in range(count):
        terms.append(sum(coefficients[k] * terms[-1 - k] for k in range(order)))
    return terms


def _fits(terms, coefficients):
    order = len(coefficients)
    if len(terms) <= order:
        return False
    for n in range(order, len(terms)):
        if terms[n] != sum(coefficients[k] * terms[n - 1 - k] for k in range(order)):
            return False
    return True


def _solve_recurrences(sympy, terms, order):
    """Every integer recurrence of exactly this order consistent with the terms.

    Decided by rank rather than by catching exceptions. A first version called
    `gauss_jordan_solve(b, freevar=True)`, which returns three values in this SymPy release; the
    two-value unpacking raised, a broad `except` swallowed it, and every order was reported as
    impossible - so the generator accepted zero worlds out of 900 draws while looking like it had
    simply been unlucky. Ranks make the three cases explicit:

        rank([A|b]) > rank(A)   inconsistent - no rule of this order
        rank(A) < order         underdetermined - the prefix does not pin one
        otherwise               a unique solution, integer or not
    """
    if len(terms) < 2 * order:
        return None  # underdetermined by construction; caller treats this as "cannot decide"
    rows = [[terms[n - 1 - k] for k in range(order)] for n in range(order, len(terms))]
    rhs = [terms[n] for n in range(order, len(terms))]
    A = sympy.Matrix(rows)
    b = sympy.Matrix(rhs)
    augmented = A.row_join(b)
    if augmented.rank() > A.rank():
        return []
    if A.rank() < order:
        return None
    solution = A.solve_least_squares(b) if A.rows != A.cols else A.solve(b)
    coefficients = [sympy.nsimplify(v) for v in solution]
    if not all(getattr(c, "is_Integer", False) for c in coefficients):
        return []
    values = [int(c) for c in coefficients]
    return [values] if _fits(terms, values) else []


def _minimal_rule(sympy, terms):
    """(order, coefficients) of the lowest-order rule fitting the terms, or a marker.

    Returns ("unique", order, coeffs), ("ambiguous", order, None) when the lowest order that fits
    is not pinned by the prefix, or ("none", None, None).
    """
    for order in range(1, MAX_SEARCH_ORDER + 1):
        found = _solve_recurrences(sympy, terms, order)
        if found is None:
            return ("ambiguous", order, None)
        if found:
            return ("unique", order, found[0])
    return ("none", None, None)


def _draw_world(rng, profile):
    order = rng.randint(*profile["order"])
    coefficients = [rng.randint(-profile["coeff"], profile["coeff"]) for _ in range(order)]
    while coefficients[-1] == 0:  # a zero trailing coefficient is really a lower-order rule
        coefficients[-1] = rng.randint(-profile["coeff"], profile["coeff"])
    seed_terms = [rng.randint(-6, 9) for _ in range(order)]
    return order, coefficients, seed_terms


def _generate(profile, tag):
    key = "worlds::%s::%s" % (tag, sorted(profile.items()))
    if key in _CACHE:
        return _CACHE[key]
    sympy = _sympy()
    rng = random.Random(profile["seed"])
    worlds = []
    attempts = 0
    while len(worlds) < profile["count"] and attempts < 900:
        attempts += 1
        order, coefficients, seed_terms = _draw_world(rng, profile)
        full = _extend(seed_terms, coefficients,
                       profile["shown"] + profile["horizon"] - order)
        shown = full[: profile["shown"]]
        if any(abs(v) > 10 ** 12 for v in full):
            continue  # runaway growth makes the terms unreadable rather than harder
        status, found_order, found = _minimal_rule(sympy, shown)
        # Every third world is deliberately under-determined by truncating the prefix so the
        # minimal rule is not pinned. The others must be uniquely determined.
        want_ambiguous = len(worlds) % 3 == 2
        if want_ambiguous:
            short = shown[: 2 * order - 1]
            st, _o, _c = _minimal_rule(sympy, short)
            if st != "ambiguous":
                continue
            shown = short
            status = "ambiguous"
        elif status != "unique":
            continue
        worlds.append({
            "key": "q%d_o%d%s" % (len(worlds), order, "_amb" if want_ambiguous else ""),
            "order": order,
            "coefficients": coefficients,
            "shown": shown,
            "continuation": full[len(shown): len(shown) + profile["horizon"]],
            "ambiguous": want_ambiguous,
            "status": status,
        })
    if len(worlds) < profile["count"]:
        raise ValueError(
            "only %d of %d sequences met the determinacy quota in %d draws"
            % (len(worlds), profile["count"], attempts)
        )
    _CACHE[key] = tuple(worlds)
    return _CACHE[key]


def development_worlds():
    return _generate(_profile(_LADDER, DIFFICULTY), "dev")


def sealed_worlds():
    return _generate(_profile(_SEALED_LADDER, DIFFICULTY), "sealed")


def _observation(world):
    return {
        "terms": list(world["shown"]),
        "horizon": len(world["continuation"]),
        "max_order": MAX_SEARCH_ORDER,
    }


def _parse(submission):
    if not isinstance(submission, dict):
        return None, "expected a dict, got %s" % type(submission).__name__
    if submission.get("abstain"):
        return {"abstain": True}, ""
    coefficients = submission.get("coefficients")
    if coefficients is None:
        return None, "missing 'coefficients' (or set 'abstain': True)"
    try:
        values = [int(c) for c in coefficients]
    except (TypeError, ValueError):
        return None, "coefficients must be integers"
    if not values:
        return None, "coefficients must be non-empty"
    if len(values) > MAX_SEARCH_ORDER:
        return None, "order %d exceeds the searched maximum %d" % (len(values), MAX_SEARCH_ORDER)
    if any(not math.isfinite(float(c)) for c in values):
        return None, "non-finite coefficient"
    return {"abstain": False, "coefficients": values}, ""


def _score_world(world, parsed):
    """A rule is right when it reproduces the held-out continuation exactly, not when it fits."""
    coefficients = parsed["coefficients"]
    fits_shown = _fits(world["shown"], coefficients)
    predicted = _extend(world["shown"][-len(coefficients):], coefficients,
                        len(world["continuation"]))[len(coefficients):]
    correct = predicted == world["continuation"]
    return {
        "mechanism": 1.0 if correct else 0.0,
        "fits_shown_terms": fits_shown,
        "predicts_continuation": correct,
        "claimed_order": len(coefficients),
        "true_order": world["order"],
        # A claim is a false discovery when it fits everything shown and still gets the
        # continuation wrong: the sequence did not admit that rule, the prefix merely allowed it.
        "false_claim": bool(fits_shown and not correct),
    }


def _score_split(recover, worlds):
    rows = []
    for world in worlds:
        try:
            raw = recover(_observation(world))
        except Exception as exc:  # noqa: BLE001 - candidate faults are scored, not raised
            rows.append({"key": world["key"], "valid": False,
                         "reason": "raised: %s" % type(exc).__name__})
            continue
        parsed, why = _parse(raw)
        if parsed is None:
            rows.append({"key": world["key"], "valid": False, "reason": why})
            continue
        determined = not world["ambiguous"]
        if parsed["abstain"]:
            rows.append({"key": world["key"], "valid": True, "abstained": True,
                         "determined": determined, "mechanism": 0.0,
                         "correct_refusal": not determined})
            continue
        metrics = _score_world(world, parsed)
        metrics.update({"key": world["key"], "valid": True, "abstained": False,
                        "determined": determined, "correct_refusal": False})
        rows.append(metrics)

    valid = [r for r in rows if r["valid"]]
    determined = [r for r in valid if r["determined"]]
    undetermined = [r for r in valid if not r["determined"]]
    claims = [r for r in valid if not r.get("abstained")]
    return {
        "rows": rows,
        "valid_count": len(valid),
        "world_count": len(worlds),
        "mechanism": (sum(r["mechanism"] for r in determined) / len(determined)
                      if determined else 0.0),
        "false_discovery_rate": (sum(1 for r in claims if r.get("false_claim")) / len(claims)
                                 if claims else None),
        "correct_refusal_rate": ((sum(1 for r in undetermined if r["correct_refusal"])
                                  / len(undetermined)) if undetermined else None),
        "unwarranted_refusal_rate": (
            sum(1 for r in determined if r.get("abstained")) / len(determined)
            if determined else 0.0),
    }


def evaluate(recover_law) -> dict:
    development = _score_split(recover_law, development_worlds())
    valid = development["valid_count"] == development["world_count"]
    result = {
        "combined_score": float(development["mechanism"]) if valid else 0.0,
        "valid": 1.0 if valid else 0.0,
        "development_mechanism_score": development["mechanism"],
        "development_false_discovery_rate": development["false_discovery_rate"],
        "development_correct_refusal_rate": development["correct_refusal_rate"],
        "development_unwarranted_refusal_rate": development["unwarranted_refusal_rate"],
        "per_instance": development["rows"],
        "difficulty": DIFFICULTY,
    }
    if valid:
        sealed = _score_split(recover_law, sealed_worlds())
        result.update({
            "robustness_score": float(sealed["mechanism"]),
            "heldout_mechanism_score": sealed["mechanism"],
            "heldout_false_discovery_rate": sealed["false_discovery_rate"],
            "heldout_correct_refusal_rate": sealed["correct_refusal_rate"],
            "sealed_per_instance": sealed["rows"],
        })
    else:
        result["robustness_score"] = 0.0
    return result
