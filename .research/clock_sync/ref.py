"""Prototype reference for ClockSyncInversion (truth-blind: uses only the public problem, exchange, wait).

Rounds spread over the horizon; rough skews from per-round minima; the lowest residuals of every
round kept as upper constraints (delay >= propagation, jitter margin by a family-wise normal
quantile); a lower-envelope LP (Moon et al.) to select each direction's global-minimum probe,
which the empty-queue floor guarantees is an empty-queue probe; propagation variables per
direction, calibrated asymmetry constraints, and group-wise empty-queue constraints that make a
non-affine clock infeasible.  Intervals are the LP's min and max of x_j at each epoch; an
infeasible LP is a refusal.
"""
import math

import numpy as np
from scipy.optimize import linprog
from scipy.stats import beta, binom, norm

CFG = {"rounds": 12, "keep": 3, "groups": 3, "delta": 1e-3, "atoms": True, "group_atoms": True, "detect_only": False, "z": None, "atom_bound": "quantile", "upper": "order", "k": 5}


def identify(problem, exchange, wait, cfg=None):
    cfg = {**CFG, **(cfg or {})}
    N = problem["nodes"]
    links = [tuple(l) for l in problem["links"]]
    cal = {tuple(l) for l in problem["calibrated_links"]}
    L = {tuple(int(v) for v in k.split("->")): x for k, x in problem["lower_bound_s"].items()}
    sig = problem["timestamp_sigma_s"]
    alpha = problem["asymmetry_bound_s"]
    B, H, dt = problem["probe_budget"], problem["horizon_s"], problem["probe_spacing_s"]
    R = cfg["rounds"]
    n = B // (R * len(links))
    busy = n * len(links) * dt
    gap = (H - R * busy) / R
    raw = {l: [] for l in links}
    for r in range(R):
        for l in links:
            raw[l].append(exchange(l[0], l[1], n))
        if r < R - 1:
            wait(gap)
    # directed data: d=(a,b) means a sends, b receives; tc on the sender's... use T1 for fwd, T3 for back
    D = {}
    for (i, j) in links:
        X = np.stack(raw[(i, j)])                       # R x n x 4
        D[(i, j)] = {"tc": X[:, :, 0], "node": i, "y": X[:, :, 1] - X[:, :, 0]}
        D[(j, i)] = {"tc": X[:, :, 2], "node": j, "y": X[:, :, 3] - X[:, :, 2]}
    total = sum(d["y"].size for d in D.values())
    z = cfg["z"] if cfg["z"] is not None else norm.isf(cfg["delta"] / total)
    m = {d: z * math.hypot(sig[d[0]], sig[d[1]]) for d in D}

    # rough node trajectories from per-round minima: u_ij ~ (min fwd - min back)/2, least squares
    rows, rhs_t = [], []
    for (i, j) in links:
        f, b = D[(i, j)]["y"].min(axis=1), D[(j, i)]["y"].min(axis=1)
        tt = D[(i, j)]["tc"].mean(axis=1)
        for r in range(R):
            e = np.zeros(2 * N)
            e[j], e[i], e[N + j], e[N + i] = 1, -1, tt[r], -tt[r]
            rows.append(e); rhs_t.append((f[r] - b[r]) / 2)
    A = np.array(rows)[:, [k for k in range(2 * N) if k not in (0, N)]]
    sol = np.linalg.lstsq(A, np.array(rhs_t), rcond=None)[0]
    th = np.concatenate([[0.0], sol[:N - 1]])
    sk = np.concatenate([[0.0], sol[N - 1:]])

    def time_of(d):
        tc = D[d]["tc"]
        k = D[d]["node"]
        return tc - (th[k] + sk[k] * tc)

    for d in D:
        D[d]["t"] = time_of(d)

    dirs = sorted(D)
    pidx = {d: 2 * (N - 1) + k for k, d in enumerate(dirs)}
    nv = 2 * (N - 1) + len(dirs)

    def u(d, t):
        """Coefficient row for x_b(t) - x_a(t)."""
        a, b = d
        r = np.zeros(nv)
        for node, sgn in ((b, 1.0), (a, -1.0)):
            if node > 0:
                r[node - 1] += sgn
                r[N - 1 + node - 1] += sgn * t
        return r

    Aub, bub = [], []
    sel = {}
    for d in dirs:
        t, y = D[d]["t"], D[d]["y"]
        res = y - ((th[d[1]] + sk[d[1]] * t) - (th[d[0]] + sk[d[0]] * t))
        idx = np.argsort(res, axis=1)[:, :cfg["keep"]]
        sel[d] = [(t[r, k], y[r, k]) for r in range(R) for k in idx[r]]
        for tk, yk in sel[d]:
            row = u(d, tk); row[pidx[d]] = 1.0
            Aub.append(row); bub.append(yk + m[d])
    bounds = [(None, None)] * (2 * (N - 1)) + [(L[d], None) for d in dirs]
    for (i, j) in cal:
        for s in (1, -1):
            row = np.zeros(nv); row[pidx[(i, j)]] = s; row[pidx[(j, i)]] = -s
            Aub.append(row); bub.append(alpha)

    def solve(c, A, b):
        return linprog(c, A_ub=np.array(A), b_ub=np.array(b), bounds=bounds, method="highs")

    # lower-envelope fit: minimise total slack of the kept constraints
    c = np.zeros(nv)
    for d in dirs:
        for tk, yk in sel[d]:
            c -= u(d, tk)
            c[pidx[d]] -= 1.0
    env = solve(c, Aub, bub)
    if env.status != 0:
        return None
    v = env.x

    def resid(d):
        t, y = D[d]["t"], D[d]["y"]
        a, b = d
        xb = (v[b - 1] + v[N - 1 + b - 1] * t) if b > 0 else 0 * t
        xa = (v[a - 1] + v[N - 1 + a - 1] * t) if a > 0 else 0 * t
        return y - (xb - xa)

    if cfg["upper"] == "order":
        # within one round's block of one direction the k-th smallest residual is at least the k-th
        # smallest timestamp noise, whose lower quantile is a Beta order statistic
        ks = cfg["k"] if isinstance(cfg["k"], (list, tuple)) else [cfg["k"]]
        du = cfg["delta"] / (2 * len(dirs) * R * len(ks))
        for k in ks:
            zk = -norm.ppf(beta.ppf(du, k, n - k + 1))
            for d in dirs:
                res = resid(d)
                sp = math.hypot(sig[d[0]], sig[d[1]])
                for r in range(R):
                    kk = np.argsort(res[r])[k - 1]
                    row = u(d, D[d]["t"][r, kk]); row[pidx[d]] = 1.0
                    Aub.append(row); bub.append(D[d]["y"][r, kk] + zk * sp)
    n_base = len(Aub)
    if cfg["atoms"]:
        G = cfg["groups"] if cfg["group_atoms"] else 1
        pmin = problem["empty_queue_probability_min"]
        da = cfg["delta"] / (2 * len(dirs) * G)
        for d in dirs:
            res = resid(d)
            sp = math.hypot(sig[d[0]], sig[d[1]])
            for g in np.array_split(np.arange(R), G):
                ng = len(g) * n
                # at least a_min empty-queue probes with probability 1 - da; the smallest of their
                # noises is below q with probability 1 - da; the group minimum is at most that
                a_min = int(binom.ppf(da, ng, pmin))
                if cfg["atom_bound"] == "quantile" and a_min >= 1:
                    q = sp * norm.ppf(1 - da ** (1.0 / a_min)) + 0.5 * sp
                else:
                    q = m[d]
                block = res[g]
                r0, k0 = np.unravel_index(np.argmin(block), block.shape)
                tk, yk = D[d]["t"][g][r0, k0], D[d]["y"][g][r0, k0]
                row = -u(d, tk); row[pidx[d]] = -1.0
                Aub.append(row); bub.append(-(yk - q))
    if cfg["detect_only"]:
        if solve(np.zeros(nv), Aub, bub).status != 0:
            return None
        del Aub[n_base:], bub[n_base:]
    out = {}
    for j in range(1, N):
        out[j] = []
        for E in problem["epochs_s"]:
            cj = np.zeros(nv); cj[j - 1] = 1.0; cj[N - 1 + j - 1] = E
            lo, hi = solve(cj, Aub, bub), solve(-cj, Aub, bub)
            if lo.status != 0 or hi.status != 0:
                return None
            out[j].append([lo.fun, -hi.fun])
    return out
