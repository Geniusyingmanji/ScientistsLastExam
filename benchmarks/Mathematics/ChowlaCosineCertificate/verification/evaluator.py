"""Exact, resource-bounded Laurent identity checker for a candidate Opt task.

No angular sampling contributes to verification. The score-one reference is a
reproducible Sidon construction, not the best known or optimal cosine polynomial.
"""

from collections import defaultdict
from fractions import Fraction
from math import gcd, isqrt, sqrt


# Immutable specifications: candidate calls receive independently built plain data.
WORLD_SPECS = ((15, 64), (28, 128), (45, 256))


def evaluation_problems():
    """Return fresh public input dictionaries for the frozen development worlds."""
    return [dict(n_terms=n, max_frequency=degree, max_factors=degree + 1,
                 max_total_terms=4 * degree + 4, max_pair_products=100000,
                 max_rational_bits=128, max_denominator_lcm_bits=512,
                 reference_bound=[(1 + isqrt(1 + 8*n)) // 2, 2])
            for n, degree in WORLD_SPECS]


def _integer(value, bits):
    if type(value) is not int or value.bit_length() > bits:
        raise ValueError("integer type or bit budget")
    return value


def _rational_parts(value, bits):
    # Check raw integers before Fraction construction (including unreduced pairs).
    if type(value) is int:
        return _integer(value, bits), 1
    if type(value) is not list or len(value) != 2:
        raise ValueError("rational must be an integer or two-integer list")
    numerator, denominator = (_integer(v, bits) for v in value)
    if denominator <= 0:
        raise ValueError("denominator must be positive")
    return numerator, denominator


def certified_bound(submission, problem):
    """Return the proven rational bound, or raise ValueError on invalid input.

    `problem` is trusted evaluator configuration. All untrusted containers and
    scalar values are checked before any Fraction arithmetic. Denominators share
    an LCM of at most max_denominator_lcm_bits; each product then divides its cube.
    Together with scalar bits and product count this bounds intermediate growth.
    """
    if type(submission) is not dict:
        raise ValueError("submission must be an object")
    if not {"frequencies", "bound", "factors"} <= submission.keys():
        raise ValueError("missing submission fields")
    bits = problem["max_rational_bits"]
    frequencies = submission["frequencies"]
    if type(frequencies) is not list or len(frequencies) != problem["n_terms"]:
        raise ValueError("frequency count")
    seen = set()
    for frequency in frequencies:
        _integer(frequency, bits)
        if not 1 <= frequency <= problem["max_frequency"] or frequency in seen:
            raise ValueError("frequency range or repetition")
        seen.add(frequency)

    factors = submission["factors"]
    if type(factors) is not list or not 1 <= len(factors) <= problem["max_factors"]:
        raise ValueError("factor count")
    # First cap the aggregate work, without walking the polynomial coefficients.
    total_terms = pair_products = 0
    for factor in factors:
        if type(factor) is not dict or not {"weight", "terms"} <= factor.keys():
            raise ValueError("factor fields")
        terms = factor["terms"]
        if type(terms) is not list or not terms:
            raise ValueError("terms must be a nonempty list")
        total_terms += len(terms)
        pair_products += len(terms) ** 2
        if total_terms > problem["max_total_terms"] or pair_products > problem["max_pair_products"]:
            raise ValueError("term or pair-product budget")

    denominator_lcm = 1
    def parts(value):
        nonlocal denominator_lcm
        pair = _rational_parts(value, bits)
        denominator_lcm = (denominator_lcm // gcd(denominator_lcm, pair[1])) * pair[1]
        if denominator_lcm.bit_length() > problem["max_denominator_lcm_bits"]:
            raise ValueError("collective denominator LCM budget")
        return pair

    raw_bound = parts(submission["bound"])
    raw_factors = []
    for factor in factors:
        weight = parts(factor["weight"])
        if weight[0] < 0:
            raise ValueError("negative weight")
        raw_terms = []
        exponents = set()
        for term in factor["terms"]:
            if type(term) is not list or len(term) != 2:
                raise ValueError("term must be exponent-coefficient pair")
            exponent = _integer(term[0], bits)
            if not 0 <= exponent <= problem["max_frequency"] or exponent in exponents:
                raise ValueError("exponent range or repetition")
            exponents.add(exponent)
            coefficient = parts(term[1])
            if coefficient[0] == 0:
                raise ValueError("zero sparse coefficient")
            raw_terms.append((exponent, coefficient))
        raw_factors.append((weight, raw_terms))

    bound = Fraction(*raw_bound)
    if not 0 < bound <= problem["n_terms"]:
        raise ValueError("bound must satisfy 0 < r <= n_terms")
    coefficients = defaultdict(Fraction)
    for raw_weight, raw_terms in raw_factors:
        weight = Fraction(*raw_weight)
        terms = [(exponent, Fraction(*value)) for exponent, value in raw_terms]
        for exponent, a in terms:
            for other, b in terms:
                coefficients[exponent - other] += weight * a * b
    target = {0: bound}
    for frequency in frequencies:
        target[frequency] = target[-frequency] = Fraction(1, 2)
    if {lag: value for lag, value in coefficients.items() if value} != target:
        raise ValueError("Laurent coefficient identity mismatch")
    return bound


def evaluate(candidate_callable):
    """Score all frozen worlds; failures contribute zero, never disappear."""
    rows = []
    for problem in evaluation_problems():
        n = problem["n_terms"]
        reference = Fraction(*problem["reference_bound"])
        row = dict(n_terms=n, max_frequency=problem["max_frequency"], valid=False,
                   score=0.0, bound=None, raw_bound=0.0, bound_over_sqrt_n=0.0,
                   reference_bound=[reference.numerator, reference.denominator],
                   reference_excess=0.0, reason="invalid submission")
        try:
            # Only the nested reference pair needs copying: all other values are ints.
            public = dict(problem, reference_bound=list(problem["reference_bound"]))
            submission = candidate_callable(public)
            bound = certified_bound(submission, problem)
            score = float(max(Fraction(0), (n - bound) / (n - reference)))
            row.update(valid=True, score=score, bound=[bound.numerator, bound.denominator],
                       raw_bound=float(bound), bound_over_sqrt_n=float(bound)/sqrt(n),
                       reference_excess=max(0.0, score - 1.0), reason="ok")
        except Exception:
            # Do not interpolate arbitrary candidate exceptions into stable JSON.
            pass
        rows.append(row)
    valid_count = sum(row["valid"] for row in rows)
    return dict(combined_score=sum(row["score"] for row in rows)/len(rows),
                valid=float(valid_count == len(rows)), feasibility_rate=valid_count/len(rows),
                reference_excess=sum(row["reference_excess"] for row in rows)/len(rows),
                per_instance=rows)
