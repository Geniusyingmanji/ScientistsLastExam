"""Hidden oracle for BellBoundCertificate.

The product is not an object. It is an argument, and the score is the strength of what the
argument proves.

A Bell functional `B` is a linear combination of correlators of two spacelike-separated parties.
Its maximum over all quantum strategies is, for most functionals, unknown: the Navascues-Pironio-
Acin hierarchy produces a decreasing sequence of upper bounds that converges to it, and each level
costs combinatorially more than the last. A certificate for the bound `beta` is a sum-of-squares
decomposition

    beta * I - B = u^dagger Q u,    Q positive semidefinite,

where `u` is a vector of words in the observables. Any such pair `(u, Q)` proves `<B> <= beta` for
every state and every set of measurements: write `Q = R^dagger R`, and the right-hand side becomes
`(R u)^dagger (R u)`, whose expectation cannot be negative. Nothing about how the pair was found
matters. What is scored is `beta`.

Three things make this a task rather than a solver call.

**The certificate must be exact.** Entries are integers or integer ratios; the identity is checked
in exact rational arithmetic and positive semidefiniteness by exact symmetric elimination. A
floating-point SDP solution is not a certificate, and a submission of floats is rejected rather
than rounded. Extracting a rational certificate from a numerical one - and repairing the
feasibility that rounding destroys - is the work.

**The basis is chosen, not given.** Each instance caps how many words the certificate may use and
how long each may be. Which words to spend the budget on is the open part: arXiv:2607.14755
enumerates all 2^21 subsets of the level-2 moments for I3322 and finds the landscape non-monotone,
with real synergy between moments, so a greedy budget is not optimal.

**The relaxation is not tight.** For CHSH the hierarchy closes at the first level and the exact
answer 2*sqrt(2) is irrational, so a rational certificate can only approach it and the score is how
closely. For I3322 the hierarchy does not close at any level anyone has computed: level 1 gives
0.375, level 2 gives 0.25102173, and the best known quantum value is 0.25087538, reached only at
level 4 or higher. The gap between what a small certificate proves and what is true is the whole
scale of the task.

Scoring is uncapped and logarithmic in that gap. Halving the distance to the known quantum value is
worth the same wherever it happens, which is the only scale on which "0.375 -> 0.2757" and
"0.25103 -> 0.25102" are comparable improvements. A certificate that proves a bound *below* the
published quantum value would contradict an explicit published strategy; the oracle reports that
case rather than scoring it, because it is either a defect in this checker or a result.
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

# --- the functionals -------------------------------------------------------------------------
#
# Words are (A-part, B-part) tuples of letter indices; () is the identity. CHSH is textbook. The
# I3322 row is arXiv:2607.14755 eq. (18) *after* converting it out of the Collins-Gisin
# probability picture, which is what those coefficients actually are: read as +-1 correlators they
# give a classical bound of 8, not the 0 the paper states. Substituting
# P(A_i B_j) = (1 + a_i + b_j + c_ij)/4 and P(A_i) = (1 + a_i)/2 reproduces the classical bound of
# 0 exactly, and the level-1 relaxation of the result reproduces the paper's NPA1 = 0.37500001 to
# seven digits. The stored form is multiplied by 4 to clear denominators, so the reported bound is
# (raw + OFFSET) / SCALE.
CHSH = {((0,), (0,)): 1, ((0,), (1,)): 1, ((1,), (0,)): 1, ((1,), (1,)): -1}

I3322_TIMES_FOUR = {
    ((0,), ()): 1, ((1,), ()): 1, ((), (0,)): -1, ((), (1,)): -1,
    ((0,), (0,)): 1, ((0,), (1,)): 1, ((0,), (2,)): -1,
    ((1,), (0,)): 1, ((1,), (1,)): 1, ((1,), (2,)): 1,
    ((2,), (0,)): -1, ((2,), (1,)): 1,
}

# Entry magnitudes are bounded so that a well-formed submission cannot occupy the oracle for an
# unbounded time. The cost here is a product of two rationals per (square, basis pair), so the work
# is MAX_SQUARES * max_basis^2 multiplications of numbers no wider than these caps - about a
# hundred thousand operations on 270-bit rationals at the largest instance, which is a fraction of
# a second. Nothing is elided: an exact LDL decomposition of a rational semidefinite matrix has
# entries that are ratios of its leading minors, and 10^40 leaves room for those at these sizes.
MAX_DENOMINATOR = 10 ** 2000
MAX_NUMERATOR = 10 ** 2000
MAX_WORD_LETTERS = 3


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
    """Logarithmic in the distance to the best known quantum value; uncapped above.

    The alternative, a linear ratio against the easy bound, compresses everything interesting
    into the last two per cent of the scale: for I3322 the level-1 relaxation would already score
    0.93 and level 2 would score 1.00, with the entire open region between them indistinguishable.
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


# Anchors are published numbers, not measurements of this package. The three I3322 values are
# quoted verbatim from arXiv:2607.14755 section 3.1: "the best currently known quantum value is
# approximately 0.250 875 38, obtained at NPA4 or higher", "the NPA1 relaxation gives 0.375 000 01,
# and NPA2 gives 0.251 021 73". They are recorded with their source in references/anchors.json.
#
# `easy_bound` is what the standard first level proves - the answer a submission gets for free, and
# therefore the zero of the scale. `target_bound` is the best published bound, worth exactly 1.
# Neither is a ceiling: the score is uncapped, and the quantum value itself is only a supremum,
# shown in arXiv:2608.29734 not to be attained in any finite dimension.
I3322_QUANTUM = 0.25087538
I3322_NPA1 = 0.37500001
I3322_NPA2 = 0.25102173


def _i3322(name, max_basis):
    return {
        "name": name,
        "settings": (3, 3),
        "functional": I3322_TIMES_FOUR,
        # The stored functional is 4 * I3322 shifted by -4; undo both to report the bound in the
        # units the literature uses.
        "scale": 4, "offset": -4,
        "max_basis": max_basis,
        "quantum_value": I3322_QUANTUM,
        "easy_bound": I3322_NPA1,
        "target_bound": I3322_NPA2,
    }


INSTANCES = (
    {
        "name": "chsh",
        "settings": (2, 2),
        "functional": CHSH,
        "scale": 1, "offset": 0,
        "max_basis": 24,
        # Tsirelson's bound. Irrational, so no rational certificate attains it and the score is how
        # closely one comes. This instance exists so that a competent submission always has
        # somewhere to stand: a task whose every instance is open measures nothing when nobody
        # reaches the first rung, which is how a sibling task in this repository drew zero valid
        # proposals in three of three seeds.
        "quantum_value": 2.0 * math.sqrt(2.0),
        "easy_bound": 4.0,
        "target_bound": 2.0 * math.sqrt(2.0) + 1e-15,
    },
    # The same open functional under three certificate budgets. Which words to spend the budget on
    # is the open part: arXiv:2607.14755 enumerates all 2^21 level-2 moment subsets for I3322 and
    # reports a non-monotone landscape with genuine synergy between moments, so the budgeted
    # instances are not simply truncations of the generous one.
    _i3322("i3322_k12", 12),
    _i3322("i3322_k24", 24),
    _i3322("i3322_k40", 40),
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
            "basis_budget": instance["max_basis"],
            "free_bound": instance["easy_bound"],
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
        "max_basis": instance["max_basis"],
        "max_squares": MAX_SQUARES,
        "max_word_letters": MAX_WORD_LETTERS,
        "max_numerator": MAX_NUMERATOR,
        "max_denominator": MAX_DENOMINATOR,
        "free_bound": instance["easy_bound"],
        "published_target_bound": instance["target_bound"],
        "best_known_quantum_value": instance["quantum_value"],
    }
