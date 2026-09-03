"""Truth-blind reference for BlackBoxGroupIdentification: find the identity from one element's
powers, grow a generating set by left-multiplication closure, reconstruct the whole table from
generator words, spend what is left of the budget checking predictions, and match the invariants
of the reconstructed table against tables built from the public catalogue.

Reads only the public problem and the charged oracle. Deliberately not at the ceiling: it picks
generators at random (so a group needing many generators eats most of the budget), verifies only
with whatever queries remain, and identifies by element-order profile plus centre size rather than
a full isomorphism test. A generator choice that reads the order profile first, a verification
plan with a fixed reserve, and finer invariants are the headroom a searcher is meant to claim.
"""
from __future__ import annotations

import itertools
import math

import numpy as np

MAX_VERIFICATION = 24


class _Budget(Exception):
    pass


def _build(construction):
    kind = construction["type"]
    if kind == "cyclic_product":
        moduli = [int(m) for m in construction["moduli"]]
        elements = list(itertools.product(*[range(m) for m in moduli]))
        identity = tuple(0 for _ in moduli)
        elements.remove(identity)
        elements.insert(0, identity)
        return _table(elements, lambda a, b: tuple((x + y) % m for x, y, m in zip(a, b, moduli)))
    if kind == "semidirect":
        m, k, r = int(construction["m"]), int(construction["k"]), int(construction["r"])
        elements = [(a, b) for b in range(k) for a in range(m)]
        return _table(elements, lambda x, y: ((x[0] + pow(r, x[1], m) * y[0]) % m, (x[1] + y[1]) % k))
    if kind == "dicyclic":
        n = int(construction["n"])
        elements = [(i, j) for j in range(2) for i in range(2 * n)]

        def product(x, y):
            if x[1] == 0:
                return ((x[0] + y[0]) % (2 * n), y[1])
            if y[1] == 0:
                return ((x[0] - y[0]) % (2 * n), 1)
            return ((x[0] - y[0] + n) % (2 * n), 0)
        return _table(elements, product)
    if kind == "direct":
        left, right = _build(construction["left"]), _build(construction["right"])
        elements = [(a, b) for a in range(left.shape[0]) for b in range(right.shape[0])]
        return _table(elements, lambda x, y: (int(left[x[0], y[0]]), int(right[x[1], y[1]])))
    if kind == "permutation":
        gens = [tuple(g) for g in construction["generators"]]
        d = len(gens[0])
        return _closure(gens, lambda p, q: tuple(p[q[i]] for i in range(d)), tuple(range(d)))
    if kind == "matrix_mod":
        p = int(construction["p"])

        def compose(a, b):
            return ((a[0] * b[0] + a[1] * b[2]) % p, (a[0] * b[1] + a[1] * b[3]) % p,
                    (a[2] * b[0] + a[3] * b[2]) % p, (a[2] * b[1] + a[3] * b[3]) % p)
        return _closure([tuple(g) for g in construction["generators"]], compose, (1, 0, 0, 1))
    if kind == "pauli":
        def compose(a, b):
            C = np.array(a, dtype=complex).reshape(2, 2) @ np.array(b, dtype=complex).reshape(2, 2)
            return tuple(complex(round(z.real), round(z.imag)) for z in C.ravel())
        return _closure([(0j, 1 + 0j, 1 + 0j, 0j), (0j, -1j, 1j, 0j), (1j, 0j, 0j, 1j)], compose,
                        (1 + 0j, 0j, 0j, 1 + 0j))
    raise ValueError("unknown construction %r" % (kind,))


def _table(elements, product):
    index = {e: i for i, e in enumerate(elements)}
    n = len(elements)
    table = np.zeros((n, n), dtype=np.int64)
    for i, a in enumerate(elements):
        for j, b in enumerate(elements):
            table[i, j] = index[product(a, b)]
    return table


def _closure(generators, compose, identity):
    elements, seen, frontier = [identity], {identity}, [identity]
    while frontier:
        new = []
        for x in frontier:
            for g in generators:
                y = compose(g, x)
                if y not in seen:
                    seen.add(y); elements.append(y); new.append(y)
        frontier = new
    return _table(elements, compose)


def _invariants(table, identity):
    n = table.shape[0]
    orders = []
    for a in range(n):
        x, k = a, 1
        while x != identity:
            x = int(table[x, a]); k += 1
        orders.append(k)
    histogram = tuple(sorted((k, orders.count(k)) for k in set(orders)))
    centre = sum(1 for a in range(n) if all(table[a, b] == table[b, a] for b in range(n)))
    return histogram, centre


def identify(problem, mul):
    n = int(problem["order"])
    budget = int(problem["query_budget"])
    spent = [0]

    def query(a, b):
        if spent[0] >= budget:
            raise _Budget()
        spent[0] += 1
        return int(mul(a, b))

    rng = np.random.default_rng(7)
    try:
        # Identity: powers of one element cycle back; the element before the repeat is e.
        a = int(rng.integers(0, n))
        powers = [a]
        while True:
            nxt = query(powers[-1], a)
            if nxt == a:
                break
            powers.append(nxt)
            if len(powers) > n:
                return {"abstain": True, "abstain_reason": "not_a_group", "confidence": 0.6}
        identity = powers[-1]
        # Left-multiplication closure over a growing generating set. left[g][x] = g*x.
        left = {}
        known = {identity: ()}          # element -> word (tuple of generator labels, applied right to left)
        order_found = [identity]
        generators = []
        while len(known) < n:
            unreached = [x for x in range(n) if x not in known]
            g = int(rng.choice(unreached))
            generators.append(g)
            left[g] = {}
            # Every element reached so far, multiplied on the left by the new generator, then the
            # frontier expands with all generators as usual.
            frontier = list(order_found)
            while frontier:
                new = []
                for x in frontier:
                    for h in generators:
                        if x in left[h]:
                            continue
                        y = query(h, x)
                        left[h][x] = y
                        if y not in known:
                            known[y] = (h,) + known[x]
                            order_found.append(y)
                            new.append(y)
                frontier = new
        # Reconstruct the table: y * x = apply y's word to x, one generator map at a time.
        table = np.zeros((n, n), dtype=np.int64)
        for y in range(n):
            word = known[y]
            for x in range(n):
                z = x
                for h in reversed(word):
                    z = left[h][z]
                table[y, x] = z
        # Verification with what is left: any disagreement means this is not a group.
        checks = min(MAX_VERIFICATION, budget - spent[0])
        for _ in range(checks):
            y, x = int(rng.integers(0, n)), int(rng.integers(0, n))
            if query(y, x) != table[y, x]:
                return {"abstain": True, "abstain_reason": "not_a_group", "confidence": 0.8}
    except _Budget:
        return {"abstain": True, "abstain_reason": "outside_catalogue", "confidence": 0.2}
    # Latin-square sanity: a group table has every element once per row and column.
    if any(len(set(table[i])) != n or len(set(table[:, i])) != n for i in range(n)):
        return {"abstain": True, "abstain_reason": "not_a_group", "confidence": 0.8}
    target = _invariants(table, identity)
    matches = []
    for entry in problem["catalogue"]:
        built = _build(entry["construction"])
        if _invariants(built, 0) == target:
            matches.append(entry["id"])
    if len(matches) == 1:
        return {"catalogue_id": matches[0], "abstain": False, "confidence": 0.75}
    if not matches:
        return {"abstain": True, "abstain_reason": "outside_catalogue", "confidence": 0.7}
    return {"catalogue_id": matches[0], "abstain": False, "confidence": 0.4}
