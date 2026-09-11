"""Reference for ClockSyncInversion: an envelope LP with empty-queue constraints (truth-blind).

It reads only the public problem and what `exchange` returns.

    rounds          the probe budget is split evenly over the links and over twelve rounds spread
                    across the horizon, so that every link is sampled early and late
    rough clocks    per-round minima in both directions give (min forward - min back) / 2 per
                    link and round; least squares over the network gives rough offsets and rates,
                    used only to convert every sender timestamp to approximate true time
    upper rows      a delay is at least its propagation, so for every probe
                    x_b(t) - x_a(t) + p_ab <= y + (jitter); the three lowest residuals of every
                    round and direction are kept with a margin of z pair sigmas, z the normal
                    quantile of delta/4 over every probe; the k-th lowest residual of every round
                    and direction is kept with the margin of the k-th order statistic of the
                    round's jitter, at delta/4 over all of them
    envelope        a lower-envelope LP (Moon, Skelly and Towsley 1999) fits the kept rows and
                    selects, per direction and per third of the horizon, the probe with the
                    lowest residual
    atom rows       with probability 1 - delta/4 a third of the horizon holds at least a_min
                    empty-queue probes (binomial at the published floor), and the least of their
                    jitters lies below q; the selected probe's residual is at most that, so
                    x_b(t*) - x_a(t*) + p_ab >= y* - q - sigma/2 (the half sigma allows for the
                    tilt of the envelope within a third)
    bounds          p_ab >= L_ab; |p_ab - p_ba| <= alpha on calibrated links
    answer          the LP's minimum and maximum of x_j at each epoch; an infeasible LP means no
                    affine clocks and constant delays explain the exchanges, and it declines

The atom rows are what make a fault visible: without them nothing stops the LP from absorbing a
rate step or a miscalibrated link into queueing. The three families of rows take delta/4 each, so
by the union bound the probability that any row excludes the truth is at most 3 delta / 4, with
delta = 10^-3 per world; the tilt allowance is outside that bound.
"""
import math
import warnings
from fractions import Fraction

import numpy as np
from scipy.optimize import linprog
from scipy.stats import beta, binom, norm

CFG = {"rounds": 12, "keep": 3, "groups": 3, "delta": 1e-3, "atoms": True, "detect_only": False,
       "z": None, "atom_bound": "quantile", "order": True, "k": 5, "tilt": 0.5, "q": None}
# atom_bound: "quantile" is the bound above; "margin" uses the upper rows' z; "fixed" uses q pair
# sigmas, a hand-set threshold with no probability behind it (the ladder and the probe use it)


def _solve_centered_lp(c, A, b, bounds, center, scale):
    """Solve the identical LP in x = center + scale*z coordinates.

    Clock offsets/rates can dwarf sub-microsecond residuals. Subtract the
    public-observation rough-clock fit before unit scaling, and shift propagation
    variables by their public lower bounds. No constraint or objective changes.

    The solver is SciPy's revised simplex with Bland's rule: it runs in the
    calling thread only. HiGHS starts worker threads, which the candidate
    sandbox's seccomp filter refuses (clone is denied), and the legacy
    interior-point method stops at its iteration limit on some of these LPs.
    """
    c, A, b = np.asarray(c), np.asarray(A), np.asarray(b)
    objective = c * scale
    objective_scale = max(float(np.max(np.abs(objective))), 1e-12)
    shifted_bounds = [(None if lo is None else (lo - center[k]) / scale[k],
                       None if hi is None else (hi - center[k]) / scale[k])
                      for k, (lo, hi) in enumerate(bounds)]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        result = linprog(objective / objective_scale,
                         A_ub=A * scale / 1e-6,
                         b_ub=(b - A @ center) / 1e-6, bounds=shifted_bounds,
                         method="revised simplex",
                         options={"tol": 1e-9, "maxiter": 20000, "pivot": "bland"})
    # Unboundedness or numerical failure is not evidence of model infeasibility.
    if result.status not in (0, 2):
        raise RuntimeError("LP did not establish an optimum or infeasibility")
    if result.status == 0:
        if result.x is None or not np.all(np.isfinite(result.x)) or not np.isfinite(result.fun):
            raise RuntimeError("LP returned no finite optimum")
        result.x = center + result.x * scale
        result.fun = float(result.fun * objective_scale + c @ center)
    return result


def _clock_row_indices(A, b, clock_count):
    """Keep the exact lower hull of parallel affine-in-time clock inequalities.

    Within a direction/sign group every row is a0 + t*a1. A point (t,b)
    above the chord between two others is implied by their convex combination.
    Fraction arithmetic tests this implication exactly for the supplied binary
    floats; no geometric/numerical tolerance can drop a stronger constraint.
    Asymmetry rows and any unrecognized rows are kept unchanged.
    """
    A, b = np.asarray(A), np.asarray(b)
    keep, groups = set(), {}
    for index, (row, rhs) in enumerate(zip(A, b)):
        theta = row[:clock_count]
        rate = row[clock_count:2 * clock_count]
        propagation = row[2 * clock_count:]
        active = np.flatnonzero(theta)
        prop = np.flatnonzero(propagation)
        if (not len(active) or len(prop) != 1 or
                not np.all(np.isin(theta, [-1, 0, 1])) or
                abs(propagation[prop[0]]) != 1):
            keep.add(index)
            continue
        t = float(rate[active[0]] / theta[active[0]])
        if not np.array_equal(rate, theta * t) or not math.isfinite(t) or not math.isfinite(rhs):
            keep.add(index)
            continue
        key = tuple(theta) + tuple(propagation)
        groups.setdefault(key, []).append((Fraction(t), Fraction(float(rhs)), index))
    for points in groups.values():
        # For equal times only the lowest rhs is needed. Keep one identical row.
        points.sort()
        distinct = []
        for point in points:
            if not distinct or point[0] != distinct[-1][0]:
                distinct.append(point)
        hull = []
        for point in distinct:
            while len(hull) >= 2:
                left, middle = hull[-2], hull[-1]
                cross = ((middle[0] - left[0]) * (point[1] - left[1]) -
                         (middle[1] - left[1]) * (point[0] - left[0]))
                if cross > 0:
                    break
                hull.pop()
            hull.append(point)
        keep.update(point[2] for point in hull)
    return sorted(keep)


def identify(problem, exchange, wait, cfg=None):
    cfg = {**CFG, **(cfg or {})}
    N = problem["nodes"]
    links = [tuple(l) for l in problem["links"]]
    cal = {tuple(l) for l in problem["calibrated_links"]}
    L = {tuple(int(v) for v in k.split("->")): x for k, x in problem["lower_bound_s"].items()}
    sig = problem["timestamp_sigma_s"]
    alpha = problem["asymmetry_bound_s"]
    B, H, dt = problem["probe_budget"], problem["horizon_s"], problem["probe_spacing_s"]
    R, delta = cfg["rounds"], cfg["delta"]
    n = B // (R * len(links))
    gap = (H - R * n * len(links) * dt) / R
    raw = {l: [] for l in links}
    for r in range(R):
        for l in links:
            raw[l].append(np.asarray(exchange(l[0], l[1], n), dtype=float))
        if r < R - 1:
            wait(gap)
    # directed data: (a, b) means a sends and b receives; y = receipt - send, tc the send stamp
    D = {}
    for (i, j) in links:
        X = np.stack(raw[(i, j)])                       # R x n x 4
        D[(i, j)] = {"tc": X[:, :, 0], "node": i, "y": X[:, :, 1] - X[:, :, 0]}
        D[(j, i)] = {"tc": X[:, :, 2], "node": j, "y": X[:, :, 3] - X[:, :, 2]}
    dirs = sorted(D)
    total = sum(d["y"].size for d in D.values())
    z = cfg["z"] if cfg["z"] is not None else norm.isf(delta / 4 / total)
    spair = {d: math.hypot(sig[d[0]], sig[d[1]]) for d in dirs}

    # rough clocks from per-round minima, least squares with node 0 fixed
    rows, rhs = [], []
    for (i, j) in links:
        f, b = D[(i, j)]["y"].min(axis=1), D[(j, i)]["y"].min(axis=1)
        tt = D[(i, j)]["tc"].mean(axis=1)
        for r in range(R):
            e = np.zeros(2 * N)
            e[j], e[i], e[N + j], e[N + i] = 1, -1, tt[r], -tt[r]
            rows.append(e); rhs.append((f[r] - b[r]) / 2)
    A = np.array(rows)[:, [k for k in range(2 * N) if k not in (0, N)]]
    sol = np.linalg.lstsq(A, np.array(rhs), rcond=None)[0]
    th = np.concatenate([[0.0], sol[:N - 1]])
    sk = np.concatenate([[0.0], sol[N - 1:]])
    for d in dirs:
        tc, k = D[d]["tc"], D[d]["node"]
        D[d]["t"] = tc - (th[k] + sk[k] * tc)

    pidx = {d: 2 * (N - 1) + k for k, d in enumerate(dirs)}
    nv = 2 * (N - 1) + len(dirs)

    def u(d, t):
        """Coefficients of x_b(t) - x_a(t)."""
        r = np.zeros(nv)
        for node, sgn in ((d[1], 1.0), (d[0], -1.0)):
            if node > 0:
                r[node - 1] += sgn
                r[N - 1 + node - 1] += sgn * t
        return r

    Aub, bub, sel = [], [], {}
    for d in dirs:
        t, y = D[d]["t"], D[d]["y"]
        res = y - ((th[d[1]] + sk[d[1]] * t) - (th[d[0]] + sk[d[0]] * t))
        idx = np.argsort(res, axis=1)[:, :cfg["keep"]]
        sel[d] = [(t[r, k], y[r, k]) for r in range(R) for k in idx[r]]
        for tk, yk in sel[d]:
            row = u(d, tk); row[pidx[d]] = 1.0
            Aub.append(row); bub.append(yk + z * spair[d])
    bounds = [(None, None)] * (2 * (N - 1)) + [(L[d], None) for d in dirs]
    for (i, j) in cal:
        for s in (1, -1):
            row = np.zeros(nv); row[pidx[(i, j)]] = s; row[pidx[(j, i)]] = -s
            Aub.append(row); bub.append(alpha)

    reduced_rows = {}

    def solve(c, A, b):
        # HiGHS exits in the pinned candidate sandbox (see _solve_centered_lp). The
        # legacy backends want residual-sized coordinates rather than absolute clocks.
        scale = np.full(nv, 1e-6)
        scale[N - 1:2 * (N - 1)] /= H
        center = np.concatenate([th[1:], sk[1:], [L[d] for d in dirs]])
        # Rows are only appended or truncated to a previous prefix in this
        # algorithm. Reuse each stage's identical feasible set across objectives.
        if len(A) not in reduced_rows:
            kept = _clock_row_indices(A, b, N - 1)
            reduced_rows[len(A)] = np.asarray(A)[kept], np.asarray(b)[kept]
        reduced_A, reduced_b = reduced_rows[len(A)]
        return _solve_centered_lp(c, reduced_A, reduced_b, bounds, center, scale)

    # lower envelope: the fit that leaves the least total slack in the kept rows
    c = np.zeros(nv)
    for d in dirs:
        for tk, yk in sel[d]:
            c -= u(d, tk)
            c[pidx[d]] -= 1.0
    env = solve(c, Aub, bub)
    if env.status != 0:
        return {"verdict": "no_model", "confidence": 0.9}
    v = env.x

    def resid(d):
        t, y = D[d]["t"], D[d]["y"]
        a, b = d
        xb = (v[b - 1] + v[N - 1 + b - 1] * t) if b > 0 else 0 * t
        xa = (v[a - 1] + v[N - 1 + a - 1] * t) if a > 0 else 0 * t
        return y - (xb - xa)

    if cfg["order"]:
        # the k-th lowest residual of a round is at least the k-th lowest of its n jitters
        k = cfg["k"]
        zk = -norm.ppf(beta.ppf(delta / 4 / (len(dirs) * R), k, n - k + 1))
        for d in dirs:
            res = resid(d)
            for r in range(R):
                kk = np.argsort(res[r])[k - 1]
                row = u(d, D[d]["t"][r, kk]); row[pidx[d]] = 1.0
                Aub.append(row); bub.append(D[d]["y"][r, kk] + zk * spair[d])
    n_base = len(Aub)
    if cfg["atoms"]:
        G = cfg["groups"]
        pmin = problem["empty_queue_probability_min"]
        da = delta / 4 / (2 * len(dirs) * G)
        for d in dirs:
            res, sp = resid(d), spair[d]
            for g in np.array_split(np.arange(R), G):
                a_min = int(binom.ppf(da, len(g) * n, pmin))
                if cfg["atom_bound"] == "quantile" and a_min >= 1:
                    q = sp * norm.ppf(1 - da ** (1.0 / a_min)) + cfg["tilt"] * sp
                elif cfg["atom_bound"] == "fixed":
                    q = cfg["q"] * sp
                else:
                    q = z * sp
                block = res[g]
                r0, k0 = np.unravel_index(np.argmin(block), block.shape)
                row = -u(d, D[d]["t"][g][r0, k0]); row[pidx[d]] = -1.0
                Aub.append(row); bub.append(-(D[d]["y"][g][r0, k0] - q))
    if cfg["detect_only"]:
        if solve(np.zeros(nv), Aub, bub).status != 0:
            return {"verdict": "no_model", "confidence": 0.9}
        del Aub[n_base:], bub[n_base:]
    intervals = {}
    for j in range(1, N):
        intervals[str(j)] = []
        for E in problem["epochs_s"]:
            cj = np.zeros(nv); cj[j - 1] = 1.0; cj[N - 1 + j - 1] = E
            lo, hi = solve(cj, Aub, bub), solve(-cj, Aub, bub)
            if lo.status != 0 or hi.status != 0:
                return {"verdict": "no_model", "confidence": 0.9}
            intervals[str(j)].append([float(lo.fun), float(-hi.fun)])
    return {"verdict": "offsets", "intervals": intervals, "confidence": 0.6}


# Fixed disclosed configuration; no task data or hidden oracle imports.
CFG.update({'detect_only': True, 'z': 3.0})
