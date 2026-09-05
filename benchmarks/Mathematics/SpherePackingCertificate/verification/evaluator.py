"""Hidden oracle for SpherePackingCertificate.

How densely can unit balls be packed in R^n? Solved in dimensions 1, 2, 3, 8 and 24. Open
everywhere else, and the gap is not small: in dimension 12 the best packing known reaches a centre
density of 0.03704 while the best proof stops at 0.06279, so a factor of 1.7 of the answer is
simply unknown.

Cohn and Elkies (Ann. of Math. 157 (2003), Theorem 3.1) turned the upper half of that gap into an
analytic problem. If `f : R^n -> R` satisfies

    (1) f(x) <= 0 for |x| >= 1,
    (2) fhat(y) >= 0 for all y,

then the centre density of any packing is at most `f(0) / (2^n * fhat(0))`. The theorem is a page of
Poisson summation; producing a function that makes it say something strong is the research problem,
and it is the one Viazovska solved in dimension 8.

**What is scored is the certificate, not the function.** A submission is exact and rational
throughout, and both hypotheses are verified rather than sampled.

The variable is the reason this is possible. The Fourier eigenbasis for radial functions is
`L_k^{(n/2-1)}(2*pi*|x|^2) * exp(-pi*|x|^2)` with eigenvalue `(-1)^k`, so a function written in that
basis has an exactly known transform - the same coefficients with alternating signs. Written in
`|x|^2` those polynomials carry powers of `2*pi` and nothing is rational; written in
`w = 2*pi*|x|^2` they are rational, and the support condition `|x| >= r` becomes `w >= R` with
`R = 2*pi*r^2` chosen by the submitter. Choosing `R` rational makes both hypotheses statements about
rational polynomials on rational half-lines, and a univariate polynomial is non-negative on
`[0, infinity)` exactly when it is `sigma0(w) + w*sigma1(w)` with both parts sums of squares. That
characterisation is complete, so the check is a proof and not a test: no sampling, no tolerance, no
root isolation. `pi` enters only the number finally reported.

Scoring runs from Rogers' classical bound - what was known before linear programming, and what a
submission gets for free - to the published Cohn-Elkies bound, and is uncapped above. Dimension 8
is the rung where the answer is known: Viazovska proved the optimum is exactly 1/16, the linear
programming bound is tight there, and the ceiling is 1.013. The other three have between four and
ten times that much room, all of it inside territory nobody has proved anything about.
"""
from __future__ import annotations

import math
from fractions import Fraction

# The algebra is inlined rather than imported from a sibling. The trusted driver loads this file by
# path, not as a package, so `from lp_algebra import ...` resolves against the harness's sys.path
# and not against this directory - it raised ModuleNotFoundError inside the sandbox while working
# perfectly when imported directly, which is the worst way for this to fail. verification/lp_algebra.py
# remains the readable statement of the same rules and the task's tests check the copies agree.


def laguerre(k: int, alpha: Fraction) -> list:
    """Coefficients of L_k^{(alpha)}(w) in ascending powers of w, exact for rational alpha.

    L_k^{(alpha)}(w) = sum_i (-1)^i * binom(k + alpha, k - i) * w^i / i!
    """
    out = []
    for i in range(k + 1):
        binomial = Fraction(1)
        for j in range(1, k - i + 1):
            binomial *= (alpha + i + j)
            binomial /= j
        factorial = Fraction(1)
        for j in range(1, i + 1):
            factorial *= j
        out.append((-1) ** i * binomial / factorial)
    return out


def poly_add(left: list, right: list) -> list:
    size = max(len(left), len(right))
    out = [Fraction(0)] * size
    for i, value in enumerate(left):
        out[i] += value
    for i, value in enumerate(right):
        out[i] += value
    return _trim(out)


def poly_scale(poly: list, factor) -> list:
    return _trim([factor * value for value in poly])


def poly_mul(left: list, right: list) -> list:
    if not left or not right:
        return []
    out = [Fraction(0)] * (len(left) + len(right) - 1)
    for i, a in enumerate(left):
        if a == 0:
            continue
        for j, b in enumerate(right):
            if b == 0:
                continue
            out[i + j] += a * b
    return _trim(out)


def poly_shift(poly: list, offset) -> list:
    """p(w) -> p(w + offset), by repeated synthetic division. Exact."""
    out = [Fraction(0)]
    for coefficient in reversed(poly):
        out = poly_add(poly_mul(out, [Fraction(offset), Fraction(1)]), [Fraction(coefficient)])
    return _trim(out)


def poly_eval(poly: list, point) -> Fraction:
    total = Fraction(0)
    for coefficient in reversed(poly):
        total = total * point + coefficient
    return total


def _trim(poly: list) -> list:
    while poly and poly[-1] == 0:
        poly.pop()
    return poly


def sum_of_squares(terms) -> list:
    """sum_k weight_k * q_k(w)^2 from [(weight, coefficients), ...]. Weights must be >= 0."""
    total: list = []
    for weight, polynomial in terms:
        if weight < 0:
            raise ValueError("a square carries a negative weight")
        if weight == 0:
            continue
        total = poly_add(total, poly_scale(poly_mul(polynomial, polynomial), weight))
    return total


def nonnegative_on_half_line(target: list, sigma0, sigma1) -> bool:
    """Verify `target(w) >= 0 for all w >= 0` from a Positivstellensatz certificate.

    A univariate polynomial is non-negative on [0, infinity) exactly when it can be written
    `sigma0(w) + w * sigma1(w)` with both parts sums of squares, so the certificate is complete:
    anything true has one, and anything with one is true. That is what makes this checkable rather
    than merely testable - no sampling, no tolerance, no root isolation.
    """
    reconstructed = poly_add(sum_of_squares(sigma0),
                             poly_mul([Fraction(0), Fraction(1)], sum_of_squares(sigma1)))
    return _trim(list(target)) == reconstructed

DIFFICULTY = 1

MAX_DEGREE = 60
MAX_SQUARES = 40
MAX_NUMERATOR = 10 ** 2000
MAX_DENOMINATOR = 10 ** 2000

# Cohn and Elkies, New upper bounds on sphere packings I, Annals of Mathematics 157 (2003),
# Table 3, page 711. Columns, verbatim: "Dimension | Best Packing Known | Rogers' Bound | New Upper
# Bound", all in centre density. Recorded with the retrieval date in references/anchors.json.
#
# The zero of the scale is not Rogers' bound. Rogers' bound comes from a different technique and is
# not reachable by this one at any degree anyone has managed to certify exactly; anchoring there
# would score every honest submission at zero. The zero is instead what *this* method gives with no
# work at all - the two-term certificate, whose value is closed form and derived in solution.py:
#
#     trivial(n) = ((n + 2) / (2*pi))^(n/2) * (n + 2) / 2^(n + 1)
#
# The one is the published Cohn-Elkies bound. Reaching it means writing down an exact rational
# certificate as strong as their numerical one, which as far as we can find nobody has published in
# any dimension; the scale is uncapped above it.
INSTANCES = (
    # Dimension 8 is the rung with a known answer: Viazovska proved the optimum is exactly 1/16 and
    # that the linear programming bound is tight there.
    {"dimension": 8, "best_packing": 0.0625, "rogers": 0.06326, "cohn_elkies": 0.06251},
    {"dimension": 12, "best_packing": 0.03704, "rogers": 0.06559, "cohn_elkies": 0.06279},
    {"dimension": 16, "best_packing": 0.0625, "rogers": 0.11774, "cohn_elkies": 0.10738},
    {"dimension": 20, "best_packing": 0.13154, "rogers": 0.32454, "cohn_elkies": 0.27855},
)


def trivial_bound(dimension):
    """The two-term certificate's bound, in closed form. See solution.py for the derivation."""
    return (((dimension + 2) / (2.0 * math.pi)) ** (dimension / 2.0)
            * (dimension + 2) / 2.0 ** (dimension + 1))


def _fraction(value):
    """Accept an integer or an exact [numerator, denominator] pair. Never a float.

    Floats are rejected rather than converted. A numerical solution of the linear program is not a
    certificate: the whole difficulty is that the optimum sits where the constraints are tight, and
    rounding a numerical optimum breaks them. Accepting floats would score the wrong thing.
    """
    if isinstance(value, bool):
        raise ValueError("boolean is not a coefficient")
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
        raise ValueError("coefficients must be integers or [numerator, denominator] pairs")
    if abs(number.numerator) > MAX_NUMERATOR or number.denominator > MAX_DENOMINATOR:
        raise ValueError("coefficient exceeds the size cap")
    return number


def _polynomial(value, limit=MAX_DEGREE):
    if not isinstance(value, (list, tuple)):
        raise ValueError("a polynomial is a list of coefficients, lowest degree first")
    if len(value) > limit + 1:
        raise ValueError("polynomial degree above the cap")
    return [_fraction(entry) for entry in value]


def _squares(value):
    if not isinstance(value, (list, tuple)):
        raise ValueError("a sum of squares is a list of {'weight', 'poly'} entries")
    if len(value) > MAX_SQUARES:
        raise ValueError("more squares than the cap allows")
    terms = []
    for entry in value:
        if not isinstance(entry, dict):
            raise ValueError("each square is a mapping with 'weight' and 'poly'")
        weight = _fraction(entry.get("weight"))
        if weight < 0:
            raise ValueError("square weights must be non-negative")
        terms.append((weight, _polynomial(entry.get("poly"))))
    return terms


def certified_bound(submission, instance):
    """Return the centre-density bound this certificate proves, or raise if it proves nothing."""
    if not isinstance(submission, dict):
        raise ValueError("a certificate is a mapping")
    dimension = instance["dimension"]
    alpha = Fraction(dimension, 2) - 1

    threshold = _fraction(submission.get("threshold"))
    if threshold <= 0:
        raise ValueError("the support threshold R must be positive")
    coefficients = [_fraction(c) for c in submission.get("coefficients", [])]
    if not coefficients:
        raise ValueError("'coefficients' must be a non-empty list")
    if len(coefficients) > MAX_DEGREE + 1:
        raise ValueError("more Laguerre coefficients than the degree cap allows")

    # f and its transform, in the variable w = 2*pi*|x|^2. The transform is the sign flip.
    forward: list = []
    transform: list = []
    for index, coefficient in enumerate(coefficients):
        basis = laguerre(index, alpha)
        forward = poly_add(forward, poly_scale(basis, coefficient))
        transform = poly_add(transform, poly_scale(basis, coefficient * (-1) ** index))

    at_zero = poly_eval(forward, Fraction(0))
    transform_at_zero = poly_eval(transform, Fraction(0))
    if at_zero <= 0:
        raise ValueError("f(0) must be positive")
    if transform_at_zero <= 0:
        raise ValueError("fhat(0) must be positive")

    # Hypothesis (2): fhat >= 0 everywhere, i.e. transform(w) >= 0 for w >= 0.
    positivity = submission.get("transform_nonnegative")
    if not isinstance(positivity, dict):
        raise ValueError("'transform_nonnegative' must carry sigma0 and sigma1")
    if not nonnegative_on_half_line(transform, _squares(positivity.get("sigma0", [])),
                                    _squares(positivity.get("sigma1", []))):
        raise ValueError("the certificate for fhat >= 0 does not reconstruct it")

    # Hypothesis (1): f <= 0 for |x| >= r, i.e. -forward(R + s) >= 0 for s >= 0.
    negativity = submission.get("tail_nonpositive")
    if not isinstance(negativity, dict):
        raise ValueError("'tail_nonpositive' must carry sigma0 and sigma1")
    shifted = poly_scale(poly_shift(forward, threshold), Fraction(-1))
    if not nonnegative_on_half_line(shifted, _squares(negativity.get("sigma0", [])),
                                    _squares(negativity.get("sigma1", []))):
        raise ValueError("the certificate for f <= 0 on the tail does not reconstruct it")

    # centre density <= (r/2)^n * f(0)/fhat(0), with r^2 = R/(2*pi). This is the only place pi
    # appears, and nothing is verified against it.
    radius_squared = float(threshold) / (2.0 * math.pi)
    if radius_squared <= 0:
        raise ValueError("degenerate radius")
    return (radius_squared ** (dimension / 2.0)) / (2.0 ** dimension) * float(
        at_zero / transform_at_zero)


def _instance_score(instance, bound):
    """Linear from the two-term certificate to the published Cohn-Elkies bound, uncapped above.

    Linear rather than logarithmic: the interesting region here spans a factor of two in the bound,
    not orders of magnitude, and the distance to the best packing known is not the right ruler
    because in dimension 8 that distance is zero at the answer while in dimension 20 it is most of
    the interval.
    """
    if bound <= instance["best_packing"]:
        # Below an explicitly exhibited packing. Reported, never scored.
        return 0.0, True
    easy = trivial_bound(instance["dimension"])
    span = easy - instance["cohn_elkies"]
    return max(0.0, (easy - bound) / span), False


def _public_instance(instance):
    return {
        "dimension": instance["dimension"],
        "laguerre_alpha": [instance["dimension"] - 2, 2],
        "max_degree": MAX_DEGREE,
        "max_squares": MAX_SQUARES,
        "max_numerator": MAX_NUMERATOR,
        "max_denominator": MAX_DENOMINATOR,
        "best_packing_known": instance["best_packing"],
        "rogers_bound": instance["rogers"],
        "cohn_elkies_bound": instance["cohn_elkies"],
        "two_term_certificate_bound": trivial_bound(instance["dimension"]),
    }


def evaluate(build_certificate):
    rows = []
    for index, instance in enumerate(INSTANCES):
        record = {
            "instance_index": index, "dimension": instance["dimension"],
            "best_packing_known": instance["best_packing"],
            "rogers_bound": instance["rogers"],
            "cohn_elkies_bound": instance["cohn_elkies"],
            "two_term_certificate_bound": trivial_bound(instance["dimension"]),
        }
        try:
            bound = certified_bound(build_certificate(_public_instance(instance)), instance)
            score, below = _instance_score(instance, bound)
            record.update({
                "valid": True, "certified_bound": bound,
                "instance_score": round(score, 6),
                "beats_rogers": bool(bound < instance["rogers"]),
                "beats_cohn_elkies": bool(bound < instance["cohn_elkies"]),
                "below_best_packing_known": bool(below),
            })
        except Exception as exc:  # noqa: BLE001 - a bad certificate scores zero, it does not crash this
            record.update({
                "valid": False, "reason": "%s: %s" % (type(exc).__name__, exc),
                "certified_bound": None, "instance_score": 0.0,
                "beats_rogers": False, "beats_cohn_elkies": False,
                "below_best_packing_known": False,
            })
        rows.append(record)

    valid = [row for row in rows if row["valid"]]
    combined = sum(row["instance_score"] for row in rows) / len(rows)
    return {
        "combined_score": float(combined),
        "valid": 1.0 if valid else 0.0,
        "feasibility_rate": len(valid) / len(rows),
        "raw_score": float(combined),
        "instances_with_a_valid_certificate": len(valid),
        "instances_beating_rogers": sum(1 for r in rows if r["beats_rogers"]),
        "instances_beating_cohn_elkies": sum(1 for r in rows if r["beats_cohn_elkies"]),
        "instances_below_best_packing_known": sum(
            1 for r in rows if r["below_best_packing_known"]),
        "per_instance": rows,
    }
