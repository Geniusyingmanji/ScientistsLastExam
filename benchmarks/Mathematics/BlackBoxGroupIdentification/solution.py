"""Weak but valid baseline for BlackBoxGroupIdentification.

It does the first thing anyone does with a black-box group: pick elements at random, compute the
order of each by repeated multiplication until the budget runs out, and name the catalogue entry
whose element-order profile is nearest to the sampled one. It never reconstructs the table, so it
cannot tell a group from a Latin square that merely has orders; it never declines, so an unlisted
group is named after its nearest neighbour; and the order profile alone does not separate the
catalogue anyway.
"""
from __future__ import annotations

import itertools
import math

import numpy as np


def _orders_of_catalogue(entry):
    """Element-order profile of a catalogue construction, computed from a freshly built table."""
    c = entry["construction"]
    table = _build(c)
    n = table.shape[0]
    counts = {}
    for a in range(n):
        x, k = a, 1
        while x != 0:
            x = int(table[x, a]); k += 1
        counts[k] = counts.get(k, 0) + 1
    return {k: v / n for k, v in counts.items()}


def _build(c):
    kind = c["type"]
    if kind == "cyclic_product":
        moduli = [int(m) for m in c["moduli"]]
        elements = list(itertools.product(*[range(m) for m in moduli]))
        identity = tuple(0 for _ in moduli); elements.remove(identity); elements.insert(0, identity)
        return _table(elements, lambda a, b: tuple((x + y) % m for x, y, m in zip(a, b, moduli)))
    if kind == "semidirect":
        m, k, r = int(c["m"]), int(c["k"]), int(c["r"])
        return _table([(a, b) for b in range(k) for a in range(m)],
                      lambda x, y: ((x[0] + pow(r, x[1], m) * y[0]) % m, (x[1] + y[1]) % k))
    if kind == "dicyclic":
        n = int(c["n"])

        def product(x, y):
            if x[1] == 0:
                return ((x[0] + y[0]) % (2 * n), y[1])
            if y[1] == 0:
                return ((x[0] - y[0]) % (2 * n), 1)
            return ((x[0] - y[0] + n) % (2 * n), 0)
        return _table([(i, j) for j in range(2) for i in range(2 * n)], product)
    if kind == "direct":
        left, right = _build(c["left"]), _build(c["right"])
        return _table([(a, b) for a in range(left.shape[0]) for b in range(right.shape[0])],
                      lambda x, y: (int(left[x[0], y[0]]), int(right[x[1], y[1]])))
    if kind == "permutation":
        gens = [tuple(g) for g in c["generators"]]; d = len(gens[0])
        return _closure(gens, lambda p, q: tuple(p[q[i]] for i in range(d)), tuple(range(d)))
    if kind == "matrix_mod":
        p = int(c["p"])
        return _closure([tuple(g) for g in c["generators"]],
                        lambda a, b: ((a[0] * b[0] + a[1] * b[2]) % p, (a[0] * b[1] + a[1] * b[3]) % p,
                                      (a[2] * b[0] + a[3] * b[2]) % p, (a[2] * b[1] + a[3] * b[3]) % p),
                        (1, 0, 0, 1))
    if kind == "pauli":
        def compose(a, b):
            C = np.array(a, dtype=complex).reshape(2, 2) @ np.array(b, dtype=complex).reshape(2, 2)
            return tuple(complex(round(z.real), round(z.imag)) for z in C.ravel())
        return _closure([(0j, 1 + 0j, 1 + 0j, 0j), (0j, -1j, 1j, 0j), (1j, 0j, 0j, 1j)], compose,
                        (1 + 0j, 0j, 0j, 1 + 0j))
    raise ValueError(kind)


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


def identify(problem, mul):
    n = int(problem["order"])
    budget = int(problem["query_budget"])
    rng = np.random.default_rng(1)
    spent = 0
    sampled = {}
    # Order of an element: multiply by itself until the sequence repeats its first value.
    while spent < budget - n:
        a = int(rng.integers(0, n))
        seen = [a]
        x = a
        while spent < budget:
            x = int(mul(x, a)); spent += 1
            if x == a:
                break
            seen.append(x)
        k = len(seen)
        sampled[k] = sampled.get(k, 0) + 1
    total = sum(sampled.values()) or 1
    profile = {k: v / total for k, v in sampled.items()}
    best, best_distance = None, float("inf")
    for entry in problem["catalogue"]:
        reference = _orders_of_catalogue(entry)
        keys = set(profile) | set(reference)
        distance = sum(abs(profile.get(k, 0.0) - reference.get(k, 0.0)) for k in keys)
        if distance < best_distance:
            best, best_distance = entry["id"], distance
    return {"catalogue_id": best, "abstain": False, "confidence": 0.9}
