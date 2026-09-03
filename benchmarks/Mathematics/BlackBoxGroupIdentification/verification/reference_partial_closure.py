"""Truth-blind reference for BlackBoxGroupIdentification.

The budget is 2.5 times the order and left-multiplication closure over k generators costs exactly
k * order queries, so a two-generated world can be reconstructed and identified exactly while a
world needing three or more cannot be at any price available here. This reference attempts the
closure and keeps whatever the attempt bought:

    identity        the powers of one random element close on it; the chain gives one order and
                    the cheapest associativity evidence available.
    closure         left-multiplication maps of generators drawn from the unreached labels. Every
                    product is cached, and the attempt is abandoned when the budget cannot cover
                    another generator.
    full table      when the closure completes, the table is reconstructed from generator words,
                    checked as a Latin square, and matched on the exact invariant tuple.
    stalled closure the number of generators already consumed is a lower bound on the rank, which
                    rules out every catalogue entry that needs fewer; the remaining budget goes on
                    commutation checks, because rank and the order profile do not separate this
                    catalogue and the centre is what does.

Deliberately not at the ceiling: it commits to the closure before knowing whether it can finish,
its rank bound is whatever the random generator draw happened to reveal, and its centre estimate
is a plain proportion over a handful of pairs. A searcher that prices the closure first, or that
spends on the pairs that separate the two entries still standing, has most of the score left.
"""
from __future__ import annotations

import itertools

import numpy as np

MAX_ORDER_SAMPLES = 6
CENTRE_TOLERANCE = 0.28


class _Budget(Exception):
    pass


def _build(construction):
    kind = construction["type"]
    if kind == "cyclic_product":
        moduli = [int(m) for m in construction["moduli"]]
        elements = list(itertools.product(*[range(m) for m in moduli]))
        identity = tuple(0 for _ in moduli)
        elements.remove(identity); elements.insert(0, identity)
        return _table(elements, lambda a, b: tuple((x + y) % m for x, y, m in zip(a, b, moduli)))
    if kind == "semidirect":
        m, k, r = int(construction["m"]), int(construction["k"]), int(construction["r"])
        return _table([(a, b) for b in range(k) for a in range(m)],
                      lambda x, y: ((x[0] + pow(r, x[1], m) * y[0]) % m, (x[1] + y[1]) % k))
    if kind == "dicyclic":
        n = int(construction["n"])

        def product(x, y):
            if x[1] == 0:
                return ((x[0] + y[0]) % (2 * n), y[1])
            if y[1] == 0:
                return ((x[0] - y[0]) % (2 * n), 1)
            return ((x[0] - y[0] + n) % (2 * n), 0)
        return _table([(i, j) for j in range(2) for i in range(2 * n)], product)
    if kind == "direct":
        left, right = _build(construction["left"]), _build(construction["right"])
        return _table([(a, b) for a in range(left.shape[0]) for b in range(right.shape[0])],
                      lambda x, y: (int(left[x[0], y[0]]), int(right[x[1], y[1]])))
    if kind == "permutation":
        gens = [tuple(g) for g in construction["generators"]]; d = len(gens[0])
        return _closure_table(gens, lambda p, q: tuple(p[q[i]] for i in range(d)), tuple(range(d)))
    if kind == "matrix_mod":
        p = int(construction["p"])
        return _closure_table([tuple(g) for g in construction["generators"]],
                              lambda a, b: ((a[0] * b[0] + a[1] * b[2]) % p, (a[0] * b[1] + a[1] * b[3]) % p,
                                            (a[2] * b[0] + a[3] * b[2]) % p, (a[2] * b[1] + a[3] * b[3]) % p),
                              (1, 0, 0, 1))
    if kind == "pauli":
        def compose(a, b):
            C = np.array(a, dtype=complex).reshape(2, 2) @ np.array(b, dtype=complex).reshape(2, 2)
            return tuple(complex(round(z.real), round(z.imag)) for z in C.ravel())
        return _closure_table([(0j, 1 + 0j, 1 + 0j, 0j), (0j, -1j, 1j, 0j), (1j, 0j, 0j, 1j)], compose,
                              (1 + 0j, 0j, 0j, 1 + 0j))
    raise ValueError("unknown construction %r" % (kind,))


def _table(elements, product):
    index = {e: i for i, e in enumerate(elements)}
    n = len(elements)
    out = np.zeros((n, n), dtype=np.int64)
    for i, a in enumerate(elements):
        for j, b in enumerate(elements):
            out[i, j] = index[product(a, b)]
    return out


def _closure_table(generators, compose, identity):
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


def _exact_invariants(table, identity=0, with_rank=False):
    n = table.shape[0]
    orders = []
    for a in range(n):
        x, k = a, 1
        while x != identity:
            x = int(table[x, a]); k += 1
        orders.append(k)
    histogram = tuple(sorted((k, orders.count(k)) for k in set(orders)))
    centre = sum(1 for a in range(n) if all(table[a, b] == table[b, a] for b in range(n))) / n
    squares = len({int(table[a, a]) for a in range(n)})
    out = {"orders": orders, "histogram": histogram, "centre": centre, "squares": squares}
    if with_rank:
        out["rank"] = _rank(table, identity)
        out["subgroup_orders"] = _subgroup_orders(table, identity)
    return out


def _generated(table, generators, identity):
    reached, frontier = {identity}, [identity]
    while frontier:
        new = []
        for x in frontier:
            for g in generators:
                y = int(table[g, x])
                if y not in reached:
                    reached.add(y); new.append(y)
        frontier = new
    return reached


def _rank(table, identity=0):
    """Minimal number of generators, by search over small subsets."""
    n = table.shape[0]
    for k in range(1, 6):
        for combo in itertools.combinations(range(n), k):
            if len(_generated(table, combo, identity)) == n:
                return k
    return 99


def _subgroup_orders(table, identity=0):
    """Orders of the subgroups generated by one or two elements: what a stalled closure reveals."""
    n = table.shape[0]
    out = set()
    for a in range(n):
        out.add(len(_generated(table, (a,), identity)))
        for b in range(a + 1, n):
            out.add(len(_generated(table, (a, b), identity)))
    return out


def identify(problem, mul):
    n = int(problem["order"])
    budget = int(problem["query_budget"])
    spent = [0]
    seen_products = {}

    def query(a, b):
        if (a, b) in seen_products:
            return seen_products[(a, b)]
        if spent[0] >= budget:
            raise _Budget()
        spent[0] += 1
        value = int(mul(a, b))
        seen_products[(a, b)] = value
        return value

    catalogue = [(entry["id"], _exact_invariants(_build(entry["construction"]), with_rank=True))
                 for entry in problem["catalogue"]]
    rng = np.random.default_rng(11)
    observed_orders = []
    identity = None
    reconstructed = None
    try:
        a = int(rng.integers(0, n))
        chain = [a]
        while True:
            nxt = query(chain[-1], a)
            if nxt == a:
                break
            chain.append(nxt)
            if len(chain) > n:
                return {"abstain": True, "abstain_reason": "not_a_group", "confidence": 0.6}
        identity = chain[-1]
        observed_orders.append(len(chain))
        if len(set(chain)) != len(chain) or n % len(chain) != 0:
            return {"abstain": True, "abstain_reason": "not_a_group", "confidence": 0.7}
        # Bet on the closure. Every product is cached, so an abandoned attempt is not wasted.
        left = {}
        known = {identity: ()}
        found = [identity]
        generators = []
        while len(known) < n and budget - spent[0] >= n - len(known):
            unreached = [x for x in range(n) if x not in known]
            g = int(rng.choice(unreached))
            generators.append(g)
            left[g] = {}
            frontier = list(found)
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
                            found.append(y)
                            new.append(y)
                frontier = new
        if len(known) < n:
            raise _Budget()
        table = np.zeros((n, n), dtype=np.int64)
        for y in range(n):
            word = known[y]
            for x in range(n):
                z = x
                for h in reversed(word):
                    z = left[h][z]
                table[y, x] = z
        if any(len(set(table[i])) != n or len(set(table[:, i])) != n for i in range(n)):
            return {"abstain": True, "abstain_reason": "not_a_group", "confidence": 0.8}
        reconstructed = table
    except _Budget:
        pass
    if identity is None:
        return {"abstain": True, "abstain_reason": "outside_catalogue", "confidence": 0.2}
    if reconstructed is not None:
        target = _exact_invariants(reconstructed, identity)
        matches = [name for name, inv in catalogue
                   if (inv["histogram"], round(inv["centre"], 6), inv["squares"])
                   == (target["histogram"], round(target["centre"], 6), target["squares"])]
        if len(matches) == 1:
            return {"catalogue_id": matches[0], "abstain": False, "confidence": 0.9}
        if not matches:
            return {"abstain": True, "abstain_reason": "outside_catalogue", "confidence": 0.8}
        return {"catalogue_id": matches[0], "abstain": False, "confidence": 0.4}
    # The closure stalled. What it bought: a rank lower bound, one or more element orders, and a
    # proper subgroup of the order reached so far.
    rank_lower_bound = len(generators)
    subgroup_order = len(known)
    survivors = []
    for name, invariants in catalogue:
        if invariants["rank"] < rank_lower_bound:
            continue
        profile = list(invariants["orders"])
        ok = True
        for k in observed_orders:
            if k in profile:
                profile.remove(k)
            else:
                ok = False
                break
        if ok and subgroup_order > 1 and subgroup_order < n and subgroup_order not in invariants["subgroup_orders"]:
            ok = False
        if ok:
            survivors.append((name, invariants))
    # Commutation checks with the rest of the budget: the centre is what separates the entries
    # that rank and the order profile leave standing.
    commuting, pairs = 0, 0
    try:
        while pairs < 8:
            x, y = int(rng.integers(0, n)), int(rng.integers(0, n))
            if x == y:
                continue
            pairs += 1
            if query(x, y) == query(y, x):
                commuting += 1
    except _Budget:
        pass
    if pairs:
        estimate = commuting / pairs
        survivors = [(name, inv) for name, inv in survivors
                     if estimate + CENTRE_TOLERANCE >= inv["centre"]] or survivors
        survivors.sort(key=lambda item: abs(item[1]["centre"] - estimate))
    if not survivors:
        return {"abstain": True, "abstain_reason": "outside_catalogue", "confidence": 0.6}
    return {"catalogue_id": survivors[0][0], "abstain": False,
            "confidence": round(min(0.8, 1.0 / len(survivors)), 3)}
