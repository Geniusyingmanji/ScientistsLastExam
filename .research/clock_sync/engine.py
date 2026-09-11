"""Prototype world, campaign and oracle for ClockSyncInversion.

Clocks are affine, C_j(t) = t + theta_j + s_j t, node 0 is true time.  A two-way exchange i -> j -> i
at true time t returns (T1, T2, T3, T4): T1 on i's clock at send, T2 on j's clock at receipt, T3 on
j's clock at reply, T4 on i's clock at receipt.  A one-way delay is the direction's propagation p
plus queueing, which is zero with probability pi(t) and exponential otherwise; every timestamp
carries Gaussian jitter with its node's sigma.  The offset of node j at time t is x_j(t) = theta_j
+ s_j t.  The oracle's identifiable set is the set of offset trajectories consistent with infinite
noiseless data, the published lower bounds on propagation and the published asymmetry bound on
calibrated links; it is a polytope in (dtheta, ds), and its width at an epoch is two LPs.
"""
import math

import numpy as np
from scipy.optimize import linprog

SPACING = 0.25          # seconds between probes in one exchange
TURNAROUND = 20e-6      # seconds between T2 and T3 on the responder's clock
PI_MIN = 0.05


class Campaign:
    def __init__(self, world, budget, horizon, shift=0):
        self.w = world
        self.budget, self.horizon = budget, horizon
        self.used, self.now = 0, 0.0
        self.rng = np.random.default_rng(world["seed"] + 17 + 7919 * shift)

    def wait(self, seconds):
        seconds = float(seconds)
        if not seconds >= 0 or self.now + seconds > self.horizon:
            raise RuntimeError("wait past the horizon")
        self.now += seconds

    def exchange(self, i, j, n):
        w = self.w
        key = (min(i, j), max(i, j))
        if key not in w["links"] or n < 1:
            raise ValueError("no such link")
        if self.used + n > self.budget:
            raise RuntimeError("probe budget exhausted")
        t = self.now + SPACING * np.arange(n)
        if t[-1] > self.horizon:
            raise RuntimeError("exchange past the horizon")
        self.used += n
        self.now = float(t[-1] + SPACING)
        df = w["p"][(i, j)] + self._queue((i, j), t)
        t2 = t + df
        t3 = t2 + TURNAROUND
        db = w["p"][(j, i)] + self._queue((j, i), t3)
        t4 = t3 + db
        si, sj = w["sigma"][i], w["sigma"][j]
        r = self.rng
        T1 = clock(w, i, t) + r.normal(0, si, n)
        T2 = clock(w, j, t2) + r.normal(0, sj, n)
        T3 = clock(w, j, t3) + r.normal(0, sj, n)
        T4 = clock(w, i, t4) + r.normal(0, si, n)
        return np.stack([T1, T2, T3, T4], axis=1)

    def _queue(self, d, t):
        q = self.w["queue"][d]
        load = 0.5 * (1 + np.sin(2 * math.pi * t / q["period"] + q["phase"]))
        pi = np.maximum(PI_MIN, q["pi0"] * (1 - 0.9 * load))
        mu = q["mu0"] * (0.3 + load)
        empty = self.rng.random(len(t)) < pi
        return np.where(empty, 0.0, self.rng.exponential(1.0, len(t)) * mu)


def offset(w, j, t):
    """x_j(t), including a frequency step if the world has one."""
    x = w["theta"][j] + w["skew"][j] * t
    st = w.get("step")
    if st and st["node"] == j:
        x = x + st["ds"] * np.maximum(0.0, t - st["at"])
    jp = w.get("jump")
    if jp and jp["node"] == j:
        x = x + jp["size"] * (t > jp["at"])
    return x


def clock(w, j, t):
    return t + offset(w, j, t)


def make_world(spec):
    rng = np.random.default_rng(spec["seed"])
    N = spec["nodes"]
    edges = set()
    for j in range(1, N):
        edges.add((int(rng.integers(0, j)), j))
    while len(edges) < N - 1 + spec["extra"]:
        a, b = sorted(rng.choice(N, 2, replace=False).tolist())
        edges.add((a, b))
    links = sorted(edges)
    calibrated = [links[k] for k in spec.get("calibrated", [])]
    alpha = spec.get("alpha", 1e-6)
    p, lower, queue = {}, {}, {}
    for (a, b) in links:
        base = rng.uniform(50e-6, 2e-3)
        asym = rng.choice([-1, 1]) * rng.uniform(0.6, 1.0) * alpha if (a, b) in calibrated else rng.uniform(-200e-6, 200e-6)
        p[(a, b)], p[(b, a)] = base + asym / 2, base - asym / 2
        for d in ((a, b), (b, a)):
            lower[d] = p[d] - rng.uniform(0, 30e-6) * spec.get("slack", 1.0)
            queue[d] = {"pi0": rng.uniform(0.06, 0.5), "mu0": rng.uniform(20e-6, 2e-3),
                        "period": rng.uniform(1800, 7200), "phase": rng.uniform(0, 2 * math.pi)}
    theta = np.concatenate([[0.0], rng.uniform(-3e-3, 3e-3, N - 1)])
    skew = np.concatenate([[0.0], rng.uniform(-30e-6, 30e-6, N - 1)])
    sigma = np.where(rng.random(N) < spec.get("soft", 0.25), 2e-6, 0.2e-6)
    if "soft_nodes" in spec:
        sigma = np.full(N, 0.2e-6)
        sigma[list(spec["soft_nodes"])] = 2e-6
    sigma[0] = 0.2e-6
    w = {"seed": spec["seed"], "N": N, "links": set(links), "link_list": links, "calibrated": calibrated,
         "alpha": alpha, "p": p, "lower": lower, "queue": queue, "theta": theta, "skew": skew,
         "sigma": sigma, "kind": "supported"}
    fault = spec.get("fault")
    if fault == "miscalibrated":
        a, b = calibrated[spec.get("fault_link", 0)]
        extra = spec.get("fault_size", 12e-6)
        p[(a, b)] += extra / 2
        p[(b, a)] -= extra / 2
        w["kind"] = "miscalibrated"
    elif fault == "step":
        w["step"] = {"node": spec.get("fault_node", N - 1), "at": spec.get("fault_at", 0.5) * spec["horizon"],
                     "ds": spec.get("fault_size", 2e-9)}
        w["kind"] = "step"
    elif fault == "jump":
        w["jump"] = {"node": spec.get("fault_node", N - 1), "at": spec.get("fault_at", 0.5) * spec["horizon"],
                     "size": spec.get("fault_size", 10e-6)}
        w["kind"] = "jump"
    return w


def public(w, spec):
    return {"nodes": w["N"], "links": [list(l) for l in w["link_list"]],
            "lower_bound_s": {f"{a}->{b}": w["lower"][(a, b)] for (a, b) in w["lower"]},
            "calibrated_links": [list(l) for l in w["calibrated"]], "asymmetry_bound_s": w["alpha"],
            "timestamp_sigma_s": [float(s) for s in w["sigma"]], "empty_queue_probability_min": PI_MIN,
            "probe_budget": spec["budget"], "horizon_s": spec["horizon"], "probe_spacing_s": SPACING,
            "epochs_s": [0.0, spec["horizon"]]}


def identifiable(w, horizon):
    """Widths of the infinite-data identifiable set of x_j(E) for E in {0, horizon}, j >= 1."""
    N = w["N"]
    nv = 2 * (N - 1)          # dtheta_1.., ds_1..

    def row(j, t, sign):
        r = np.zeros(nv)
        if j > 0:
            r[j - 1] = sign
            r[N - 1 + j - 1] = sign * t
        return r

    A, b = [], []
    for (i, j) in w["p"]:
        for t in (0.0, horizon):
            A.append(row(j, t, 1) + row(i, t, -1))
            b.append(w["p"][(i, j)] - w["lower"][(i, j)])
    for (i, j) in w["calibrated"]:
        a = w["p"][(i, j)] - w["p"][(j, i)]
        for t in (0.0, horizon):
            d = row(j, t, 1) + row(i, t, -1)
            A.append(d); b.append((a + w["alpha"]) / 2)
            A.append(-d); b.append(-(a - w["alpha"]) / 2)
    A, b = np.array(A), np.array(b)
    widths = np.zeros((N, 2))
    for j in range(1, N):
        for k, t in enumerate((0.0, horizon)):
            c = row(j, t, 1)
            lo = linprog(c, A_ub=A, b_ub=b, bounds=[(None, None)] * nv, method="highs")
            hi = linprog(-c, A_ub=A, b_ub=b, bounds=[(None, None)] * nv, method="highs")
            assert lo.status == 0 and hi.status == 0, (lo.message, hi.message)
            widths[j, k] = -hi.fun - lo.fun
    return widths


def truth(w, horizon):
    return np.array([[offset(w, j, 0.0), offset(w, j, horizon)] for j in range(w["N"])])


def score(w, answer, horizon, widths):
    """1 for a refusal where the model fails; else mean sharpness, -1 if any interval misses."""
    if w["kind"] != "supported":
        return (1.0, "refuse-ok") if answer is None else (0.0, "FD")
    if answer is None:
        return 0.0, "declined"
    x = truth(w, horizon)
    sharp = []
    for j in range(1, w["N"]):
        for k in range(2):
            lo, hi = answer[j][k]
            if not lo <= x[j, k] <= hi:
                return -1.0, f"FD node {j} epoch {k} miss {min(abs(x[j,k]-lo), abs(x[j,k]-hi))*1e6:.2f}us"
            sharp.append(min(1.0, widths[j, k] / max(hi - lo, 1e-15)))
    return float(np.mean(sharp)), "claim"


def detectability(w, horizon, grid=49):
    """Smallest uniform relaxation eps (seconds) under which some affine clocks and constant
    propagations reproduce every true floor trajectory within eps, respect every lower bound and
    every calibrated asymmetry bound within eps.  Zero for a supported world; a refusal world is
    detectable with infinite data exactly when eps > 0."""
    N = w["N"]
    dirs = sorted(w["p"])
    pidx = {d: 2 * (N - 1) + k for k, d in enumerate(dirs)}
    nv = 2 * (N - 1) + len(dirs) + 1           # ..., eps
    ts = np.linspace(0.0, horizon, grid)
    A, b = [], []

    def u(d, t):
        r = np.zeros(nv)
        for node, sgn in ((d[1], 1.0), (d[0], -1.0)):
            if node > 0:
                r[node - 1] += sgn
                r[N - 1 + node - 1] += sgn * t
        return r

    for d in dirs:
        floor = offset(w, d[1], ts) - offset(w, d[0], ts) + w["p"][d]
        for t, f in zip(ts, floor):
            r = u(d, t); r[pidx[d]] = 1.0; r[-1] = -1.0
            A.append(r); b.append(f)
            r = -u(d, t); r[pidx[d]] = -1.0; r[-1] = -1.0
            A.append(r); b.append(-f)
        r = np.zeros(nv); r[pidx[d]] = -1.0; r[-1] = -1.0
        A.append(r); b.append(-w["lower"][d])
    for (i, j) in w["calibrated"]:
        for s in (1, -1):
            r = np.zeros(nv); r[pidx[(i, j)]] = s; r[pidx[(j, i)]] = -s; r[-1] = -1.0
            A.append(r); b.append(w["alpha"])
    c = np.zeros(nv); c[-1] = 1.0
    res = linprog(c, A_ub=np.array(A), b_ub=np.array(b), bounds=[(None, None)] * (nv - 1) + [(0, None)], method="highs")
    assert res.status == 0, res.message
    return res.fun


def detectability_sigma(w, horizon, grid=49):
    """Smallest kappa such that affine clocks and constant propagations reproduce every true floor
    trajectory within kappa * sigma_pair of its direction, with the published lower bounds and
    calibrated asymmetry bounds held exactly.  Zero for a supported world."""
    N = w["N"]
    dirs = sorted(w["p"])
    pidx = {d: 2 * (N - 1) + k for k, d in enumerate(dirs)}
    nv = 2 * (N - 1) + len(dirs) + 1
    ts = np.linspace(0.0, horizon, grid)
    A, b = [], []

    def u(d, t):
        r = np.zeros(nv)
        for node, sgn in ((d[1], 1.0), (d[0], -1.0)):
            if node > 0:
                r[node - 1] += sgn
                r[N - 1 + node - 1] += sgn * t
        return r

    for d in dirs:
        sp = math.hypot(w["sigma"][d[0]], w["sigma"][d[1]])
        floor = offset(w, d[1], ts) - offset(w, d[0], ts) + w["p"][d]
        for t, f in zip(ts, floor):
            r = u(d, t); r[pidx[d]] = 1.0; r[-1] = -sp
            A.append(r); b.append(f)
            r = -u(d, t); r[pidx[d]] = -1.0; r[-1] = -sp
            A.append(r); b.append(-f)
    for (i, j) in w["calibrated"]:
        for s in (1, -1):
            r = np.zeros(nv); r[pidx[(i, j)]] = s; r[pidx[(j, i)]] = -s
            A.append(r); b.append(w["alpha"])
    bounds = [(None, None)] * (2 * (N - 1)) + [(w["lower"][d], None) for d in dirs] + [(0, None)]
    c = np.zeros(nv); c[-1] = 1.0
    res = linprog(c, A_ub=np.array(A), b_ub=np.array(b), bounds=bounds, method="highs")
    assert res.status == 0, res.message
    return res.fun
