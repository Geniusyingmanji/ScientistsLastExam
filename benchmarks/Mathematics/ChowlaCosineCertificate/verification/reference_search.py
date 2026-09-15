"""Public-input-only constructions and deterministic local development search.

Numerical spectral factor screening is not a proof. Rational correction yields
the identity; the trusted evaluator, never imported here, checks that identity.
"""

from fractions import Fraction
from math import isqrt

import numpy as np


def _pair(value):
    return [value.numerator, value.denominator]


def sidon_certificate(problem):
    """Greedy distinct-difference ruler, with r=m/2 and n=m(m-1)/2."""
    n = problem["n_terms"]
    m = (1 + isqrt(1 + 8*n)) // 2
    if m * (m - 1) // 2 != n:
        raise ValueError("n_terms must be triangular")
    marks, differences = [0], set()
    while len(marks) < m:
        for candidate in range(marks[-1] + 1, problem["max_frequency"] + 1):
            new = {candidate - mark for mark in marks}
            if len(new) == len(marks) and differences.isdisjoint(new):
                differences.update(new)
                marks.append(candidate)
                break
        else:
            raise ValueError("greedy Sidon ruler does not fit max_frequency")
    return dict(frequencies=sorted(differences), bound=_pair(Fraction(m, 2)),
                factors=[dict(weight=[1, 2], terms=[[mark, 1] for mark in marks])])


def corrected_certificate(frequencies, coefficients):
    """Exact correction of any real rational q, including unwanted harmonics.

    If e_l = 1_A(l)/2 - c_l(q), add |e_l| |1+sign(e_l) z^l|^2.
    The resulting constant is c_0(q)+2 sum |e_l|. No sampled claim is trusted.
    """
    if len(set(frequencies)) != len(frequencies):
        raise ValueError("frequencies must be distinct")
    q = [Fraction(c) for c in coefficients]
    degree = max(max(frequencies), len(q) - 1)
    factors = []
    terms = [[i, _pair(c)] for i, c in enumerate(q) if c]
    if terms:
        factors.append(dict(weight=1, terms=terms))
    bound = sum((c*c for c in q), Fraction(0))
    selected = set(frequencies)
    for lag in range(1, degree + 1):
        correlation = sum((q[i] * q[i + lag] for i in range(len(q) - lag)), Fraction(0))
        error = (Fraction(1, 2) if lag in selected else Fraction(0)) - correlation
        if error:
            factors.append(dict(weight=_pair(abs(error)),
                                terms=[[0, 1], [lag, 1 if error > 0 else -1]]))
            bound += 2 * abs(error)
    return dict(frequencies=sorted(frequencies), bound=_pair(bound), factors=factors)


def spectral_certificate(frequencies, grid_size=8192, rational_bits=24):
    """Approximate a real spectral factor by FFT cepstrum, then correct exactly.

    A positive margin helps the approximation. Even if the sampled minimum
    misses a negative trough, correctness of the rational correction is unchanged.
    Coefficients use a common dyadic denominator to control exact-arithmetic cost.
    """
    degree = max(frequencies)
    if grid_size <= 2 * degree or not 1 <= rational_bits <= 40:
        raise ValueError("spectral grid or rational precision")
    x = 2 * np.pi * np.arange(grid_size) / grid_size
    cosine_sum = np.cos(np.outer(frequencies, x)).sum(axis=0)
    level = max(0.0, float(-cosine_sum.min())) + 0.01
    cepstrum = np.fft.fft(np.log(np.maximum(level + cosine_sum, 1e-12))) / grid_size
    analytic = np.zeros(grid_size, dtype=complex)
    analytic[0] = cepstrum[0] / 2
    analytic[1:grid_size//2] = cepstrum[1:grid_size//2]
    factor_samples = np.exp(np.fft.ifft(analytic) * grid_size)
    approximate = (np.fft.fft(factor_samples) / grid_size).real[:degree + 1]
    denominator = 1 << rational_bits
    rational = [Fraction(int(round(float(c) * denominator)), denominator) for c in approximate]
    return corrected_certificate(frequencies, rational)


def search_certificate(problem, iterations=128, grid_size=8192):
    """Deterministic discrete single-swap search followed by exact extraction.

    The local search screen is deliberately inexpensive. Try the best sampled
    set and the original Sidon set; retain the explicit Sidon identity if neither
    corrected bound improves it. No verifier or hidden state is consulted.
    """
    anchor = sidon_certificate(problem)
    selected = list(anchor["frequencies"])
    degree = problem["max_frequency"]
    x = 2 * np.pi * np.arange(grid_size) / grid_size
    cosines = np.cos(np.outer(np.arange(1, degree + 1), x))
    values = cosines[np.array(selected) - 1].sum(axis=0)
    best_screen = float(-values.min())
    # Local generator is reset for every call and unaffected by candidate RNG use.
    rng = np.random.default_rng(20260906)
    for _ in range(iterations):
        position = int(rng.integers(len(selected)))
        replacement = int(rng.integers(1, degree + 1))
        if replacement in selected:
            continue
        trial = values - cosines[selected[position] - 1] + cosines[replacement - 1]
        screen = float(-trial.min())
        if screen < best_screen:
            selected[position] = replacement
            values, best_screen = trial, screen
    best = anchor
    for frequencies in (sorted(selected), anchor["frequencies"]):
        candidate = spectral_certificate(frequencies, grid_size=grid_size)
        if Fraction(*candidate["bound"]) < Fraction(*best["bound"]):
            best = candidate
    return best
