"""Reference: a seeded structural search for an exactly certifiable certificate.

Deliberately below the ceiling, and the way it is below is the point. Three stronger-looking
approaches were measured and discarded first:

  * **The grid linear program**, which is the textbook numerical method, does not merely fail to
    produce a certificate - it produces *false bounds*. At degree 16 it reports 0.06237 in dimension
    8, below what the E8 lattice actually achieves, and 0.00066 in dimension 16 against a packing of
    0.0625. The polynomial satisfies every grid constraint and dips between the points. Exact
    extraction refuses all of its solutions, at every degree and rounding denominator tried.
  * **Searching the Laguerre coefficients directly.** Four thousand random draws produced not one
    candidate that passed even a numerical screen: the feasible set is a thin sliver.
  * **A semidefinite formulation over Gram factors** with the tail as a penalty. Six restarts of a
    derivative-free method per configuration, and no configuration produced an extractable
    certificate, because at the optimum both hypotheses are tight and a rational point needs slack.

What works is to make the tail hypothesis structural. Writing

    -f(R + s) = q0(s)^2 + s * q1(s)^2

means `f <= 0` on `[R, infinity)` holds by construction with its certificate already in hand. That
fixes `f`, hence its Laguerre coefficients, hence the transform, and leaves one thing to establish
by extraction rather than two coupled things. Every draw then starts inside half the feasible set
instead of outside all of it.

The search below is small, seeded and bounded, so it is reproducible and finishes in about a minute
for the whole instance set. It is also nowhere near the frontier: it draws `q0` and `q1` with at
most three terms and small rational coefficients. Raising the degree, choosing the radius by
optimisation rather than by draw, and rounding with per-entry denominators are all left on the
table.
"""
from __future__ import annotations

import math
from fractions import Fraction

import numpy as np
from scipy.optimize import minimize

# Everything is inlined so this file is self-contained. It is run two ways - directly, and as a
# candidate inside the Bubblewrap sandbox where only the submitted program is present and
# verification/ is not readable - and a sibling import works in the first and fails in the second
# with "blocked_or_missing_import". verification/lp_algebra.py, extract.py and search.py remain the
# readable statements of the same code.


def laguerre(k: int, alpha: Fraction) -> list:
    """Coefficients of L_k^{(alpha)}(w) in ascending powers of w, exact for rational alpha.

    L_k^{(alpha)}(w) = sum_i (-1)^i * binom(k + alpha, k - i) * w^i / i!
    """
    out = []
    for i in range(k + 1):
        binomial = Fraction(1)
        for j in range(1, k - i + 1):
            binomial *= (alpha + i + j)
            binomial /= j
        factorial = Fraction(1)
        for j in range(1, i + 1):
            factorial *= j
        out.append((-1) ** i * binomial / factorial)
    return out


def poly_add(left: list, right: list) -> list:
    size = max(len(left), len(right))
    out = [Fraction(0)] * size
    for i, value in enumerate(left):
        out[i] += value
    for i, value in enumerate(right):
        out[i] += value
    return _trim(out)


def poly_scale(poly: list, factor) -> list:
    return _trim([factor * value for value in poly])


def poly_mul(left: list, right: list) -> list:
    if not left or not right:
        return []
    out = [Fraction(0)] * (len(left) + len(right) - 1)
    for i, a in enumerate(left):
        if a == 0:
            continue
        for j, b in enumerate(right):
            if b == 0:
                continue
            out[i + j] += a * b
    return _trim(out)


def poly_shift(poly: list, offset) -> list:
    """p(w) -> p(w + offset), by repeated synthetic division. Exact."""
    out = [Fraction(0)]
    for coefficient in reversed(poly):
        out = poly_add(poly_mul(out, [Fraction(offset), Fraction(1)]), [Fraction(coefficient)])
    return _trim(out)


def poly_eval(poly: list, point) -> Fraction:
    total = Fraction(0)
    for coefficient in reversed(poly):
        total = total * point + coefficient
    return total


def _trim(poly: list) -> list:
    while poly and poly[-1] == 0:
        poly.pop()
    return poly


def sum_of_squares(terms) -> list:
    """sum_k weight_k * q_k(w)^2 from [(weight, coefficients), ...]. Weights must be >= 0."""
    total: list = []
    for weight, polynomial in terms:
        if weight < 0:
            raise ValueError("a square carries a negative weight")
        if weight == 0:
            continue
        total = poly_add(total, poly_scale(poly_mul(polynomial, polynomial), weight))
    return total


def nonnegative_on_half_line(target: list, sigma0, sigma1) -> bool:
    """Verify `target(w) >= 0 for all w >= 0` from a Positivstellensatz certificate.

    A univariate polynomial is non-negative on [0, infinity) exactly when it can be written
    `sigma0(w) + w * sigma1(w)` with both parts sums of squares, so the certificate is complete:
    anything true has one, and anything with one is true. That is what makes this checkable rather
    than merely testable - no sampling, no tolerance, no root isolation.
    """
    reconstructed = poly_add(sum_of_squares(sigma0),
                             poly_mul([Fraction(0), Fraction(1)], sum_of_squares(sigma1)))
    return _trim(list(target)) == reconstructed


def _sizes(degree):
    m0 = degree // 2
    m1 = max(0, (degree - 1) // 2)
    return m0 + 1, m1 + 1


def _groups(n0, n1, width):
    """Which Gram cells feed each output coefficient. Cells partition by output degree."""
    table = {k: ([], []) for k in range(width)}
    for i in range(n0):
        for j in range(n0):
            table[i + j][0].append((i, j))
    for i in range(n1):
        for j in range(n1):
            table[i + j + 1][1].append((i, j))
    return table


def _numeric(target, n0, n1, width, margin=1e-3, tries=12):
    """Fit the coefficient identity with Gram matrices held strictly inside the PSD cone.

    G = a^T a + margin*I makes the interiority structural, which matters because the rounding that
    follows must not fall out of the cone: an optimum on the boundary does not survive being
    written down as a rational. With interiority structural the objective is a smooth least-squares
    fit and has an analytic gradient, where maximising a minimum eigenvalue directly is non-smooth
    and defeated L-BFGS on even the trivial target w.
    """
    goal = np.zeros(width)
    for i, value in enumerate(target):
        goal[i] = float(value)
    table = _groups(n0, n1, width)
    # Which output coefficient each Gram cell feeds, as flat index arrays.
    idx0 = np.empty(n0 * n0, dtype=np.int64)
    idx1 = np.empty(max(1, n1 * n1), dtype=np.int64)
    for k, (gc, hc) in table.items():
        for i, j in gc:
            idx0[i * n0 + j] = k
        for i, j in hc:
            idx1[i * n1 + j] = k
    eye0 = np.eye(n0) * margin
    eye1 = np.eye(n1) * margin

    def value_and_gradient(x):
        a = x[:n0 * n0].reshape(n0, n0)
        b = x[n0 * n0:].reshape(n1, n1)
        G = a.T @ a + eye0
        H = b.T @ b + eye1
        produced = (np.bincount(idx0, weights=G.ravel(), minlength=width)
                    + np.bincount(idx1, weights=H.ravel(), minlength=width))
        residual = produced - goal
        outer0 = (2.0 * residual)[idx0].reshape(n0, n0)
        outer1 = (2.0 * residual)[idx1].reshape(n1, n1)
        grad = np.concatenate([(a @ (outer0 + outer0.T)).ravel(),
                               (b @ (outer1 + outer1.T)).ravel()])
        return float(residual @ residual), grad

    for attempt in range(tries):
        rng = np.random.default_rng(attempt)
        x = rng.normal(scale=0.5, size=n0 * n0 + n1 * n1)
        result = minimize(value_and_gradient, x, jac=True, method="L-BFGS-B",
                          options={"maxiter": 40000, "maxfun": 80000, "ftol": 1e-20,
                                   "gtol": 1e-18})
        a = result.x[:n0 * n0].reshape(n0, n0)
        b = result.x[n0 * n0:].reshape(n1, n1)
        G = a.T @ a + eye0
        H = b.T @ b + eye1
        produced = (np.bincount(idx0, weights=G.ravel(), minlength=width)
                    + np.bincount(idx1, weights=H.ravel(), minlength=width))
        if np.max(np.abs(produced - goal)) < 1e-10:
            return G, H, table
    return None


def _psd_squares(gram, size):
    """Exact LDL of a rational PSD matrix into weighted squares; None if not semidefinite."""
    work = [[Fraction(v) for v in row] for row in gram]
    squares = []
    for k in range(size):
        pivot = max(range(k, size), key=lambda r: work[r][r])
        if work[pivot][pivot] < 0:
            return None
        if work[pivot][pivot] == 0:
            if any(work[r][c] != 0 for r in range(k, size) for c in range(k, size)):
                return None
            break
        if work[k][k] == 0:
            work[k], work[pivot] = work[pivot], work[k]
            for r in range(size):
                work[r][k], work[r][pivot] = work[r][pivot], work[r][k]
        head = work[k][k]
        vector = [Fraction(0)] * size
        vector[k] = Fraction(1)
        for c in range(k + 1, size):
            vector[c] = work[k][c] / head
        squares.append((head, vector))
        for r in range(k + 1, size):
            factor = work[r][k]
            if factor == 0:
                continue
            factor /= head
            for c in range(k + 1, size):
                work[r][c] -= factor * work[k][c]
    return squares


def extract(target, denominator=10 ** 12):
    """Return (sigma0, sigma1) proving target >= 0 on [0, infinity), or None."""
    poly = [Fraction(v) for v in target]
    while poly and poly[-1] == 0:
        poly.pop()
    if not poly:
        return [], []
    degree = len(poly) - 1
    n0, n1 = _sizes(degree)
    width = max(2 * (n0 - 1), 2 * (n1 - 1) + 1) + 1
    found = _numeric(poly, n0, n1, width)
    if found is None:
        return None
    G, H, table = found
    gram0 = [[Fraction(round(G[i, j] * denominator), denominator) for j in range(n0)]
             for i in range(n0)]
    gram1 = [[Fraction(round(H[i, j] * denominator), denominator) for j in range(n1)]
             for i in range(n1)]
    for grid in (gram0, gram1):
        n = len(grid)
        for i in range(n):
            for j in range(i + 1, n):
                mid = (grid[i][j] + grid[j][i]) / 2
                grid[i][j] = grid[j][i] = mid
    # Exact repair: every Gram cell belongs to exactly one output coefficient, so distributing
    # each deficit over its own group restores the identity without touching any other.
    for k, (gc, hc) in table.items():
        want = poly[k] if k < len(poly) else Fraction(0)
        have = sum(gram0[i][j] for i, j in gc) + sum(gram1[i][j] for i, j in hc)
        cells = len(gc) + len(hc)
        if cells == 0:
            if want != 0:
                return None
            continue
        shift = (want - have) / cells
        for i, j in gc:
            gram0[i][j] += shift
        for i, j in hc:
            gram1[i][j] += shift
    squares0 = _psd_squares(gram0, n0)
    squares1 = _psd_squares(gram1, n1)
    if squares0 is None or squares1 is None:
        return None
    sigma0 = [(w, v) for w, v in squares0 if w != 0]
    sigma1 = [(w, v) for w, v in squares1 if w != 0]
    if not nonnegative_on_half_line(poly, sigma0, sigma1):
        return None
    return sigma0, sigma1


def forward_from_tail(q0, q1, radius):
    """P(w) = -[q0(w-R)^2 + (w-R) q1(w-R)^2], plus the tail certificate in s."""
    shift = [-radius, Fraction(1)]
    left = _compose(q0, shift)
    right = _compose(q1, shift)
    tail = poly_add(poly_mul(left, left), poly_mul(shift, poly_mul(right, right)))
    return poly_scale(tail, Fraction(-1))


def _compose(poly, inner):
    out: list = []
    for coefficient in reversed(poly):
        out = poly_add(poly_mul(out, inner), [coefficient])
    return out


def laguerre_expand(poly, dimension, degree):
    """Exact coordinates of a polynomial in the Laguerre basis."""
    alpha = Fraction(dimension, 2) - 1
    rows = [laguerre(k, alpha) for k in range(degree + 1)]
    work = list(poly) + [Fraction(0)] * (degree + 1 - len(poly))
    coefficients = [Fraction(0)] * (degree + 1)
    for k in range(degree, -1, -1):
        value = work[k] / rows[k][k]
        coefficients[k] = value
        for i, entry in enumerate(rows[k]):
            work[i] -= value * entry
    if any(v != 0 for v in work[:degree + 1]):
        raise ValueError("Laguerre expansion left a residue")
    return coefficients, rows


def evaluate_candidate(dimension, q0, q1, radius, screen_top=400.0, screen_points=4000):
    forward = forward_from_tail(q0, q1, radius)
    degree = len(forward) - 1
    if degree < 0:
        return None
    at_zero = poly_eval(forward, Fraction(0))
    if at_zero <= 0:
        return None
    coefficients, rows = laguerre_expand(forward, dimension, degree)
    transform: list = []
    for index, (row, value) in enumerate(zip(rows, coefficients)):
        transform = poly_add(transform, poly_scale(row, value * (-1) ** index))
    transform_zero = poly_eval(transform, Fraction(0))
    if transform_zero <= 0:
        return None
    bound = ((float(radius) / (2.0 * math.pi)) ** (dimension / 2.0)) / (2.0 ** dimension) \
        * float(at_zero / transform_zero)
    grid = np.linspace(0.0, screen_top, screen_points)
    values = np.polyval(np.array([float(v) for v in transform])[::-1], grid)
    if float(values.min()) < -1e-12:
        return None
    if len(transform) > 1 and transform[-1] < 0:
        return None
    return bound, coefficients, forward, transform


def certify(dimension, q0, q1, radius):
    got = evaluate_candidate(dimension, q0, q1, radius)
    if got is None:
        return None
    bound, coefficients, forward, transform = got
    positive = extract(transform)
    if positive is None:
        return None
    return bound, coefficients, radius, positive, (q0, q1)


TRIALS = 30000
SEED = 11


def _draw(rng, low, high, denominators):
    return Fraction(int(rng.integers(low, high + 1)), int(rng.choice(denominators)))


def build_certificate(instance):
    dimension = instance["dimension"]
    ceiling = instance["two_term_certificate_bound"]
    rng = np.random.default_rng(SEED)
    denominators = [1, 2, 3]
    best = None
    for _ in range(TRIALS):
        left = [_draw(rng, -10, 10, denominators) for _ in range(int(rng.integers(1, 4)))]
        right = [_draw(rng, -10, 10, denominators) for _ in range(int(rng.integers(1, 4)))]
        radius = _draw(rng, max(2, dimension - 4), 6 * dimension, [1, 2])
        if radius <= 0:
            continue
        # The cheap pass rebuilds both polynomials exactly but only screens the transform on a grid;
        # the exact extraction, which is the expensive part, runs only on what survives and only on
        # what would improve the incumbent.
        cheap = evaluate_candidate(dimension, left, right, radius)
        if cheap is None or cheap[0] >= (best[0] if best else ceiling):
            continue
        found = certify(dimension, left, right, radius)
        if found and (best is None or found[0] < best[0]):
            best = found
    if best is None:
        raise RuntimeError("no certifiable candidate found in dimension %d" % dimension)
    _bound, coefficients, radius, positive, (left, right) = best
    return {
        "threshold": [radius.numerator, radius.denominator],
        "coefficients": [[c.numerator, c.denominator] for c in coefficients],
        "transform_nonnegative": _emit(positive),
        # The tail certificate needs no search: -f(R + s) was built as q0^2 + s*q1^2.
        "tail_nonpositive": {"sigma0": [_square(Fraction(1), left)],
                             "sigma1": [_square(Fraction(1), right)]},
    }


def _square(weight, polynomial):
    return {"weight": [weight.numerator, weight.denominator],
            "poly": [[v.numerator, v.denominator] for v in polynomial]}


def _emit(pair):
    sigma0, sigma1 = pair
    return {"sigma0": [_square(w, v) for w, v in sigma0],
            "sigma1": [_square(w, v) for w, v in sigma1]}
