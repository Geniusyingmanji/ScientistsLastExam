"""Hidden oracle for FourSettingMomentCertificate.

The product is not an object. It is an argument, and the score is the strength of what the
argument proves.

The functional is Brunner-Gisin I_4422^{13}, not I3322. Extra basis words must be a
Hamming-weight subset of a frozen 24-word NPA-2 same-party pool; free words are rejected.
A certificate is an exact rational sum of squares for beta * I - B. Floats are rejected,
not rounded. The evaluator never solves an SDP.

Scoring is logarithmic in the gap to the two-qubit value 0.25, matching
BellBoundCertificate: the triangle bound 4 scores zero, and score one is hung at
certified bound 3.0. That target is a wave-1 evaluator anchor, not a published
NPA-2 number. The catalog SOS at 7/2 and the 36-point pairing grid both stop at
3.5 and therefore land below one. A certificate below 0.25 is reported rather
than scored.
"""
from __future__ import annotations

import math
from fractions import Fraction


# The algebra is inlined rather than imported from a sibling module. The trusted driver loads this
# file by path, not as a package, so `from algebra import ...` resolves against the harness's
# sys.path and not against this directory - it raised ModuleNotFoundError inside the sandbox while
# working perfectly when the file was imported directly, which is the worst way for this to fail.
# verification/algebra.py is kept as the readable statement of the same rules and is checked
# against this copy by the task's tests.


def reduce_side(letters) -> tuple:
    """Free reduction under X_i^2 = I."""
    out: list = []
    for x in letters:
        if out and out[-1] == x:
            out.pop()
        else:
            out.append(x)
    return tuple(out)


def canonical(a, b) -> tuple:
    return (reduce_side(a), reduce_side(b))


def dagger(word: tuple) -> tuple:
    a, b = word
    return (tuple(reversed(a)), tuple(reversed(b)))


def multiply(u: tuple, v: tuple) -> tuple:
    """u * v, using [A_x, B_y] = 0 to keep the A-part and B-part separate."""
    return canonical(u[0] + v[0], u[1] + v[1])

DIFFICULTY = 1

# I_4422^{13} correlator form lives with the instance table below.

# Entry magnitudes are bounded so that a well-formed submission cannot occupy the oracle for an
# unbounded time. The cost here is a product of two rationals per (square, basis pair), so the work
# is MAX_SQUARES * max_basis^2 multiplications of numbers no wider than these caps.
MAX_DENOMINATOR = 10 ** 2000
MAX_NUMERATOR = 10 ** 2000
MAX_WORD_LETTERS = 2


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
        # A float is rejected on purpose rather than converted: a floating-point SDP solution is
        # not a certificate, and silently rounding one would score the wrong thing.
        raise ValueError("matrix entries must be integers or [numerator, denominator] pairs")
    if abs(number.numerator) > MAX_NUMERATOR or number.denominator > MAX_DENOMINATOR:
        raise ValueError("matrix entry exceeds the size cap")
    return number


def _word(value, settings):
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValueError("a basis word is a [A-letters, B-letters] pair")
    sides = []
    for letters, count in zip(value, settings):
        if not isinstance(letters, (list, tuple)):
            raise ValueError("word sides must be lists of setting indices")
        if len(letters) > MAX_WORD_LETTERS:
            raise ValueError("word side longer than the cap")
        for letter in letters:
            if isinstance(letter, bool) or not isinstance(letter, int):
                raise ValueError("setting indices must be integers")
            if not 0 <= letter < count:
                raise ValueError("setting index outside the scenario")
        sides.append(tuple(letters))
    word = canonical(sides[0], sides[1])
    if word != (tuple(sides[0]), tuple(sides[1])):
        # Refusing an unreduced word keeps the basis a set: A_0 A_0 and the identity are the same
        # element, and letting both in would silently make the matrix singular in a way the
        # submitter did not intend.
        raise ValueError("basis words must already be reduced")
    return word


MAX_SQUARES = 60


def _read_certificate(value, instance):
    """Parse a submission into (basis, weights, vectors).

    The certificate is submitted *as the squares*, not as a matrix to be tested. A sum of squares
    is what the argument is, and taking it in that form makes positive semidefiniteness free:
    every ``weight >= 0`` and the operator is manifestly a non-negative combination of squares.
    The alternative - accept a matrix and prove it semidefinite by exact elimination - was the
    first design here and was dropped because its cost is not bounded by the submission's size.
    Rational elimination grows entries as it goes, so a well-formed 100-by-100 submission with
    twelve-digit denominators can occupy the oracle for an unbounded time. That is a denial of
    service against the grader, and no scientific content is lost by refusing it: any positive
    semidefinite rational matrix has an exact rational LDL decomposition, so a candidate that has
    one can always present it, and finding it is their cost rather than the oracle's.
    """
    if not isinstance(value, dict):
        raise ValueError("a certificate is a mapping with 'basis' and 'squares'")
    raw_basis = value.get("basis")
    raw_squares = value.get("squares")
    if not isinstance(raw_basis, (list, tuple)) or not raw_basis:
        raise ValueError("'basis' must be a non-empty list of words")
    if len(raw_basis) > instance["max_basis"]:
        raise ValueError("basis larger than the instance budget")
    basis = [_word(word, instance["settings"]) for word in raw_basis]
    if len(set(basis)) != len(basis):
        raise ValueError("basis words must be distinct")
    extras = [word for word in basis if word not in instance["npa1"]]
    if any(word not in instance["moment_pool"] for word in extras):
        raise ValueError("extra basis words must be taken from the frozen moment pool")
    if len(extras) > instance["extra_budget"]:
        raise ValueError("more extra moments than the Hamming-weight budget")
    size = len(basis)
    if not isinstance(raw_squares, (list, tuple)) or not raw_squares:
        raise ValueError("'squares' must be a non-empty list")
    if len(raw_squares) > MAX_SQUARES:
        raise ValueError("more squares than the cap allows")
    weights, vectors = [], []
    for square in raw_squares:
        if not isinstance(square, dict):
            raise ValueError("each square is a mapping with 'weight' and 'vector'")
        weight = _fraction(square.get("weight"))
        if weight < 0:
            raise ValueError("square weights must be non-negative")
        raw_vector = square.get("vector")
        if not isinstance(raw_vector, (list, tuple)) or len(raw_vector) != size:
            raise ValueError("each 'vector' must have one entry per basis word")
        weights.append(weight)
        vectors.append([_fraction(entry) for entry in raw_vector])
    return basis, weights, vectors


def certified_bound(basis, weights, vectors, instance):
    """Return the bound this certificate proves, or raise if it proves nothing.

    The certificate asserts

        beta * I - B = sum_k weight_k * (v_k . u)^dagger (v_k . u),   weight_k >= 0,

    with `u` the vector of basis words. Expanding the right-hand side gives one rational
    coefficient per canonical word; `beta` is read off the identity and every other word must match
    the functional exactly. There is no tolerance anywhere: the identity holds or it does not.
    """
    size = len(basis)
    products = [[None] * size for _ in range(size)]
    for i, s in enumerate(basis):
        ds = dagger(s)
        for j, t in enumerate(basis):
            products[i][j] = multiply(ds, t)
    produced = {}
    for weight, vector in zip(weights, vectors):
        if weight == 0:
            continue
        support = [i for i in range(size) if vector[i] != 0]
        for i in support:
            scaled = weight * vector[i]
            row = products[i]
            for j in support:
                word = row[j]
                produced[word] = produced.get(word, Fraction(0)) + scaled * vector[j]
    identity = ((), ())
    beta = produced.get(identity, Fraction(0))
    required = {word: Fraction(-coefficient)
                for word, coefficient in instance["functional"].items()}
    for word in set(produced) | set(required):
        if word == identity:
            continue
        if produced.get(word, Fraction(0)) != required.get(word, Fraction(0)):
            raise ValueError("operator identity fails at word %r" % (word,))
    return (beta + instance["offset"]) / instance["scale"]


def _instance_score(instance, bound):
    """Logarithmic in the distance to the two-qubit value; uncapped above.

    A linear ratio against the catalog SOS at 7/2 compressed the open region into
    the last step of a 36-point pairing grid. Halving the remaining gap to 0.25 is
    worth the same wherever it happens, which is the only scale on which 4 → 3.5
    and 3.5 → 3.0 are comparable. Score one is hung at 3.0, which that grid does
    not reach. There is still no independently recomputed NPA-2 number for this
    functional; 3.0 is a wave-1 evaluator target, not a recalled I3322 table.
    """
    quantum = instance["quantum_value"]
    gap = float(bound) - quantum
    if gap < 0.0:
        return 0.0, True
    easy_gap = instance["easy_bound"] - quantum
    target_gap = instance["target_bound"] - quantum
    span = math.log10(easy_gap) - math.log10(target_gap)
    achieved = math.log10(easy_gap) - math.log10(max(gap, target_gap * 1e-9))
    return max(0.0, achieved / span), False


# I_4422^{13} in Collins-Gisin form, Brunner and Gisin arXiv:0711.3362 Appendix A.
# Converted to +-1 correlators by P(A)=(1+a)/2, P(AB)=(1+a+b+ab)/4, then multiplied by 4.
# Classical maximum of the CG table is 0; 1811.11820 quotes L=1, Q=1.25 for the affine
# form 1 + I_CG, so the two-qubit quantum value of I_CG is 0.25.
I4422_TIMES_FOUR = {
    ((0,), ()): -1, ((1,), ()): -1, ((3,), ()): 2,
    ((), (0,)): -1, ((), (1,)): -1, ((), (3,)): 2,
    ((0,), (1,)): 1, ((0,), (2,)): 1, ((0,), (3,)): 1,
    ((1,), (0,)): 1, ((1,), (1,)): -2, ((1,), (2,)): 1, ((1,), (3,)): 1,
    ((2,), (0,)): 1, ((2,), (1,)): 1, ((2,), (2,)): -1, ((2,), (3,)): 1,
    ((3,), (0,)): 1, ((3,), (1,)): 1, ((3,), (2,)): 1, ((3,), (3,)): -1,
}

SETTINGS = (4, 4)
NPA1 = (((), ()),) + tuple(((i,), ()) for i in range(4)) + tuple(((), (j,)) for j in range(4))
MOMENT_POOL = (
    tuple(((i, k), ()) for i in range(4) for k in range(4) if i != k)
    + tuple(((), (j, l)) for j in range(4) for l in range(4) if j != l)
)
I4422_QUANTUM = 0.25
I4422_TRIANGLE = 4.0
I4422_CATALOG = 3.5
# Score one is hung here. The catalog SOS and the 36-point pairing grid prove 3.5
# and stop; 3.0 is not a published NPA-2 value for this functional.
I4422_SCORE_ONE = 3.0


def _i4422(name, extra_budget):
    return {
        "name": name,
        "settings": SETTINGS,
        "functional": I4422_TIMES_FOUR,
        "scale": 4, "offset": -8,
        "npa1": NPA1,
        "moment_pool": set(MOMENT_POOL),
        "extra_budget": extra_budget,
        "max_basis": 9 + extra_budget,
        "quantum_value": I4422_QUANTUM,
        "easy_bound": I4422_TRIANGLE,
        "catalog_bound": I4422_CATALOG,
        "target_bound": I4422_SCORE_ONE,
    }


INSTANCES = (
    _i4422("i4422_k4", 4),
    _i4422("i4422_k8", 8),
    _i4422("i4422_k12", 12),
)


def evaluate(build_certificate):
    """Score one submission across every instance.

    `build_certificate(instance)` is called once per instance with a mapping describing it - the
    functional, the scenario size, and the budget - and must return
    ``{"basis": [...], "squares": [{"weight": ..., "vector": [...]}, ...]}``. A submission that
    raises, returns nonsense, or returns a certificate whose identity does not hold scores zero on
    that instance and does not disturb the others.
    """
    rows = []
    for index, instance in enumerate(INSTANCES):
        published = {
            "instance_index": index, "name": instance["name"],
            "settings": list(instance["settings"]),
            "extra_budget": instance["extra_budget"],
            "basis_budget": instance["max_basis"],
            "free_bound": instance["easy_bound"],
            "catalog_sos_bound": instance["catalog_bound"],
            "score_one_bound": instance["target_bound"],
            "published_target_bound": instance["target_bound"],
            "best_known_quantum_value": instance["quantum_value"],
        }
        try:
            basis, weights, vectors = _read_certificate(
                build_certificate(_public_instance(instance)), instance)
            bound = certified_bound(basis, weights, vectors, instance)
            score, below_published = _instance_score(instance, bound)
            published.update({
                "valid": True,
                "certified_bound": float(bound),
                "basis_size": len(basis),
                "square_count": len(weights),
                "instance_score": round(score, 6),
                "beats_the_free_bound": bool(float(bound) < instance["easy_bound"]),
                "beats_the_published_target": bool(float(bound) < instance["target_bound"]),
                # A certificate below the best known quantum value would contradict an explicit
                # published strategy. It is reported, never scored: it is either a defect in this
                # checker or a result, and neither is a number to average.
                "below_best_known_quantum_value": bool(below_published),
            })
        except Exception as exc:  # noqa: BLE001 - a bad certificate scores zero, it does not crash this
            published.update({
                "valid": False, "reason": "%s: %s" % (type(exc).__name__, exc),
                "certified_bound": None, "basis_size": None, "square_count": None,
                "instance_score": 0.0, "beats_the_free_bound": False,
                "beats_the_published_target": False,
                "below_best_known_quantum_value": False,
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
        "instances_below_best_known_quantum_value": sum(
            1 for r in rows if r["below_best_known_quantum_value"]),
        "per_instance": rows,
    }


def _public_instance(instance):
    """What the candidate is told. Everything here is public; nothing is withheld.

    The functional, the scenario and the budget are the problem statement. The anchors are quoted
    from the literature and are in the task card. There is no hidden held-out set to protect,
    because the score is a proof: a certificate cannot be tuned to a grader it has not seen, it can
    only be correct or not.
    """
    return {
        "name": instance["name"],
        "settings": instance["settings"],
        "functional": {word: int(coefficient)
                       for word, coefficient in instance["functional"].items()},
        "scale": instance["scale"],
        "offset": instance["offset"],
        "extra_budget": instance["extra_budget"],
        "moment_pool": [[list(a), list(b)] for a, b in MOMENT_POOL],
        "max_basis": instance["max_basis"],
        "max_squares": MAX_SQUARES,
        "max_word_letters": MAX_WORD_LETTERS,
        "max_numerator": MAX_NUMERATOR,
        "max_denominator": MAX_DENOMINATOR,
        "free_bound": instance["easy_bound"],
        "catalog_sos_bound": instance["catalog_bound"],
        "score_one_bound": instance["target_bound"],
        "published_target_bound": instance["target_bound"],
        "best_known_quantum_value": instance["quantum_value"],
    }
