"""Reference: turn a numerical SDP solution into an exact rational certificate.

Deliberately below the ceiling. This is the honest baseline procedure - solve the relaxation
numerically by alternating projections, round the result to rationals, repair the linear identity
exactly, and buy back positive semidefiniteness with a multiple of the identity - and each of those
four steps is done in the simplest way that works. A stronger submission can pick a better basis
for the budget, use a finer denominator, run a real interior-point method instead of Dykstra, or
repair feasibility without paying the full diagonal shift.

The repair rests on one fact about this algebra: for any reduced word `w`, `w^dagger w` is the
identity. So adding `epsilon * I` to `Q` adds `epsilon * |basis|` to the identity coefficient and
changes no other coefficient at all. Feasibility can therefore always be restored by raising the
bound, and never by breaking the operator identity.
"""
from __future__ import annotations

import itertools
import math
import sys
from fractions import Fraction
from pathlib import Path

import numpy as np
from scipy.optimize import minimize

# Same reason as the evaluator: this file is run by path. Resolve the sibling against this
# directory rather than against whatever sys.path happens to hold.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from algebra import dagger, is_positive_semidefinite, multiply  # noqa: E402


def word_groups(basis):
    """Which (i, j) cells contribute to each canonical word."""
    groups = {}
    for i, s in enumerate(basis):
        ds = dagger(s)
        for j, t in enumerate(basis):
            groups.setdefault(multiply(ds, t), []).append((i, j))
    return groups


def enumerate_words(settings, max_letters):
    """Every reduced word with at most `max_letters` letters per side, shortest first.

    The order matters because the budgets truncate this list. Sorting by total length puts the
    first level - the identity, every A_x, every B_y - at the front, and that prefix already
    produces every word the functionals use: s^dagger t with s = A_x and t = B_y is A_x B_y. A
    truncation that cut into it would leave the operator identity unsatisfiable for any Q at all,
    which is a defect in the reference rather than a hard instance.
    """
    def side(count):
        out = [()]
        for length in range(1, max_letters + 1):
            for candidate in itertools.product(range(count), repeat=length):
                if all(candidate[k] != candidate[k + 1] for k in range(length - 1)):
                    out.append(candidate)
        return out
    words = [(a, b) for a in side(settings[0]) for b in side(settings[1])]
    return sorted(words, key=lambda w: (len(w[0]) + len(w[1]), len(w[0]), w))


def _group_index(basis, groups):
    """Map every (i, j) cell to the index of the canonical word it contributes to.

    With this, a group sum is one `np.bincount` and the matrix `sum_g c_g C_g` is one fancy-index
    reshape, which is what makes an analytic gradient cheap enough to matter: L-BFGS without a
    gradient finite-differences every one of the |basis|^2 variables per step, and on the 16-word
    I3322 basis that alone was most of nine minutes.
    """
    size = len(basis)
    order = list(groups)
    position = {word: k for k, word in enumerate(order)}
    index = np.empty(size * size, dtype=np.int64)
    for word, cells in groups.items():
        for i, j in cells:
            index[i * size + j] = position[word]
    return order, index


def _factored_solution(functional, basis, groups, seed=0, restarts=3):
    """Minimise the bound over Q = R^T R, with the operator identity as a rising penalty.

    Writing Q as R^T R makes positive semidefiniteness structural, so the only thing left to
    enforce is the identity, and a quasi-Newton method walks it down far more accurately than
    alternating projections do near the cone boundary - 1e-7 from Tsirelson's bound on CHSH
    against 4e-2 for Dykstra on the same basis. Accuracy is what makes the certificate cheap: the
    diagonal shift that buys positive semidefiniteness back after rounding is charged straight to
    the bound, so a point accurate to 1e-9 costs about |basis| * 1e-9 and one accurate to 1e-2
    costs ten million times that.
    """
    size = len(basis)
    identity = ((), ())
    order, index = _group_index(basis, groups)
    count = len(order)
    target = np.zeros(count)
    for word, coefficient in functional.items():
        if word not in groups:
            raise KeyError("functional word %r is outside the products of this basis" % (word,))
        target[order.index(word)] = -float(coefficient)
    identity_slot = order.index(identity)
    # The identity coefficient is the objective, not a constraint; every other group is pinned.
    weightings = np.ones(count)
    weightings[identity_slot] = 0.0
    objective_direction = np.zeros(count)
    objective_direction[identity_slot] = 1.0

    def value_and_gradient(flat, weight):
        factor = flat.reshape(size, size)
        matrix = factor.T @ factor
        sums = np.bincount(index, weights=matrix.ravel(), minlength=count)
        residual = (sums - target) * weightings
        value = sums[identity_slot] + weight * float(residual @ residual)
        coefficients = objective_direction + 2.0 * weight * residual * weightings
        outer = coefficients[index].reshape(size, size)
        gradient = factor @ (outer + outer.T)
        return value, gradient.ravel()

    best = None
    for attempt in range(restarts):
        rng = np.random.default_rng(seed + attempt)
        flat = rng.normal(scale=0.5, size=size * size)
        for weight in (1e2, 1e4, 1e6, 1e8, 1e10, 1e12):
            result = minimize(value_and_gradient, flat, args=(weight,), jac=True,
                              method="L-BFGS-B",
                              options={"maxiter": 20000, "maxfun": 40000,
                                       "ftol": 1e-18, "gtol": 1e-16})
            flat = result.x
        factor = flat.reshape(size, size)
        matrix = factor.T @ factor
        sums = np.bincount(index, weights=matrix.ravel(), minlength=count)
        violation = float(np.max(np.abs((sums - target) * weightings)))
        if violation < 1e-7 and (best is None or sums[identity_slot] < best[0]):
            best = (sums[identity_slot], matrix)
    if best is None:
        return None
    return best[1]


def _numeric_solution(functional, basis, groups, bracket_iterations=3000,
                      settle_iterations=40000, tolerance=1e-11, margin=1e-4):
    """Dykstra alternating projection onto {affine identity} and {PSD}, bisecting on the bound.

    The reference is limited by this routine on purpose. Alternating projections converge
    sublinearly as the feasible point approaches the boundary of the positive-semidefinite cone,
    and the optimum is on that boundary: measured on CHSH, forty thousand iterations still leave a
    residual of 7e-5 at the true bound while reaching 1e-10 a hundredth above it. So the bisection
    accepts a bound only when the projection actually settles, which stops it short of the optimum
    by an amount nobody chose. A submission that runs a real interior-point method, or that
    exploits the structure of this particular affine set, is expected to beat it - that is the
    headroom the task is scored on.
    """
    size = len(basis)
    identity = ((), ())
    target = {word: 0.0 for word in groups}
    for word, coefficient in functional.items():
        if word not in groups:
            raise KeyError("functional word %r is outside the products of this basis" % (word,))
        target[word] = -float(coefficient)

    def project_affine(matrix, beta):
        out = matrix.copy()
        for word, cells in groups.items():
            want = beta if word == identity else target[word]
            have = sum(out[i, j] for i, j in cells)
            shift = (want - have) / len(cells)
            for i, j in cells:
                out[i, j] += shift
        return out

    def project_psd(matrix):
        symmetric = (matrix + matrix.T) / 2.0
        values, vectors = np.linalg.eigh(symmetric)
        return (vectors * np.clip(values, 0.0, None)) @ vectors.T

    def settle(beta, iterations):
        current = np.zeros((size, size))
        pa = np.zeros((size, size))
        pb = np.zeros((size, size))
        for _ in range(iterations):
            stepped = project_affine(current + pa, beta)
            pa = current + pa - stepped
            projected = project_psd(stepped + pb)
            pb = stepped + pb - projected
            if np.max(np.abs(projected - current)) < 1e-15:
                current = projected
                break
            current = projected
        affine = project_affine(current, beta)
        residual = max(np.max(np.abs(affine - current)),
                       -min(0.0, float(np.linalg.eigvalsh((current + current.T) / 2).min())))
        return current, residual

    low = 0.0
    high = float(sum(abs(v) for v in functional.values())) * size + 1.0
    for _ in range(30):
        middle = (low + high) / 2.0
        _point, residual = settle(middle, bracket_iterations)
        if residual < tolerance:
            high = middle
        else:
            low = middle
    relaxed = high + margin * max(1.0, abs(high))
    point, residual = settle(relaxed, settle_iterations)
    if residual >= tolerance:
        raise RuntimeError("alternating projection did not settle at the bracketed bound")
    return project_affine(point, relaxed)


def rationalise(numeric, basis, groups, functional, denominator):
    """Round, repair the identity exactly, then shift the diagonal until PSD holds."""
    size = len(basis)
    identity = ((), ())
    matrix = [[Fraction(round(numeric[i, j] * denominator), denominator) for j in range(size)]
              for i in range(size)]
    for i in range(size):
        for j in range(i + 1, size):
            averaged = (matrix[i][j] + matrix[j][i]) / 2
            matrix[i][j] = matrix[j][i] = averaged
    # Exact repair of every constrained word. The identity group is the diagonal and is left
    # alone: its sum is the bound, which is the objective rather than a constraint.
    required = {word: Fraction(-coefficient) for word, coefficient in functional.items()}
    for word, cells in groups.items():
        if word == identity:
            continue
        have = sum(matrix[i][j] for i, j in cells)
        shift = (required.get(word, Fraction(0)) - have) / len(cells)
        if shift == 0:
            continue
        for i, j in cells:
            matrix[i][j] += shift
    # Symmetry survives the repair because the cell set of every word is closed under transpose:
    # if s^dagger t = w then t^dagger s = w^dagger, and the two groups get the same shift only
    # when w is self-adjoint. Re-symmetrise rather than assume it.
    for i in range(size):
        for j in range(i + 1, size):
            if matrix[i][j] != matrix[j][i]:
                averaged = (matrix[i][j] + matrix[j][i]) / 2
                matrix[i][j] = matrix[j][i] = averaged
    for word, cells in groups.items():
        if word == identity:
            continue
        have = sum(matrix[i][j] for i, j in cells)
        shift = (required.get(word, Fraction(0)) - have) / len(cells)
        if shift != 0:
            for i, j in cells:
                matrix[i][j] += shift
    def shifted_by(epsilon):
        return [[matrix[i][j] + (epsilon if i == j else 0) for j in range(size)]
                for i in range(size)]

    if is_positive_semidefinite(matrix, size):
        return matrix
    # Double until it holds, then bisect back down. Doubling alone can overpay by a factor of two,
    # and the diagonal shift is charged straight to the bound: |basis| * epsilon is added to the
    # identity coefficient, so on CHSH an overshoot of 4e-3 was most of the reference's distance
    # from Tsirelson's bound.
    high = Fraction(1, denominator)
    for _ in range(200):
        if is_positive_semidefinite(shifted_by(high), size):
            break
        high *= 2
    else:
        raise RuntimeError("could not restore positive semidefiniteness")
    low = Fraction(0)
    for _ in range(60):
        middle = (low + high) / 2
        if middle.denominator > 10 ** 12:
            break
        if is_positive_semidefinite(shifted_by(middle), size):
            high = middle
        else:
            low = middle
    return shifted_by(high)


def exact_ldl_squares(matrix, size):
    """Write a rational PSD matrix as an exact sum of weighted squares.

    Q = sum_k d_k w_k w_k^T with every d_k >= 0, by symmetric elimination. The elimination is done
    once here, where it is the reference's own cost, rather than in the oracle where an adversarial
    submission could make it unbounded. Raises if the matrix is not semidefinite.
    """
    work = [[Fraction(value) for value in row] for row in matrix]
    squares = []
    for k in range(size):
        pivot_row = max(range(k, size), key=lambda r: work[r][r])
        if work[pivot_row][pivot_row] < 0:
            raise ValueError("matrix is not positive semidefinite")
        if work[pivot_row][pivot_row] == 0:
            if any(work[r][c] != 0 for r in range(k, size) for c in range(k, size)):
                raise ValueError("matrix is not positive semidefinite")
            break
        # Pivoting would permute the basis; instead take the pivot in place when it is usable and
        # fall back to the largest only if the diagonal entry here has died.
        if work[k][k] == 0:
            work[k], work[pivot_row] = work[pivot_row], work[k]
            for r in range(size):
                work[r][k], work[r][pivot_row] = work[r][pivot_row], work[r][k]
        pivot = work[k][k]
        vector = [Fraction(0)] * size
        vector[k] = Fraction(1)
        for c in range(k + 1, size):
            vector[c] = work[k][c] / pivot
        # Clear denominators: write v = (g / L) * n with n an integer vector of content 1, and
        # move (g / L)^2 into the weight. Every product weight * v_i * v_j is unchanged. Without
        # this the LDL vectors carry ratios of leading minors and blow through the oracle's caps.
        multiplier = 1
        for entry in vector:
            multiplier = multiplier * entry.denominator // math.gcd(multiplier, entry.denominator)
        integral = [int(entry * multiplier) for entry in vector]
        content = 0
        for entry in integral:
            content = math.gcd(content, abs(entry))
        if content > 1:
            integral = [entry // content for entry in integral]
        scale = Fraction(content if content else 1, multiplier)
        squares.append((pivot * scale * scale, [Fraction(entry) for entry in integral]))
        for r in range(k + 1, size):
            factor = work[r][k]
            if factor == 0:
                continue
            factor = factor / pivot
            for c in range(k + 1, size):
                work[r][c] -= factor * work[k][c]
    return squares


def _rational(value):
    return [value.numerator, value.denominator]


def build(instance, denominator=10 ** 9, max_letters=1, margin=1e-4):
    basis = enumerate_words(instance["settings"], max_letters)[: instance["max_basis"]]
    groups = word_groups(basis)
    numeric = _factored_solution(instance["functional"], basis, groups)
    if numeric is None:
        # Alternating projections always return something feasible, just far from optimal. Keeping
        # them as the fallback means a hard basis yields a weak certificate rather than none.
        numeric = _numeric_solution(instance["functional"], basis, groups, margin=margin)
    matrix = rationalise(numeric, basis, groups, instance["functional"], denominator)
    squares = exact_ldl_squares(matrix, len(basis))
    return {
        "basis": [[list(word[0]), list(word[1])] for word in basis],
        "squares": [{"weight": _rational(weight),
                     "vector": [_rational(entry) for entry in vector]}
                    for weight, vector in squares if weight != 0],
    }


def build_certificate(instance):
    """Candidate-shaped entry point: the reference as a submission.

    The basis is the shortest-first enumeration truncated to the budget, which is the obvious
    choice and not the good one - arXiv:2607.14755 shows the moment-selection landscape for this
    functional is non-monotone, so spending a budget on the shortest words is exactly the greedy
    strategy their exhaustive enumeration beats. Choosing the basis is left as headroom on purpose.
    """
    settings = instance["settings"]
    functional = {(tuple(word[0]), tuple(word[1])) if isinstance(word, (list, tuple)) else word:
                  coefficient for word, coefficient in instance["functional"].items()}
    internal = {
        "settings": tuple(settings),
        "functional": functional,
        "max_basis": instance["max_basis"],
    }
    level_one = 1 + settings[0] + settings[1]
    single_letter = (1 + settings[0]) * (1 + settings[1])
    letters = 1 if instance["max_basis"] <= single_letter else 2
    if instance["max_basis"] < level_one:
        raise ValueError("budget below the first level")
    return build(internal, max_letters=letters)
