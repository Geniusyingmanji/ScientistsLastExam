"""Reference construction for ShannonCapacityCertificate.

Both sides of the interval are built here, and neither is quoted from anywhere.

**Above.** For the odd cycle the Lovasz matrix can be taken circulant, which collapses the
semidefinite program to one free variable: with ``A[i][j] = x`` on the two edge diagonals and 1
everywhere else, the eigenvalues are ``n - 2 + 2x`` and ``2(x-1)cos(2 pi k/n)``, so the best ``x``
is where the largest of them cross. The reference finds that crossing by bisection on rationals
with a capped denominator, then bisects ``b`` upward until ``b*I - A`` passes the exact positive
definiteness test. The result is about ``3e-6`` above ``theta`` and is a proof rather than an
eigenvalue.

**Below.** Local search on the strong power is a trap: from a random start it reaches 337 of the
367 known codewords in ``C_7^{box 5}`` and then stops, and every restart stops in the same place.
What moves it is an algebraic seed. The construction here is the circular-graph route: for a
modulus ``n`` and a multiplier ``m``, the cyclic code ``{t * (1, m, m^2, ...) mod n}`` is pushed
into the cycle by ``x -> floor(cycle * x / n)``, the few collisions the rounding creates are pruned
away, and the survivors seed the local search. The sweep over ``(n, m)`` is the work; it is not
told where to look, and on ``C_7`` at power 5 it rediscovers the modulus 382 with multiplier 7 in
about twenty seconds.

Everything here is deterministic: the sweeps are over fixed ranges, the local search runs a fixed
number of iterations from a fixed seed, and no step reads the clock.
"""
from __future__ import annotations

import array
import heapq
import random

import numpy as np
from fractions import Fraction
from itertools import product


# --- the upper side ---------------------------------------------------------------------------


def _circulant(cycle: int, x: Fraction):
    return [[Fraction(1) if (i == j or (i - j) % cycle not in (1, cycle - 1)) else x
             for j in range(cycle)] for i in range(cycle)]


def _positive_definite(matrix) -> bool:
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


def _proves(cycle: int, x: Fraction, bound: Fraction) -> bool:
    matrix = _circulant(cycle, x)
    shifted = [[(bound if i == j else Fraction(0)) - matrix[i][j] for j in range(cycle)]
               for i in range(cycle)]
    return _positive_definite(shifted)


def theta_certificate(cycle: int, denominator: int = 10 ** 6):
    """A rational Lovasz matrix and a rational bound it proves, both exact.

    The two eigenvalue families move in opposite directions in ``x``, so the smallest achievable
    ``lambda_max`` sits where they meet. Bisecting on the grid of rationals with the given
    denominator finds that crossing without ever naming ``cos(pi/n)``; the bound is then the
    smallest grid point above it that the exact test accepts.
    """
    low, high = -Fraction(cycle), Fraction(1)
    for _ in range(80):
        middle = Fraction((low.numerator * high.denominator + high.numerator * low.denominator),
                          2 * low.denominator * high.denominator)
        # n - 2 + 2x rises with x; the other family falls. Compare them through the exact test at
        # a bound slightly above the rising branch.
        rising = Fraction(cycle - 2) + 2 * middle
        if _proves(cycle, middle, rising + Fraction(1, denominator)):
            high = middle
        else:
            low = middle
    x = Fraction(round(high * denominator), denominator)
    bound = Fraction(cycle - 2) + 2 * x
    step = Fraction(1, denominator)
    for _ in range(64):
        if _proves(cycle, x, bound):
            return _circulant(cycle, x), bound
        bound += step
    raise RuntimeError("no rational bound was certified")


# --- the lower side ---------------------------------------------------------------------------


def neighbour_table(cycle: int, power: int):
    """Flat adjacency for C_cycle^{box power}: row v holds the 3^power - 1 neighbours of v."""
    shifts = [s for s in product((0, 1, cycle - 1), repeat=power) if any(s)]
    weights = [cycle ** i for i in range(power)]
    size = cycle ** power
    degree = len(shifts)
    table = array.array("i", bytes(4 * size * degree))
    for vertex in range(size):
        digits = [(vertex // weights[i]) % cycle for i in range(power)]
        base = vertex * degree
        for position, shift in enumerate(shifts):
            table[base + position] = sum(
                ((digits[i] + shift[i]) % cycle) * weights[i] for i in range(power))
    return table, degree, size


def cyclic_code(cycle: int, power: int, modulus: int, multiplier: int):
    """{t * (1, m, m^2, ...) mod n} rounded into the cycle by x -> floor(cycle * x / n).

    Vectorised because the sweep is dominated by building these, not by pruning them: the
    pure-Python form costs about five milliseconds per code, and a fifty-wide modulus window over
    all multipliers is tens of thousands of codes. Everything here is exact integer arithmetic -
    t * m^i stays far inside int64 for the moduli this task sweeps - so the vectorised form returns
    the same set as the loop, which the task's tests check on four parameter sets.
    """
    powers = np.ones(power, dtype=np.int64)
    for i in range(1, power):
        powers[i] = (powers[i - 1] * multiplier) % modulus
    steps = np.arange(modulus, dtype=np.int64)
    rounded = (cycle * ((steps[:, None] * powers[None, :]) % modulus)) // modulus
    weights = cycle ** np.arange(power, dtype=np.int64)
    return set(np.unique(rounded @ weights).tolist())


def _collisions(table, degree, members, cap):
    total = 0
    for vertex in members:
        for other in table[vertex * degree:(vertex + 1) * degree]:
            if other in members:
                total += 1
                if total > cap:
                    return total
    return total


def prune(table, degree, members):
    """Drop the most-conflicted codeword until nothing collides."""
    members = set(members)
    conflicts = {v: [u for u in table[v * degree:(v + 1) * degree] if u in members]
                 for v in members}
    count = {v: len(c) for v, c in conflicts.items()}
    heap = [(-count[v], v) for v in members if count[v]]
    heapq.heapify(heap)
    while heap:
        negative, vertex = heapq.heappop(heap)
        if vertex not in members or -negative != count[vertex] or count[vertex] == 0:
            continue
        members.discard(vertex)
        for other in conflicts[vertex]:
            if other in members:
                count[other] -= 1
                heapq.heappush(heap, (-count[other], other))
    return members


def extend(table, degree, size, members, rng):
    occupied = bytearray(size)
    blocked = array.array("i", bytes(4 * size))
    for vertex in members:
        occupied[vertex] = 1
        for other in table[vertex * degree:(vertex + 1) * degree]:
            blocked[other] += 1
    grown = set(members)
    order = list(range(size))
    rng.shuffle(order)
    for vertex in order:
        if occupied[vertex] or blocked[vertex]:
            continue
        occupied[vertex] = 1
        grown.add(vertex)
        for other in table[vertex * degree:(vertex + 1) * degree]:
            blocked[other] += 1
    return grown


def plateau(table, degree, size, members, rng, iterations):
    """The (1,0) and (1,1) swap walk, run for a fixed number of draws."""
    occupied = bytearray(size)
    blocked = array.array("i", bytes(4 * size))
    live = set(members)
    for vertex in live:
        occupied[vertex] = 1
        for other in table[vertex * degree:(vertex + 1) * degree]:
            blocked[other] += 1
    best = set(live)
    draw = rng.randrange
    for _ in range(iterations):
        vertex = draw(size)
        if occupied[vertex]:
            continue
        crowd = blocked[vertex]
        if crowd > 1:
            continue
        if crowd == 1:
            base = vertex * degree
            for position in range(base, base + degree):
                other = table[position]
                if occupied[other]:
                    occupied[other] = 0
                    live.discard(other)
                    reach = other * degree
                    for step in range(reach, reach + degree):
                        blocked[table[step]] -= 1
                    break
        occupied[vertex] = 1
        live.add(vertex)
        base = vertex * degree
        for position in range(base, base + degree):
            blocked[table[position]] += 1
        if len(live) > len(best):
            best = set(live)
    return best


def sweep(cycle, power, table, degree, low, high):
    """Search moduli and multipliers; keep the largest independent set the rounding leaves."""
    best_size, best_pair, best_set = 0, None, set()
    for modulus in range(low, high):
        for multiplier in range(2, modulus):
            raw = cyclic_code(cycle, power, modulus, multiplier)
            slack = len(raw) - best_size
            if slack <= 0:
                continue
            if _collisions(table, degree, raw, 8 * slack) > 8 * slack:
                continue
            kept = prune(table, degree, raw)
            if len(kept) > best_size:
                best_size, best_pair, best_set = len(kept), (modulus, multiplier), kept
    return best_size, best_pair, best_set


def _decode(cycle, power, vertex):
    return [(vertex // cycle ** i) % cycle for i in range(power)]


# The search window per instance. The modulus of a cyclic code is close to the number of codewords
# it can yield, so each window brackets `published_target ** power` - the size the instance is
# reaching for - rather than being fitted to where the winner turned out to be. The windows are
# about fifty wide because the sweep costs one prune per (modulus, multiplier) pair that survives
# the collision filter, and a 170-wide window for C23 took over four hundred seconds on its own.
# The plateau is six million draws only for C7, where it is load-bearing (359 codewords after the
# greedy extension, 366 after the walk); on the other three the walk never improved the pruned
# circular code, so a million draws is enough to show that and cheap enough to keep. Powers are chosen by
# measurement, not by taking the largest allowed: at power 4 the sweep gives 1513 codewords for the
# thirteen-cycle, and 1513^(1/4) = 6.2362 is *below* what squaring the two-coordinate set already
# proves, while 245 at power 3 is above it. The plateau length is a fixed iteration count rather
# than a wall-clock budget so that this reference is reproducible.
PLANS = {
    "C7": {"power": 5, "window": (350, 400), "plateau": 6_000_000},
    "C13": {"power": 3, "window": (240, 275), "plateau": 1_000_000},
    "C19": {"power": 3, "window": (790, 845), "plateau": 1_000_000},
    "C23": {"power": 3, "window": (1410, 1480), "plateau": 1_000_000},
}


def classical_floor(cycle, max_power, rng, iterations=2_000_000, restarts=3):
    """The construction anyone gets: the best two-coordinate code, squared if the cap allows.

    This is the zero of the scale, and the reference submits it alongside its own search so a bad
    sweep can only fail to improve on it, never fall below it. The budget is sized by measurement:
    three restarts of two million draws reach floor(n(n-1)/4) - 39, 85 and 126 for the thirteen-,
    nineteen- and twenty-three-cycle - in about five seconds. Half a million draws reaches 125 of
    the 126 on the largest of them, which is why the number is not smaller.
    """
    table, degree, size = neighbour_table(cycle, 2)
    best = set()
    for _ in range(restarts):
        grown = extend(table, degree, size, set(), rng)
        found = plateau(table, degree, size, grown, rng, iterations)
        if len(found) > len(best):
            best = found
    pairs = [tuple(_decode(cycle, 2, v)) for v in sorted(best)]
    if max_power >= 4:
        return 4, [list(a + b) for a in pairs for b in pairs]
    return 2, [list(p) for p in pairs]


def reference_certificate(instance):
    plan = PLANS[instance["name"]]
    cycle, power = instance["cycle"], plan["power"]
    rng = random.Random(20260906)

    floor_power, floor_words = classical_floor(cycle, instance["max_power"], rng)

    table, degree, size = neighbour_table(cycle, power)
    _size, _pair, seed = sweep(cycle, power, table, degree, *plan["window"])
    grown = extend(table, degree, size, seed, rng) if seed else set()
    best = plateau(table, degree, size, grown, rng, plan["plateau"]) if grown else set()

    lower = [{"power": floor_power, "vertices": floor_words}]
    if best:
        lower.append({"power": power,
                      "vertices": [_decode(cycle, power, v) for v in sorted(best)]})

    matrix, bound = theta_certificate(cycle)
    return {
        "lower_certificates": lower,
        "upper_certificate": {
            "matrix": [[[entry.numerator, entry.denominator] for entry in row] for row in matrix],
            "bound": [bound.numerator, bound.denominator],
        },
    }


def build_certificate(instance):
    return reference_certificate(instance)
