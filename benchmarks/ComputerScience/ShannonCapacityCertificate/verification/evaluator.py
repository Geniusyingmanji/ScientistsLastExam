"""Hidden oracle for ShannonCapacityCertificate.

Shannon asked in 1956 for the zero-error capacity of the five-cycle. Lovasz answered it in 1979
with ``theta``, and the same question for the seven-cycle has been open ever since. What is known
is an interval. From below, every independent set in a strong product power ``C_n^{box k}`` is a
zero-error code and proves ``Theta(C_n) >= alpha(C_n^{box k})^{1/k}``; from above, ``theta`` is
multiplicative and proves ``Theta(C_n) <= theta(C_n)``. For the seven-cycle that interval is still
about ``[3.2588, 3.3177]`` after seventy years, and it moved three times in July 2026 alone.

This task scores the interval a submission can *certify*, not the interval it can quote.

Both sides are checked as proofs, exactly, with no tolerance and no trust:

* The lower side is a set of codewords. Verification is a membership test - for every codeword,
  none of its ``3^k - 1`` shifts by ``{0, +1, -1}`` may also be a codeword - so a submitted set is
  either a zero-error code or it is not, and the oracle's work is ``|S| * 3^k`` dictionary lookups.
  Nothing about how the set was found matters.

* The upper side is a rational matrix. For any symmetric ``A`` with ones on the diagonal and ones
  at every non-adjacent pair, ``lambda_max(A) >= theta(G) >= Theta(G)``; a rational ``b`` with
  ``b*I - A`` positive definite therefore proves ``Theta(G) <= b``. Positive definiteness is
  decided by exact rational elimination. That decision is affordable *here*, unlike in the
  sum-of-squares setting, for one reason: the matrix is ``n x n`` with ``n`` fixed by the instance
  at 7, 11 or 13, so the cost is bounded by the instance rather than by anything the candidate
  chooses. A float is not a certificate and is rejected rather than rounded.

The zero of the scale is the free bound: what the product construction over the small powers
shipped in ``references/`` already gives, per instance, with the witnessing set. One is the best
published lower bound on the capacity as of the retrieval date in ``references/anchors.json`` -
reached in the literature only through constructions at power 10 and beyond, while this task caps
the power at 5. The scale is uncapped above, because an independent set larger than the published
record at a power this task allows would be a result rather than a full mark.
"""
from __future__ import annotations

import math
from fractions import Fraction
from itertools import product


DIFFICULTY = 1

# --- the rules, inlined ------------------------------------------------------------------------
#
# verification/graphs.py states these same rules in readable form. The copy lives here because the
# trusted driver loads this file by path and not as a package, so `from graphs import ...` resolves
# against the harness's sys.path rather than this directory: it raises ModuleNotFoundError inside
# the sandbox while importing perfectly in a plain interpreter, which is the worst way for a check
# to fail. The task's tests compare the two copies.


def cycle_adjacent(n: int, i: int, j: int) -> bool:
    return (i - j) % n in (1, n - 1)


def strong_power_shifts(n: int, power: int):
    return [shift for shift in product((0, 1, n - 1), repeat=power) if any(shift)]


def independence_failure(n: int, power: int, vertices):
    """Return a colliding pair, or None when the set is independent in C_n^{box power}."""
    members = set(vertices)
    for shift in strong_power_shifts(n, power):
        for vertex in members:
            moved = tuple((vertex[i] + shift[i]) % n for i in range(power))
            if moved in members:
                return (vertex, moved)
    return None


def is_positive_definite(matrix) -> bool:
    """Exact rational LDL^T without pivoting; positive definite iff every pivot is positive."""
    size = len(matrix)
    work = [list(row) for row in matrix]
    for k in range(size):
        pivot = work[k][k]
        if pivot <= 0:
            return False
        for i in range(k + 1, size):
            factor = work[i][k] / pivot
            if factor:
                for j in range(k, size):
                    work[i][j] -= factor * work[k][j]
            work[i][k] = Fraction(0)
    return True


# --- submission limits -------------------------------------------------------------------------

MAX_CODEWORDS = 4000
MAX_LOWER_CERTIFICATES = 8
MAX_NUMERATOR = 10 ** 9
MAX_DENOMINATOR = 10 ** 6


def _fraction(value):
    """Accept an integer or an exact [numerator, denominator] pair. Never a float."""
    if isinstance(value, bool):
        raise ValueError("boolean is not a matrix entry")
    if isinstance(value, int):
        number = Fraction(value)
    elif isinstance(value, (list, tuple)) and len(value) == 2:
        numerator, denominator = value
        for part in (numerator, denominator):
            if isinstance(part, bool) or not isinstance(part, int):
                raise ValueError("rational parts must be integers")
        if denominator == 0:
            raise ValueError("zero denominator")
        number = Fraction(numerator, denominator)
    else:
        # A float is rejected on purpose rather than converted: a numerical eigenvalue is not a
        # proof, and silently rounding one would score the wrong thing.
        raise ValueError("entries must be integers or [numerator, denominator] pairs")
    if abs(number.numerator) > MAX_NUMERATOR or number.denominator > MAX_DENOMINATOR:
        raise ValueError("entry exceeds the size cap")
    return number


def _read_lower(value, instance):
    """Parse and verify the zero-error codes; return the best certified capacity bound."""
    if not isinstance(value, (list, tuple)) or not value:
        raise ValueError("'lower_certificates' must be a non-empty list")
    if len(value) > MAX_LOWER_CERTIFICATES:
        raise ValueError("more lower certificates than the cap allows")
    cycle = instance["cycle"]
    best, detail = None, None
    for entry in value:
        if not isinstance(entry, dict):
            raise ValueError("each lower certificate is a mapping")
        power = entry.get("power")
        if isinstance(power, bool) or not isinstance(power, int):
            raise ValueError("'power' must be an integer")
        if not 1 <= power <= instance["max_power"]:
            raise ValueError("power outside the instance's range")
        raw = entry.get("vertices")
        if not isinstance(raw, (list, tuple)) or not raw:
            raise ValueError("'vertices' must be a non-empty list")
        if len(raw) > MAX_CODEWORDS:
            raise ValueError("more codewords than the cap allows")
        words = []
        for word in raw:
            if not isinstance(word, (list, tuple)) or len(word) != power:
                raise ValueError("each codeword must have one coordinate per power")
            coordinates = []
            for coordinate in word:
                if isinstance(coordinate, bool) or not isinstance(coordinate, int):
                    raise ValueError("codeword coordinates must be integers")
                if not 0 <= coordinate < cycle:
                    raise ValueError("codeword coordinate outside the cycle")
                coordinates.append(coordinate)
            words.append(tuple(coordinates))
        if len(set(words)) != len(words):
            raise ValueError("codewords must be distinct")
        collision = independence_failure(cycle, power, words)
        if collision is not None:
            raise ValueError("codewords %r and %r are adjacent" % collision)
        bound = len(words) ** (1.0 / power)
        if best is None or bound > best:
            best, detail = bound, {"power": power, "size": len(words)}
    return best, detail


def _read_upper(value, instance):
    """Parse and verify the Lovasz-pattern certificate; return the bound it proves."""
    if not isinstance(value, dict):
        raise ValueError("'upper_certificate' is a mapping with 'matrix' and 'bound'")
    cycle = instance["cycle"]
    raw = value.get("matrix")
    if not isinstance(raw, (list, tuple)) or len(raw) != cycle:
        raise ValueError("'matrix' must have one row per cycle vertex")
    matrix = []
    for row in raw:
        if not isinstance(row, (list, tuple)) or len(row) != cycle:
            raise ValueError("'matrix' must be square")
        matrix.append([_fraction(entry) for entry in row])
    for i in range(cycle):
        for j in range(cycle):
            if matrix[i][j] != matrix[j][i]:
                raise ValueError("the matrix must be symmetric")
            if i == j or not cycle_adjacent(cycle, i, j):
                # The diagonal and every non-edge are forced to one. These are the entries that
                # make lambda_max an upper bound for theta; a submission that relaxes them is
                # bounding a different quantity.
                if matrix[i][j] != 1:
                    raise ValueError("forced entry at (%d, %d) is not 1" % (i, j))
    bound = _fraction(value.get("bound"))
    shifted = [[(bound if i == j else Fraction(0)) - matrix[i][j] for j in range(cycle)]
               for i in range(cycle)]
    if not is_positive_definite(shifted):
        raise ValueError("bound*I - matrix is not positive definite")
    return bound


def _instance_score(instance, lower, upper):
    """Progress in certified interval width, from the free bound to the published frontier."""
    theta = instance["theta"]
    free_width = theta - instance["free_bound"]
    target_width = theta - instance["target_bound"]
    width = float(upper) - lower
    return max(0.0, (free_width - width) / (free_width - target_width))


# --- the instances -----------------------------------------------------------------------------
#
# Anchors are published numbers, not measurements of this package, and are recorded with their
# source and retrieval date in references/anchors.json.
#
# `theta` is Lovasz's bound in closed form for the odd cycle, theta(C_n) = n*cos(pi/n)/(1+cos(pi/n))
# (Lovasz 1979, section 4). It is the top of the certified interval and the scale's reference
# point, not something a submission has to beat.
#
# `free_bound` is what the product construction over the small powers already proves, witnessed by
# the sets in references/free_sets.json: 108 codewords at power 4 for C7, and the squares of the
# two-coordinate sets for C13, C19 and C23. It is the zero of the scale.
#
# `target_bound` is the best published lower bound on the capacity as of 2026-09-06 and is worth
# exactly 1. Every one of the three was reached in the literature through constructions at power 6
# or higher - power 10 for C7, and a recursion out to power 200 - while this task caps the power at
# 5, 4 and 4. The scale is uncapped above for the same reason it is in the rest of this benchmark:
# the published number is a witness, not a ceiling.

# Every free bound is witnessed by a set shipped in references/free_sets.json, so the zero of the
# scale does not depend on a citation being right. The two-coordinate value alpha(C_n^{box 2}) =
# floor(n(n-1)/4) is classical (Hales 1973 for the strong product of two cycles) and is re-found by
# search here in seconds; squaring it gives a power-4 set, which is where the C13 zero comes
# from. C19 and C23 cap the power at 3, so their zero is the two-coordinate set itself.
C7_FREE = 108.0 ** 0.25       # 108 codewords at power 4
C13_FREE = 1521.0 ** 0.25     # 39 at power 2, squared
C19_FREE = 85.0 ** 0.5        # 85 at power 2
C23_FREE = 126.0 ** 0.5       # 126 at power 2


def _instance(name, cycle, max_power, free_bound, free_note, target_bound, target_note):
    angle = math.cos(math.pi / cycle)
    return {
        "name": name,
        "cycle": cycle,
        "max_power": max_power,
        "theta": cycle * angle / (1.0 + angle),
        "free_bound": free_bound,
        "free_note": free_note,
        "target_bound": target_bound,
        "target_note": target_note,
    }


INSTANCES = [
    _instance("C7", 7, 5, C7_FREE,
              "108 codewords at power 4 (Vesel and Zerovnik 2002)",
              3.258805369885,
              "Buys, Polak and Zuiddam 2026, arXiv:2607.29681"),
    _instance("C13", 13, 4, C13_FREE,
              "39 codewords at power 2, squared to power 4",
              6.302455083464,
              "Buys, Polak and Zuiddam 2026, arXiv:2607.29681"),
    _instance("C19", 19, 3, C19_FREE,
              "85 codewords at power 2",
              9.357192705918,
              "Buys, Polak and Zuiddam 2026, arXiv:2607.29681"),
    _instance("C23", 23, 3, C23_FREE,
              "126 codewords at power 2",
              11.328224257774,
              "Buys, Polak and Zuiddam 2026, arXiv:2607.29681"),
]


def _public_instance(instance):
    """What the candidate is told. Everything here is public; nothing is withheld.

    The score is a proof, so there is nothing to hold back: a certificate cannot be tuned to a
    grader it has not seen, it can only be correct or not.
    """
    return {
        "name": instance["name"],
        "cycle": instance["cycle"],
        "max_power": instance["max_power"],
        "lovasz_theta": instance["theta"],
        "free_bound": instance["free_bound"],
        "free_bound_note": instance["free_note"],
        "published_target_bound": instance["target_bound"],
        "published_target_note": instance["target_note"],
        "max_codewords": MAX_CODEWORDS,
        "max_lower_certificates": MAX_LOWER_CERTIFICATES,
        "max_numerator": MAX_NUMERATOR,
        "max_denominator": MAX_DENOMINATOR,
    }


def evaluate(build_certificate):
    """Score one submission. A malformed certificate scores zero; it never raises out of here."""
    rows = []
    for index, instance in enumerate(INSTANCES):
        published = {
            "instance_index": index,
            "name": instance["name"],
            "cycle": instance["cycle"],
            "max_power": instance["max_power"],
            "lovasz_theta": instance["theta"],
            "free_bound": instance["free_bound"],
            "published_target_bound": instance["target_bound"],
        }
        try:
            submission = build_certificate(_public_instance(instance))
            if not isinstance(submission, dict):
                raise ValueError("a certificate is a mapping")
            lower, detail = _read_lower(submission.get("lower_certificates"), instance)
            upper = _read_upper(submission.get("upper_certificate"), instance)
            score = _instance_score(instance, lower, upper)
            published.update({
                "valid": True,
                "certified_lower_bound": lower,
                "certified_upper_bound": float(upper),
                "certified_interval_width": float(upper) - lower,
                "best_lower_power": detail["power"],
                "best_lower_size": detail["size"],
                "instance_score": round(score, 6),
                "beats_the_free_bound": bool(lower > instance["free_bound"]),
                "beats_the_published_target": bool(lower > instance["target_bound"]),
            })
        except Exception as exc:  # noqa: BLE001 - a bad certificate scores zero, it does not crash this
            published.update({
                "valid": False,
                "reason": "%s: %s" % (type(exc).__name__, exc),
                "certified_lower_bound": None,
                "certified_upper_bound": None,
                "certified_interval_width": None,
                "best_lower_power": None,
                "best_lower_size": None,
                "instance_score": 0.0,
                "beats_the_free_bound": False,
                "beats_the_published_target": False,
            })
        rows.append(published)

    valid = [row for row in rows if row["valid"]]
    combined = sum(row["instance_score"] for row in rows) / len(rows)
    return {
        "combined_score": float(combined),
        "valid": 1.0 if valid else 0.0,
        "feasibility_rate": len(valid) / len(rows),
        "raw_score": float(combined),
        "instances_with_a_valid_certificate": len(valid),
        "instances_beating_the_free_bound": sum(1 for r in rows if r["beats_the_free_bound"]),
        "instances_beating_the_published_target": sum(
            1 for r in rows if r["beats_the_published_target"]),
        "per_instance": rows,
    }
