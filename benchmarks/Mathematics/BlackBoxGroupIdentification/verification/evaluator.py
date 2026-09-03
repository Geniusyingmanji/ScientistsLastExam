"""Hidden oracle for BlackBoxGroupIdentification.

A finite set of `order` labelled elements and a black-box product: `mul(a, b)` returns the label
of a*b. Nothing else - no identity label, no table, no names. The candidate has a query budget of
a few multiples of the order and must say which group this is, chosen from a public catalogue of
isomorphism types given with explicit constructions - or decline, for one of two stated reasons:
the operation is not a group at all (a Latin square that fails associativity), or it is a group
that is isomorphic to nothing in the catalogue.

Three ways to be wrong:

    order statistics    the multiset of element orders is the first thing anyone computes and it
                        does not determine the group: catalogue entries share it and differ in
                        their centre or derived subgroup. Naming a group from its order profile
                        alone is a guess dressed as an identification.
    the table you infer a generating set and the left-multiplication maps of its generators
                        determine the whole Cayley table - if the operation is associative. A
                        quasigroup that is not a group reconstructs into a table whose rows are
                        all permutations and which disagrees with the oracle on products nobody
                        queried. Checking the table's columns, or spending queries on predictions,
                        is what reveals it; reading off invariants does not.
    the catalogue       a group can be recognised as a group and still be none of the listed
                        types. Matching it to the nearest entry books a false identification;
                        the honest answer is that it lies outside the catalogue.

A non-group and an unlisted group are both declines, for different reasons, and the reason is
scored: the associativity check and the isomorphism test are different pieces of evidence.

Scoring keeps the discovery axes separate and normalises so that declining every world with the
better of the two blanket reasons earns exactly zero.
"""
from __future__ import annotations

import itertools
import math

import numpy as np

BUDGET_MULTIPLIER = 6
ABSTAIN_REASONS = ("not_a_group", "outside_catalogue")
WORLD_KINDS = ("catalogue", "not_a_group", "outside_catalogue")


# --------------------------------------------------------------------------------------------------
# Constructions. Every table is an (n, n) integer array over labels 0..n-1 with 0 the identity.
# --------------------------------------------------------------------------------------------------

def _table_from_elements(elements, product):
    index = {e: i for i, e in enumerate(elements)}
    n = len(elements)
    table = np.zeros((n, n), dtype=np.int64)
    for i, a in enumerate(elements):
        for j, b in enumerate(elements):
            table[i, j] = index[product(a, b)]
    return table


def cyclic_product(moduli):
    moduli = tuple(int(m) for m in moduli)
    elements = list(itertools.product(*[range(m) for m in moduli]))
    identity = tuple(0 for _ in moduli)
    elements.remove(identity)
    elements.insert(0, identity)
    return _table_from_elements(
        elements, lambda a, b: tuple((x + y) % m for x, y, m in zip(a, b, moduli)))


def semidirect(m, k, r):
    """Z_m x| Z_k with the generator of Z_k acting as a -> r*a; needs r^k = 1 mod m."""
    m, k, r = int(m), int(k), int(r)
    if pow(r, k, m) != 1 or math.gcd(r, m) != 1:
        raise ValueError("invalid semidirect action")
    elements = [(a, b) for b in range(k) for a in range(m)]
    return _table_from_elements(
        elements, lambda x, y: ((x[0] + pow(r, x[1], m) * y[0]) % m, (x[1] + y[1]) % k))


def dicyclic(n):
    """Dic_n of order 4n: <a, b | a^(2n) = 1, b^2 = a^n, b a b^-1 = a^-1>."""
    n = int(n)
    elements = [(i, j) for j in range(2) for i in range(2 * n)]

    def product(x, y):
        i1, j1 = x
        i2, j2 = y
        if j1 == 0:
            return ((i1 + i2) % (2 * n), j2)
        if j2 == 0:
            return ((i1 - i2) % (2 * n), 1)
        return ((i1 - i2 + n) % (2 * n), 0)

    return _table_from_elements(elements, product)


def direct(table_a, table_b):
    na, nb = table_a.shape[0], table_b.shape[0]
    elements = [(a, b) for a in range(na) for b in range(nb)]
    return _table_from_elements(
        elements, lambda x, y: (int(table_a[x[0], y[0]]), int(table_b[x[1], y[1]])))


def _closure(generators, compose, identity):
    elements = [identity]
    seen = {identity}
    frontier = [identity]
    while frontier:
        new = []
        for x in frontier:
            for g in generators:
                y = compose(g, x)
                if y not in seen:
                    seen.add(y)
                    elements.append(y)
                    new.append(y)
        frontier = new
    return _table_from_elements(elements, compose)


def permutation_group(generators):
    degree = len(generators[0])
    identity = tuple(range(degree))
    return _closure([tuple(g) for g in generators],
                    lambda p, q: tuple(p[q[i]] for i in range(degree)), identity)


def matrix_group_mod(generators, p):
    def compose(a, b):
        (a11, a12, a21, a22), (b11, b12, b21, b22) = a, b
        return ((a11 * b11 + a12 * b21) % p, (a11 * b12 + a12 * b22) % p,
                (a21 * b11 + a22 * b21) % p, (a21 * b12 + a22 * b22) % p)
    return _closure([tuple(g) for g in generators], compose, (1, 0, 0, 1))


def pauli_group():
    """The 16-element group generated by the Pauli matrices, encoded as scaled Gaussian integers."""
    def compose(a, b):
        A = np.array(a, dtype=complex).reshape(2, 2)
        B = np.array(b, dtype=complex).reshape(2, 2)
        C = A @ B
        return tuple(complex(round(z.real), round(z.imag)) for z in C.ravel())
    # X and Y alone generate a quaternion group of order 8; the scalar i is a third generator.
    x = (0j, 1 + 0j, 1 + 0j, 0j)
    y = (0j, -1j, 1j, 0j)
    scalar_i = (1j, 0j, 0j, 1j)
    return _closure([x, y, scalar_i], compose, (1 + 0j, 0j, 0j, 1 + 0j))


def build(construction):
    kind = construction["type"]
    if kind == "cyclic_product":
        return cyclic_product(construction["moduli"])
    if kind == "semidirect":
        return semidirect(construction["m"], construction["k"], construction["r"])
    if kind == "dicyclic":
        return dicyclic(construction["n"])
    if kind == "direct":
        return direct(build(construction["left"]), build(construction["right"]))
    if kind == "permutation":
        return permutation_group(construction["generators"])
    if kind == "matrix_mod":
        return matrix_group_mod(construction["generators"], construction["p"])
    if kind == "pauli":
        return pauli_group()
    raise ValueError("unknown construction %r" % (kind,))


# --------------------------------------------------------------------------------------------------
# Invariants used to score and to keep the catalogue unambiguous.
# --------------------------------------------------------------------------------------------------

def is_group(table):
    n = table.shape[0]
    if sorted(set(table[0])) != list(range(n)) or any(table[0, j] != j for j in range(n)):
        return False
    if any(table[i, 0] != i for i in range(n)):
        return False
    for i in range(n):
        if len(set(table[i])) != n or len(set(table[:, i])) != n:
            return False
    # Associativity in full: n^3 lookups, fine at these orders.
    ab = table
    left = ab[ab, :]           # (a*b)*c  -> left[a, b, c]
    right = ab[:, ab]          # a*(b*c)  -> right[a, b, c]
    return bool(np.array_equal(left, right))


def element_orders(table):
    n = table.shape[0]
    orders = []
    for a in range(n):
        x, k = a, 1
        while x != 0:
            x = int(table[x, a])
            k += 1
        orders.append(k)
    return orders


def fingerprint(table):
    n = table.shape[0]
    orders = element_orders(table)
    histogram = tuple(sorted((k, orders.count(k)) for k in set(orders)))
    centre = sum(1 for a in range(n) if all(table[a, b] == table[b, a] for b in range(n)))
    inverse = [int(np.where(table[a] == 0)[0][0]) for a in range(n)]
    commutators = {int(table[table[a, b], table[inverse[a], inverse[b]]]) for a in range(n) for b in range(n)}
    derived = {0}
    frontier = list(commutators)
    while frontier:
        new = []
        for x in frontier:
            for c in commutators:
                y = int(table[c, x])
                if y not in derived:
                    derived.add(y)
                    new.append(y)
        frontier = new
    squares = len({int(table[a, a]) for a in range(n)})
    return (histogram, centre, len(derived), squares)


# --------------------------------------------------------------------------------------------------
# The public catalogue, per order, with the constructions the candidate can build from.
# --------------------------------------------------------------------------------------------------

def _cp(*moduli):
    return {"type": "cyclic_product", "moduli": list(moduli)}


def _sd(m, k, r):
    return {"type": "semidirect", "m": m, "k": k, "r": r}


def _dic(n):
    return {"type": "dicyclic", "n": n}


def _x(left, right):
    return {"type": "direct", "left": left, "right": right}


S4 = {"type": "permutation", "generators": [[1, 2, 3, 0], [1, 0, 2, 3]]}
A4 = {"type": "permutation", "generators": [[1, 2, 0, 3], [0, 2, 3, 1]]}
SL23 = {"type": "matrix_mod", "p": 3, "generators": [[1, 1, 0, 1], [1, 0, 1, 1]]}
GL23 = {"type": "matrix_mod", "p": 3, "generators": [[1, 1, 0, 1], [1, 0, 1, 1], [1, 0, 0, 2]]}

CATALOGUE = {
    16: [
        ("C16", "cyclic of order 16", _cp(16)),
        ("C8xC2", "C8 x C2", _cp(8, 2)),
        ("C4xC4", "C4 x C4", _cp(4, 4)),
        ("C4xC2xC2", "C4 x C2 x C2", _cp(4, 2, 2)),
        ("C2^4", "elementary abelian of order 16", _cp(2, 2, 2, 2)),
        ("D16", "dihedral of order 16: <a,b | a^8 = b^2 = 1, b a b^-1 = a^-1>", _sd(8, 2, 7)),
        ("Q16", "generalised quaternion of order 16: <a,b | a^8 = 1, b^2 = a^4, b a b^-1 = a^-1>", _dic(4)),
        ("SD16", "semidihedral of order 16: <a,b | a^8 = b^2 = 1, b a b^-1 = a^3>", _sd(8, 2, 3)),
        ("M16", "modular group of order 16: <a,b | a^8 = b^2 = 1, b a b^-1 = a^5>", _sd(8, 2, 5)),
        ("C2xD8", "C2 x dihedral of order 8", _x(_cp(2), _sd(4, 2, 3))),
        ("C2xQ8", "C2 x quaternion of order 8", _x(_cp(2), _dic(2))),
    ],
    24: [
        ("C24", "cyclic of order 24", _cp(24)),
        ("C12xC2", "C12 x C2", _cp(12, 2)),
        ("C6xC2xC2", "C6 x C2 x C2", _cp(6, 2, 2)),
        ("D24", "dihedral of order 24: <a,b | a^12 = b^2 = 1, b a b^-1 = a^-1>", _sd(12, 2, 11)),
        ("Dic6", "dicyclic of order 24: <a,b | a^12 = 1, b^2 = a^6, b a b^-1 = a^-1>", _dic(6)),
        ("C3:C8", "C3 x| C8 with the generator of C8 inverting C3", _sd(3, 8, 2)),
        ("S4", "symmetric group on four letters", S4),
        ("SL(2,3)", "2x2 matrices of determinant 1 over the field with three elements", SL23),
        ("C2xA4", "C2 x alternating group on four letters", _x(_cp(2), A4)),
        ("C4xS3", "C4 x symmetric group on three letters", _x(_cp(4), _sd(3, 2, 2))),
        ("C3xD8", "C3 x dihedral of order 8", _x(_cp(3), _sd(4, 2, 3))),
        ("C3xQ8", "C3 x quaternion of order 8", _x(_cp(3), _dic(2))),
    ],
    32: [
        ("C32", "cyclic of order 32", _cp(32)),
        ("C16xC2", "C16 x C2", _cp(16, 2)),
        ("C8xC4", "C8 x C4", _cp(8, 4)),
        ("C8xC2xC2", "C8 x C2 x C2", _cp(8, 2, 2)),
        ("C4xC4xC2", "C4 x C4 x C2", _cp(4, 4, 2)),
        ("C4xC2^3", "C4 x C2 x C2 x C2", _cp(4, 2, 2, 2)),
        ("C2^5", "elementary abelian of order 32", _cp(2, 2, 2, 2, 2)),
        ("D32", "dihedral of order 32: <a,b | a^16 = b^2 = 1, b a b^-1 = a^-1>", _sd(16, 2, 15)),
        ("Q32", "generalised quaternion of order 32: <a,b | a^16 = 1, b^2 = a^8, b a b^-1 = a^-1>", _dic(8)),
        ("SD32", "semidihedral of order 32: <a,b | a^16 = b^2 = 1, b a b^-1 = a^7>", _sd(16, 2, 7)),
        ("M32", "modular group of order 32: <a,b | a^16 = b^2 = 1, b a b^-1 = a^9>", _sd(16, 2, 9)),
        ("C2xD16", "C2 x dihedral of order 16", _x(_cp(2), _sd(8, 2, 7))),
        ("C2xQ16", "C2 x generalised quaternion of order 16", _x(_cp(2), _dic(4))),
    ],
    48: [
        ("C48", "cyclic of order 48", _cp(48)),
        ("C24xC2", "C24 x C2", _cp(24, 2)),
        ("C12xC4", "C12 x C4", _cp(12, 4)),
        ("C12xC2xC2", "C12 x C2 x C2", _cp(12, 2, 2)),
        ("D48", "dihedral of order 48: <a,b | a^24 = b^2 = 1, b a b^-1 = a^-1>", _sd(24, 2, 23)),
        ("Dic12", "dicyclic of order 48: <a,b | a^24 = 1, b^2 = a^12, b a b^-1 = a^-1>", _dic(12)),
        ("C3:C16", "C3 x| C16 with the generator of C16 inverting C3", _sd(3, 16, 2)),
        ("C2xS4", "C2 x symmetric group on four letters", _x(_cp(2), S4)),
        ("C2xSL(2,3)", "C2 x SL(2,3)", _x(_cp(2), SL23)),
        ("GL(2,3)", "invertible 2x2 matrices over the field with three elements", GL23),
        ("C4xA4", "C4 x alternating group on four letters", _x(_cp(4), A4)),
        ("C2xC2xA4", "C2 x C2 x alternating group on four letters", _x(_cp(2, 2), A4)),
        ("C3xD16", "C3 x dihedral of order 16", _x(_cp(3), _sd(8, 2, 7))),
        ("C3xQ16", "C3 x generalised quaternion of order 16", _x(_cp(3), _dic(4))),
        ("C3xSD16", "C3 x semidihedral of order 16", _x(_cp(3), _sd(8, 2, 3))),
        ("C4xD12", "C4 x dihedral of order 12", _x(_cp(4), _sd(6, 2, 5))),
    ],
}

# Groups that exist at these orders and are deliberately absent from the catalogue. Their
# invariants differ from every catalogue entry of the same order (pinned by a test), so "outside
# the catalogue" is a determinable answer, not a matter of taste.
OUTSIDE = {
    16: [("C4:C4", _sd(4, 4, 3)), ("Pauli", {"type": "pauli"})],
    24: [("C2xDic3", _x(_cp(2), _dic(3))), ("C2xC3:C4", _x(_cp(2), _sd(3, 4, 2)))],
    32: [("C8:C4", _sd(8, 4, 5)), ("C4xD8", _x(_cp(4), _sd(4, 2, 3))), ("C2xM16", _x(_cp(2), _sd(8, 2, 5)))],
    48: [("C3xC4:C4", _x(_cp(3), _sd(4, 4, 3))), ("C6xD8", _x(_cp(6), _sd(4, 2, 3)))],
}

CONSTRUCTIONS_HELP = (
    "cyclic_product: Z_m1 x ... x Z_mk with componentwise addition. semidirect: Z_m x| Z_k, "
    "elements (a, b), product (a1, b1)(a2, b2) = (a1 + r^b1 * a2 mod m, b1 + b2 mod k). dicyclic: "
    "order 4n, <a, b | a^(2n) = 1, b^2 = a^n, b a b^-1 = a^-1>. direct: direct product of two "
    "constructions. permutation: the group generated by the listed permutations (images of "
    "0..d-1) under composition. matrix_mod: the group generated by the listed 2x2 matrices "
    "(row-major) under multiplication mod p. pauli: the 16-element group generated by the Pauli "
    "matrices X, Y and the scalar i."
)


def public_catalogue(order):
    return [{"id": name, "order": int(order), "presentation": presentation, "construction": construction}
            for name, presentation, construction in CATALOGUE[order]]


# --------------------------------------------------------------------------------------------------
# Worlds.
# --------------------------------------------------------------------------------------------------

def _relabel(table, rng):
    n = table.shape[0]
    perm = rng.permutation(n)
    inverse = np.argsort(perm)
    out = np.zeros_like(table)
    for x in range(n):
        for y in range(n):
            out[perm[x], perm[y]] = perm[table[x, y]]
    return out, inverse


def _isotope(table, rng):
    """A Latin square that is not a group: relabel rows, columns and values independently, and
    redraw until associativity visibly fails on sampled triples."""
    n = table.shape[0]
    for _attempt in range(50):
        s, t, f = rng.permutation(n), rng.permutation(n), rng.permutation(n)
        out = f[table[s][:, t]]
        triples = rng.integers(0, n, size=(200, 3))
        fails = sum(1 for a, b, c in triples if out[out[a, b], c] != out[a, out[b, c]])
        if fails >= 20:
            return out
    raise RuntimeError("could not draw a non-associative isotope")


def _world(spec):
    rng = np.random.default_rng(spec["seed"])
    kind, order = spec["kind"], int(spec["order"])
    if kind not in WORLD_KINDS:
        raise ValueError("unknown world kind: %r" % (kind,))
    if kind == "catalogue":
        entries = {name: construction for name, _p, construction in CATALOGUE[order]}
        table = build(entries[spec["group"]])
        truth = spec["group"]
    elif kind == "outside_catalogue":
        entries = dict(OUTSIDE[order])
        table = build(entries[spec["group"]])
        truth = None
    else:
        entries = {name: construction for name, _p, construction in CATALOGUE[order]}
        table = _isotope(build(entries[spec["group"]]), rng)
        truth = None
    if table.shape[0] != order:
        raise RuntimeError("construction has the wrong order")
    if kind != "not_a_group":
        table, _inverse = _relabel(table, rng)
    return {"kind": kind, "seed": spec["seed"], "order": order, "table": table,
            "truth": truth, "budget": BUDGET_MULTIPLIER * order}


class _Oracle:
    def __init__(self, world):
        self.table = world["table"]
        self.order = world["order"]
        self.budget = world["budget"]
        self.calls = 0
        self.violated = False

    def __call__(self, a, b):
        if self.calls >= self.budget:
            self.violated = True
            raise RuntimeError("query budget exhausted")
        if isinstance(a, bool) or isinstance(b, bool):
            raise ValueError("labels must be integers")
        a, b = int(a), int(b)
        if not (0 <= a < self.order and 0 <= b < self.order):
            raise ValueError("labels must lie in 0..order-1")
        self.calls += 1
        return int(self.table[a, b])


PUBLIC_PROBLEM = {
    "order": 16,
    "query_budget": BUDGET_MULTIPLIER * 16,
    "catalogue": None,
    "constructions_help": CONSTRUCTIONS_HELP,
    "abstain_reasons": list(ABSTAIN_REASONS),
    "measurement_model": "mul(a, b) returns the label of a*b for labels 0..order-1; labels are a "
                         "random relabelling, so no label is known to be the identity",
    "abstain_when": "either the operation fails associativity (it is a Latin square, not a group), "
                    "or it is a group isomorphic to no catalogue entry; say which",
}


def _validate_submission(submission, order):
    if not isinstance(submission, dict):
        raise ValueError("submission must be a mapping")
    abstain = bool(submission.get("abstain", False))
    confidence = float(submission.get("confidence", 0.0))
    if not math.isfinite(confidence):
        raise ValueError("confidence must be finite")
    confidence = float(np.clip(confidence, 0.0, 1.0))
    if abstain:
        reason = submission.get("abstain_reason")
        if reason not in ABSTAIN_REASONS:
            raise ValueError("abstain_reason must be one of %r" % (ABSTAIN_REASONS,))
        return None, reason, confidence
    name = submission.get("catalogue_id")
    valid = {entry for entry, _p, _c in CATALOGUE[order]}
    if not isinstance(name, str) or name not in valid:
        raise ValueError("catalogue_id must name an entry of this order's catalogue, or abstain")
    return name, None, confidence


def _metrics(world, name, reason):
    blank = {"identified": False, "mechanism_score": 0.0, "false_discovery": False,
             "correct_refusal": False, "refusal_reason_correct": False}
    kind = world["kind"]
    if kind == "catalogue":
        if name is None:
            return blank
        correct = name == world["truth"]
        blank.update({"identified": correct, "mechanism_score": 1.0 if correct else 0.0,
                      "false_discovery": not correct})
        return blank
    if name is not None:
        blank.update({"false_discovery": True})
        return blank
    correct_reason = reason == kind
    blank.update({"mechanism_score": 1.0 if correct_reason else 0.5, "correct_refusal": True,
                  "refusal_reason_correct": correct_reason})
    return blank


DEVELOPMENT_WORLDS = (
    {"kind": "catalogue", "order": 16, "group": "SD16", "seed": 51600301},
    {"kind": "catalogue", "order": 16, "group": "C4xC2xC2", "seed": 51600302},
    {"kind": "catalogue", "order": 16, "group": "C2xQ8", "seed": 51600303},
    {"kind": "not_a_group", "order": 16, "group": "Q16", "seed": 51600304},
    {"kind": "outside_catalogue", "order": 16, "group": "C4:C4", "seed": 51600305},
    {"kind": "catalogue", "order": 32, "group": "SD32", "seed": 53200301},
    {"kind": "catalogue", "order": 32, "group": "C8xC4", "seed": 53200302},
    {"kind": "catalogue", "order": 32, "group": "C2xQ16", "seed": 53200303},
    {"kind": "not_a_group", "order": 32, "group": "D32", "seed": 53200304},
    {"kind": "outside_catalogue", "order": 32, "group": "C8:C4", "seed": 53200305},
)

HELDOUT_WORLDS = (
    {"kind": "catalogue", "order": 24, "group": "SL(2,3)", "seed": 62400401},
    {"kind": "catalogue", "order": 24, "group": "C3:C8", "seed": 62400402},
    {"kind": "not_a_group", "order": 24, "group": "S4", "seed": 62400403},
    {"kind": "outside_catalogue", "order": 24, "group": "C2xDic3", "seed": 62400404},
    {"kind": "catalogue", "order": 48, "group": "GL(2,3)", "seed": 64800401},
    {"kind": "catalogue", "order": 48, "group": "C3xSD16", "seed": 64800402},
    {"kind": "not_a_group", "order": 48, "group": "C2xS4", "seed": 64800403},
    {"kind": "outside_catalogue", "order": 48, "group": "C3xC4:C4", "seed": 64800404},
)

ROW_KEYS = ("identified", "mechanism_score", "false_discovery", "correct_refusal", "refusal_reason_correct")


def _evaluate_world(identify, spec, split, index):
    world = _world(spec)
    oracle = _Oracle(world)
    problem = dict(PUBLIC_PROBLEM)
    problem.update({"order": world["order"], "query_budget": world["budget"],
                    "catalogue": public_catalogue(world["order"])})
    base = {"split": split, "world_index": int(index), "kind": world["kind"], "order": world["order"],
            "queries": 0}
    try:
        submission = identify(problem, oracle)
        name, reason, confidence = _validate_submission(submission, world["order"])
        if oracle.violated:
            raise RuntimeError("query budget exceeded")
        metrics = _metrics(world, name, reason)
        target = metrics["mechanism_score"]
        row = dict(base)
        row.update({key: metrics[key] for key in ROW_KEYS})
        row.update({
            "valid": True,
            "abstained": name is None,
            "claimed_id": name,
            "abstain_reason": reason,
            "confidence": round(confidence, 6),
            "confidence_calibration_score": round(1.0 - (confidence - target) ** 2, 6),
            "queries": oracle.calls,
        })
        row["mechanism_score"] = round(float(row["mechanism_score"]), 6)
        return row
    except Exception as exc:  # noqa: BLE001 - a bad candidate scores zero, it does not crash this
        row = dict(base)
        row.update({key: (0.0 if key.endswith("_score") else False) for key in ROW_KEYS})
        row.update({
            "valid": False,
            "reason": "%s: %s" % (type(exc).__name__, exc),
            "abstained": True,
            "claimed_id": None,
            "abstain_reason": None,
            "confidence": 0.0,
            "confidence_calibration_score": 0.0,
            "queries": oracle.calls,
        })
        return row


def _split_summary(records):
    catalogue = [r for r in records if r["kind"] == "catalogue"]
    unsupported = [r for r in records if r["kind"] != "catalogue"]
    raw = float(np.mean([r["mechanism_score"] for r in records]))
    # What declining everything earns with the better blanket reason: 1 on the worlds whose
    # reason it happens to match, 0.5 on the other unsupported worlds, 0 on catalogue worlds.
    anchors = []
    for reason in ABSTAIN_REASONS:
        anchors.append(sum((1.0 if r["kind"] == reason else 0.5) for r in unsupported) / len(records))
    always_abstain = max(anchors)
    normalized = float(np.clip((raw - always_abstain) / (1.0 - always_abstain), 0.0, 1.0))
    return {
        "normalized_mechanism": normalized,
        "raw_mechanism": raw,
        "identification_rate": float(np.mean([r["identified"] for r in catalogue])),
        "false_discovery_rate": float(np.mean([r["false_discovery"] for r in records])),
        "unsupported_false_discovery_rate": float(np.mean([r["false_discovery"] for r in unsupported])),
        "correct_refusal_rate": float(np.mean([r["correct_refusal"] for r in unsupported])),
        "refusal_reason_rate": float(np.mean([r["refusal_reason_correct"] for r in unsupported])),
        "discovery_coverage": float(np.mean([not r["abstained"] for r in catalogue])),
        "confidence_calibration": float(np.mean([r["confidence_calibration_score"] for r in records])),
        "mean_queries": float(np.mean([r["queries"] for r in records])),
        "valid_count": sum(bool(r["valid"]) for r in records),
        "world_count": len(records),
    }


def evaluate(identify):
    development = [_evaluate_world(identify, spec, "development", index)
                   for index, spec in enumerate(DEVELOPMENT_WORLDS)]
    heldout = [_evaluate_world(identify, spec, "heldout", index)
               for index, spec in enumerate(HELDOUT_WORLDS)]
    dev = _split_summary(development)
    held = _split_summary(heldout)
    return {
        "combined_score": dev["normalized_mechanism"],
        "valid": 1.0 if dev["valid_count"] > 0 else 0.0,
        "feasibility_rate": dev["valid_count"] / dev["world_count"],
        "raw_score": dev["normalized_mechanism"],
        "development_mechanism_score": dev["normalized_mechanism"],
        "development_raw_mechanism": dev["raw_mechanism"],
        "development_identification_rate": dev["identification_rate"],
        "development_false_discovery_rate": dev["false_discovery_rate"],
        "development_unsupported_false_discovery_rate": dev["unsupported_false_discovery_rate"],
        "development_correct_refusal_rate": dev["correct_refusal_rate"],
        "development_refusal_reason_rate": dev["refusal_reason_rate"],
        "development_discovery_coverage": dev["discovery_coverage"],
        "development_confidence_calibration": dev["confidence_calibration"],
        "development_mean_queries": dev["mean_queries"],
        # Evaluator-only: the sealed split is removed from the search-visible metric view by the
        # visibility contract, so a searcher cannot steer on it.
        "heldout_mechanism_score": held["normalized_mechanism"],
        "heldout_identification_rate": held["identification_rate"],
        "heldout_false_discovery_rate": held["false_discovery_rate"],
        "heldout_correct_refusal_rate": held["correct_refusal_rate"],
        "heldout_refusal_reason_rate": held["refusal_reason_rate"],
        "heldout_discovery_coverage": held["discovery_coverage"],
        "per_instance": development + heldout,
    }
