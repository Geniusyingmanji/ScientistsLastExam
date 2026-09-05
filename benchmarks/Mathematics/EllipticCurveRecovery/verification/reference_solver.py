"""Truth-blind reference witness: residue enumeration with CRT lifting.

Small primes are queried in ascending order as the budget allows; for each prime every (a mod p,
b mod p) pair is tested against the returned count by direct enumeration. The
product modulus exceeds the coefficient window twice over, so every consistent
combination lifts by the Chinese remainder theorem to at most one integer pair;
exactly one surviving lift is claimed, an empty residue set at any prime — no
elliptic pair reproduces the counts — is refused. It deliberately lacks
large-prime confirmation queries, quadratic-form methods and Hasse-interval
reasoning.
"""

from __future__ import annotations

QUERY_PRIMES = (11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47, 53, 59, 61, 67,
                71, 73, 79, 83, 89, 97)
BOUND = 1200


def _count(prime, a, b):
    total = 1
    for x in range(prime):
        value = (x * x * x + a * x + b) % prime
        if value == 0:
            total += 1
        elif pow(value, (prime - 1) // 2, prime) == 1:
            total += 2
    return total


def _residues(prime, count):
    return [(a, b) for a in range(prime) for b in range(prime)
            if _count(prime, a, b) == count]


def _centered(value, modulus):
    return value - modulus * round(value / modulus)


def recover_curve(problem, count_points, budget_units):
    budget = int(budget_units)
    per_prime = []
    for prime in QUERY_PRIMES:
        pairs = _residues(prime, count_points(prime)["point_count"])
        if not pairs:
            return {"a": None, "b": None, "abstain": True, "confidence": 0.8}
        per_prime.append(pairs)
        # Small primes cost one unit each; stop querying once the running modulus
        # pins a unique lift (the window is wide, so early stops are rare).
        if len(per_prime) >= 4 and budget - len(per_prime) <= 0:
            break

    # Incremental CRT with window pruning: after each prime, only lifts with a
    # representative inside the coefficient window survive, keeping the partial
    # sets small instead of enumerating the full cartesian product.
    partial = {(0, 0, 1)}  # (residue_a, residue_b, modulus)
    for prime, pairs in zip(QUERY_PRIMES, per_prime):
        extended = set()
        for ra, rb, modulus in partial:
            for pa, pb in pairs:
                new_modulus = modulus * prime
                factor = new_modulus // modulus
                inverse = pow(modulus % prime, -1, prime)
                combined = ((ra + modulus * (( (pa - ra) * inverse) % prime))
                            % new_modulus)
                combined_b = ((rb + modulus * (( (pb - rb) * inverse) % prime))
                              % new_modulus)
                a = _centered(combined, new_modulus)
                b = _centered(combined_b, new_modulus)
                if new_modulus <= 2 * BOUND + 1 or (abs(a) <= BOUND
                                                    and abs(b) <= BOUND):
                    extended.add((combined, combined_b, new_modulus))
        if not extended:
            return {"a": None, "b": None, "abstain": True, "confidence": 0.7}
        partial = extended

    lifts = set()
    for ra, rb, modulus in partial:
        a = _centered(ra, modulus)
        b = _centered(rb, modulus)
        if abs(a) <= BOUND and abs(b) <= BOUND and 4 * a ** 3 + 27 * b * b != 0:
            lifts.add((a, b))
    if len(lifts) != 1:
        return {"a": None, "b": None, "abstain": True, "confidence": 0.7}
    a, b = next(iter(lifts))
    return {"a": a, "b": b, "abstain": False, "confidence": 0.85}
