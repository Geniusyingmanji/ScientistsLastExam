"""Hidden oracle for ClockSyncInversion.

A small network of computers keeps time with free-running clocks. Node 0 keeps true time; every
other clock runs at its own constant rate from its own starting offset. The candidate may run
two-way timestamp exchanges over the network's links, under a probe budget and a time horizon,
and must then bound the offset of every clock at the start and at the end of the horizon. When
the exchanges cannot have come from the published model, the right answer is to decline.

The score is exact. With unlimited data the exchanges pin every relative clock rate, but not the
offsets: a one-way delay is propagation plus queueing, and no timing measurement separates a
clock offset from a delay asymmetry (Lundelius and Lynch 1984; Freris, Graham and Kumar 2011).
What remains is the published bounds: a lower bound on every propagation delay, and a bound on
the asymmetry of the links marked calibrated. The oracle knows the true clocks and delays and
solves two linear programs per clock for the set of offsets that unlimited noiseless data could
not rule out. A submitted interval that misses the true offset is a false discovery; one that
covers it scores the ratio of that identifiable width to its own width, capped at 1.

What makes it hard:

    offset versus      the data identify offsets only up to delay asymmetry; an interval
    asymmetry          narrower than the published bounds allow is a guess, and a guess that
                       misses costs a world
    queueing           most probes wait in a queue; only the ones that find it empty carry the
                       propagation floor, at least one in twenty at the worst time of day, and
                       jitter on every timestamp hides which ones did
    drift              clocks drift by up to 30 ppm, 0.43 s over the horizon, so where the
                       probes sit in time decides how well rates and end offsets are pinned
    faults that        in some worlds a clock changes rate or jumps partway through, or a link
    look like noise    marked calibrated is not; the exchanges then fit no affine clocks and
                       constant delays within the bounds, and the right answer is to decline;
                       the violations are a few microseconds against the same jitter, visible
                       only jointly across links and time
"""
from __future__ import annotations

import math

import numpy as np
from scipy.optimize import linprog

PROBE_BUDGET = 20_000
HORIZON = 14_400.0
SPACING = 0.25          # seconds between the starts of two probes of one exchange call
TURNAROUND = 20e-6      # seconds between T2 and T3 on the responder
PI_MIN = 0.05           # the floor of the empty-queue probability, published
ALPHA = 1e-6            # the asymmetry bound on calibrated links, published
SIGMA_HARD, SIGMA_SOFT = 0.2e-6, 2e-6


# ---- the world ---------------------------------------------------------------------------------
def offset(world, j, t):
    """x_j(t) = C_j(t) - t, including a rate step or a jump if the world has one."""
    t = np.asarray(t, dtype=float)
    x = world["theta"][j] + world["skew"][j] * t
    step = world.get("step")
    if step and step["node"] == j:
        x = x + step["ds"] * np.maximum(0.0, t - step["at"])
    jump = world.get("jump")
    if jump and jump["node"] == j:
        x = x + jump["size"] * (t > jump["at"])
    return x


def clock(world, j, t):
    return np.asarray(t, dtype=float) + offset(world, j, t)


def make_world(spec):
    """Every structural draw comes from the world's own seed, in a fixed order."""
    rng = np.random.default_rng(spec["seed"])
    N = spec["nodes"]
    edges = set()
    for j in range(1, N):
        edges.add((int(rng.integers(0, j)), j))
    while len(edges) < N - 1 + spec["extra"]:
        a, b = sorted(rng.choice(N, 2, replace=False).tolist())
        edges.add((a, b))
    links = sorted(edges)
    calibrated = [links[k] for k in spec["calibrated"]]
    p, lower, queue = {}, {}, {}
    for (a, b) in links:
        # The uncalibrated asymmetry is at most 200 us, split equally across the
        # two directions. Keep both one-way propagations in the stated 50 us..
        # 2 ms range. A 50 us midpoint used to create negative physical delays.
        base = rng.uniform(150e-6, 1.9e-3)
        if (a, b) in calibrated:
            asym = rng.choice([-1, 1]) * rng.uniform(0.6, 1.0) * ALPHA
        else:
            asym = rng.uniform(-200e-6, 200e-6)
        p[(a, b)], p[(b, a)] = base + asym / 2, base - asym / 2
        for d in ((a, b), (b, a)):
            lower[d] = p[d] - rng.uniform(0, 30e-6)
            queue[d] = {"pi0": rng.uniform(0.06, 0.5), "mu0": rng.uniform(20e-6, 2e-3),
                        "period": rng.uniform(1800, 7200), "phase": rng.uniform(0, 2 * math.pi)}
    theta = np.concatenate([[0.0], rng.uniform(-3e-3, 3e-3, N - 1)])
    skew = np.concatenate([[0.0], rng.uniform(-30e-6, 30e-6, N - 1)])
    soft = rng.random(N) < 0.25
    if "soft_nodes" in spec:
        soft = np.zeros(N, dtype=bool)
        soft[list(spec["soft_nodes"])] = True
    sigma = np.where(soft, SIGMA_SOFT, SIGMA_HARD)
    sigma[0] = SIGMA_HARD
    world = {"N": N, "links": links, "calibrated": calibrated, "p": p, "lower": lower,
             "queue": queue, "theta": theta, "skew": skew, "sigma": sigma, "fault": ""}
    fault = spec.get("fault")
    if fault == "miscalibrated":
        # the link keeps its published asymmetry bound and its lower bounds, which were drawn
        # for the calibrated delays; its true asymmetry is moved by fault_size
        a, b = calibrated[spec["fault_link"]]
        p[(a, b)] += spec["fault_size"] / 2
        p[(b, a)] -= spec["fault_size"] / 2
    elif fault == "step":
        world["step"] = {"node": spec["fault_node"], "at": spec["fault_at"] * HORIZON, "ds": spec["fault_size"]}
    elif fault == "jump":
        world["jump"] = {"node": spec["fault_node"], "at": spec["fault_at"] * HORIZON, "size": spec["fault_size"]}
    if fault:
        world["fault"] = fault
    world["kind"] = "unsupported" if fault else "supported"
    return world


def _u_row(N, nv, d, t):
    """Coefficients of x_b(t) - x_a(t) for direction d = (a, b) over (theta_1.., s_1.., ...)."""
    r = np.zeros(nv)
    for node, sign in ((d[1], 1.0), (d[0], -1.0)):
        if node > 0:
            r[node - 1] += sign
            r[N - 1 + node - 1] += sign * t
    return r


def identifiable_widths(world):
    """The width of the set of x_j that unlimited noiseless data cannot rule out, j = 1..N-1.

    Unlimited data give every direction's floor y(t) = x_b(t) - x_a(t) + p_ab exactly. Another
    explanation x' = x + delta with constant propagations p' must reproduce every floor, so every
    delta_b - delta_a is constant in time, and with delta_0 = 0 on a connected network every
    delta_j is a constant: rates are identified and only offsets are not. What bounds them is
    p'_ab = p_ab - (delta_b - delta_a) >= L_ab and, on a calibrated link, |p'_ab - p'_ba| <= alpha.
    The set is the same at every epoch."""
    N = world["N"]
    nv = N - 1

    def diff(d):
        r = np.zeros(nv)
        if d[1] > 0:
            r[d[1] - 1] += 1.0
        if d[0] > 0:
            r[d[0] - 1] -= 1.0
        return r

    A, b = [], []
    for d, pd in world["p"].items():
        A.append(diff(d)); b.append(pd - world["lower"][d])
    for (i, j) in world["calibrated"]:
        a = world["p"][(i, j)] - world["p"][(j, i)]
        A.append(diff((i, j))); b.append((a + ALPHA) / 2)
        A.append(-diff((i, j))); b.append(-(a - ALPHA) / 2)
    A, b = np.array(A), np.array(b)
    widths = np.zeros(N)
    for j in range(1, N):
        c = np.zeros(nv); c[j - 1] = 1.0
        lo = linprog(c, A_ub=A, b_ub=b, bounds=[(None, None)] * nv, method="highs")
        hi = linprog(-c, A_ub=A, b_ub=b, bounds=[(None, None)] * nv, method="highs")
        if lo.status != 0 or hi.status != 0:
            raise RuntimeError("identifiable set is empty: %s %s" % (lo.message, hi.message))
        widths[j] = -hi.fun - lo.fun
    return widths


def detectability(world, grid=49):
    """kappa*: the smallest kappa for which affine clocks and constant propagations reproduce
    every true floor trajectory within kappa times its direction's pair jitter, with the published
    lower bounds and calibrated asymmetry bounds held exactly. Zero exactly when the world is
    supported; the larger it is, the fewer empty-queue probes it takes to see the fault."""
    N = world["N"]
    dirs = sorted(world["p"])
    pidx = {d: 2 * (N - 1) + k for k, d in enumerate(dirs)}
    nv = 2 * (N - 1) + len(dirs) + 1
    ts = np.linspace(0.0, HORIZON, grid)
    A, b = [], []
    for d in dirs:
        sp = math.hypot(world["sigma"][d[0]], world["sigma"][d[1]])
        floor = offset(world, d[1], ts) - offset(world, d[0], ts) + world["p"][d]
        for t, f in zip(ts, floor):
            r = _u_row(N, nv, d, t); r[pidx[d]] = 1.0; r[-1] = -sp
            A.append(r); b.append(f)
            r = -_u_row(N, nv, d, t); r[pidx[d]] = -1.0; r[-1] = -sp
            A.append(r); b.append(-f)
    for (i, j) in world["calibrated"]:
        for s in (1, -1):
            r = np.zeros(nv); r[pidx[(i, j)]] = s; r[pidx[(j, i)]] = -s
            A.append(r); b.append(ALPHA)
    bounds = [(None, None)] * (2 * (N - 1)) + [(world["lower"][d], None) for d in dirs] + [(0, None)]
    c = np.zeros(nv); c[-1] = 1.0
    res = linprog(c, A_ub=np.array(A), b_ub=np.array(b), bounds=bounds, method="highs")
    if res.status != 0:
        raise RuntimeError(res.message)
    return float(res.fun)


# ---- the campaign ------------------------------------------------------------------------------
def _integer(value, low, high, what):
    if isinstance(value, bool) or not isinstance(value, (int, np.integer)):
        raise ValueError("%s must be an integer" % what)
    value = int(value)
    if not low <= value <= high:
        raise ValueError("%s must lie in %d..%d" % (what, low, high))
    return value


class _Bench:
    """The candidate's only access to the network. The candidate receives the two closures, not
    this object, so the ledger and the clock of the campaign are out of its reach."""

    def __init__(self, world, run_seed):
        self.world = world
        self.budget, self.horizon = PROBE_BUDGET, HORIZON
        self.used, self.now = 0, 0.0
        self.violated = False
        self.rng = np.random.default_rng(run_seed)

    def _queue(self, d, t):
        q = self.world["queue"][d]
        load = 0.5 * (1 + np.sin(2 * math.pi * t / q["period"] + q["phase"]))
        pi = np.maximum(PI_MIN, q["pi0"] * (1 - 0.9 * load))
        mu = q["mu0"] * (0.3 + load)
        empty = self.rng.random(len(t)) < pi
        return np.where(empty, 0.0, self.rng.exponential(1.0, len(t)) * mu)

    def oracle(self):
        state, w = self, self.world
        N = w["N"]
        linked = set(w["links"])

        def exchange(i, j, n):
            i = _integer(i, 0, N - 1, "a node")
            j = _integer(j, 0, N - 1, "a node")
            n = _integer(n, 1, PROBE_BUDGET, "the number of probes")
            if (min(i, j), max(i, j)) not in linked or i == j:
                raise ValueError("no link between %d and %d" % (i, j))
            t = state.now + SPACING * np.arange(n)
            if state.used + n > state.budget:
                state.violated = True
                raise RuntimeError("probe budget exhausted")
            if t[-1] > state.horizon:
                state.violated = True
                raise RuntimeError("exchange past the horizon")
            state.used += n
            state.now = float(t[-1] + SPACING)
            t2 = t + w["p"][(i, j)] + state._queue((i, j), t)
            t3 = t2 + TURNAROUND
            t4 = t3 + w["p"][(j, i)] + state._queue((j, i), t3)
            si, sj, r = w["sigma"][i], w["sigma"][j], state.rng
            return np.stack([clock(w, i, t) + r.normal(0, si, n), clock(w, j, t2) + r.normal(0, sj, n),
                             clock(w, j, t3) + r.normal(0, sj, n), clock(w, i, t4) + r.normal(0, si, n)], axis=1)

        def wait(seconds):
            if isinstance(seconds, bool) or not isinstance(seconds, (int, float, np.integer, np.floating)):
                raise ValueError("seconds must be a number")
            seconds = float(seconds)
            if not math.isfinite(seconds) or seconds < 0:
                raise ValueError("seconds must be finite and non-negative")
            if state.now + seconds > state.horizon:
                state.violated = True
                raise RuntimeError("wait past the horizon")
            state.now += seconds

        return exchange, wait


# ---- the problem and the answer ----------------------------------------------------------------
PUBLIC_PROBLEM = {
    "clock_model": "node 0 keeps true time; every other node j reads C_j(t) = t + theta_j + s_j t "
                   "at true time t, with theta_j and s_j unknown constants; its offset is x_j(t) = "
                   "C_j(t) - t",
    "delay_model": "a message from a to b takes p_ab + Q, where p_ab is a constant propagation "
                   "delay with p_ab >= lower_bound_s['a->b'] and Q >= 0 is queueing; in every "
                   "direction and at every moment Q = 0 with probability at least "
                   "empty_queue_probability_min, independently from probe to probe; on a link in "
                   "calibrated_links, |p_ab - p_ba| <= asymmetry_bound_s",
    "timestamp_model": "every timestamp node j writes is its clock reading plus independent "
                       "Gaussian noise of standard deviation timestamp_sigma_s[j]",
    "exchange_model": "exchange(i, j, n) runs n two-way exchanges over the link between i and j, "
                      "starting at the current time and probe_spacing_s apart: i writes T1 and "
                      "sends, j writes T2 on receipt and T3 when it replies, i writes T4 on "
                      "receipt; it returns an n x 4 array of (T1, T2, T3, T4) and advances the "
                      "time by n * probe_spacing_s; wait(seconds) advances the time; time starts "
                      "at 0 and may not pass horizon_s, and at most probe_budget exchanges may be "
                      "run in all",
    "answer_format": "verdict offsets with intervals, a mapping from every node j in 1..nodes-1 "
                     "to [[lo, hi] at epochs_s[0], [lo, hi] at epochs_s[1]] bounding x_j at those "
                     "true times, in seconds; or verdict no_model when the exchanges cannot come "
                     "from the model above",
}


def public_problem(world):
    problem = dict(PUBLIC_PROBLEM)
    problem.update({
        "nodes": world["N"],
        "links": [list(l) for l in world["links"]],
        "lower_bound_s": {"%d->%d" % d: float(world["lower"][d]) for d in sorted(world["lower"])},
        "calibrated_links": [list(l) for l in world["calibrated"]],
        "asymmetry_bound_s": ALPHA,
        "timestamp_sigma_s": [float(s) for s in world["sigma"]],
        "empty_queue_probability_min": PI_MIN,
        "probe_budget": PROBE_BUDGET,
        "horizon_s": HORIZON,
        "probe_spacing_s": SPACING,
        "epochs_s": [0.0, HORIZON],
    })
    return problem


def _finite(value, what):
    if isinstance(value, bool) or not isinstance(value, (int, float, np.integer, np.floating)):
        raise ValueError("%s must be a number" % what)
    value = float(value)
    if not math.isfinite(value):
        raise ValueError("%s must be finite" % what)
    return value


def _validate_submission(submission, N):
    if not isinstance(submission, dict):
        raise ValueError("submission must be a mapping")
    confidence = float(np.clip(_finite(submission.get("confidence", 0.0), "confidence"), 0.0, 1.0))
    if submission.get("abstain", False) is True:
        return None, confidence
    verdict = submission.get("verdict")
    if verdict == "no_model":
        return None, confidence
    if verdict != "offsets":
        raise ValueError("verdict must be 'offsets' or 'no_model'")
    intervals = submission.get("intervals")
    if not isinstance(intervals, dict):
        raise ValueError("intervals must be a mapping from node to two intervals")
    out = {}
    for key, pair in intervals.items():
        if isinstance(key, str) and key.isdigit():
            key = int(key)
        j = _integer(key, 1, N - 1, "a node")
        if j in out:
            raise ValueError("node %d given twice" % j)
        if not isinstance(pair, (list, tuple, np.ndarray)) or len(pair) != 2:
            raise ValueError("every node needs one interval per epoch")
        rows = []
        for iv in pair:
            if not isinstance(iv, (list, tuple, np.ndarray)) or len(iv) != 2:
                raise ValueError("an interval is [lo, hi]")
            lo, hi = _finite(iv[0], "lo"), _finite(iv[1], "hi")
            if lo > hi:
                raise ValueError("an interval needs lo <= hi")
            rows.append((lo, hi))
        out[j] = rows
    if sorted(out) != list(range(1, N)):
        raise ValueError("intervals must cover every node 1..%d" % (N - 1))
    return out, confidence


def _metrics(world, intervals):
    row = {"covered": False, "sharpness": 0.0, "mechanism_score": 0.0, "false_discovery": False,
           "correct_refusal": False}
    refusal_world = world["kind"] == "unsupported"
    if intervals is None:
        row.update({"mechanism_score": 1.0 if refusal_world else 0.0, "correct_refusal": refusal_world})
        return row
    if refusal_world:
        # no clocks of the model produced these exchanges, so every claim is a false discovery;
        # it scores zero where declining would have scored one
        row["false_discovery"] = True
        return row
    sharp = []
    for j in range(1, world["N"]):
        for k, epoch in enumerate((0.0, HORIZON)):
            lo, hi = intervals[j][k]
            truth = float(offset(world, j, epoch))
            if not lo <= truth <= hi:
                row.update({"false_discovery": True, "mechanism_score": -1.0})
                return row
            sharp.append(min(1.0, world["widths"][j] / max(hi - lo, 1e-15)))
    s = float(np.mean(sharp))
    row.update({"covered": True, "sharpness": s, "mechanism_score": s})
    return row


# ---- the worlds --------------------------------------------------------------------------------
# `seed` draws the network, the clocks and the delays; `run_seed` draws the campaign's queueing and
# jitter. Unsupported worlds carry their fault: a rate step of ds (s/s) or a jump of size (s) at
# fault_at times the horizon on fault_node, or a calibrated link whose asymmetry is off by size.
def _w(name, seed, run_seed, nodes, extra, calibrated, **more):
    return dict(name=name, seed=seed, run_seed=run_seed, nodes=nodes, extra=extra, calibrated=calibrated, **more)


DEVELOPMENT_WORLDS = (
    _w("dev-01", 101, 81500101, 5, 2, [0, 1]),
    _w("dev-02", 102, 81500102, 6, 3, [0, 2, 4]),
    _w("dev-03", 103, 81500103, 6, 2, [1]),
    _w("dev-04", 104, 81500104, 7, 3, [0, 3, 5]),
    _w("dev-05", 105, 81500105, 7, 4, [2, 4]),
    _w("dev-06", 106, 81500106, 8, 4, [0, 1, 5, 7]),
    _w("dev-07", 111, 81500107, 6, 3, []),
    _w("dev-08", 107, 81500108, 6, 3, [0, 2], fault="step", fault_node=1, fault_at=0.5, fault_size=3e-9, soft_nodes=[4]),
    _w("dev-09", 108, 81500109, 7, 3, [1, 3], fault="step", fault_node=6, fault_at=0.5, fault_size=-3e-9),
    _w("dev-10", 109, 81500110, 6, 3, [0, 1, 2, 3], fault="miscalibrated", fault_link=0, fault_size=40e-6, soft_nodes=[3, 5]),
    _w("dev-11", 110, 81500111, 7, 4, [0, 2, 3, 5], fault="miscalibrated", fault_link=0, fault_size=60e-6, soft_nodes=[3, 5]),
    _w("dev-12", 112, 81500112, 7, 3, [0, 2], fault="jump", fault_node=6, fault_at=0.4, fault_size=10e-6),
)

HELDOUT_WORLDS = (
    _w("held-01", 201, 92600201, 6, 3, [0, 1, 3]),
    _w("held-02", 202, 92600202, 7, 3, [0, 2, 4]),
    _w("held-03", 203, 92600203, 8, 5, [0, 2, 4, 6]),
    _w("held-04", 204, 92600204, 5, 2, [0, 1]),
    _w("held-05", 205, 92600205, 7, 3, [0, 3], fault="step", fault_node=6, fault_at=0.5, fault_size=2.5e-9),
    _w("held-06", 206, 92600206, 6, 3, [0, 1, 2], fault="miscalibrated", fault_link=2, fault_size=60e-6, soft_nodes=[4]),
)

_WORLDS = {}


def _world(spec):
    key = (spec["name"], spec["seed"])
    if key not in _WORLDS:
        world = make_world(spec)
        world["widths"] = identifiable_widths(world) if world["kind"] == "supported" else None
        _WORLDS[key] = world
    return _WORLDS[key]


ROW_KEYS = ("covered", "sharpness", "mechanism_score", "false_discovery", "correct_refusal")


def _evaluate_world(identify, spec, split, index):
    world = _world(spec)
    bench = _Bench(world, spec["run_seed"])
    base = {"split": split, "world_index": int(index), "kind": world["kind"], "probes_used": 0}
    try:
        # A world is an independent experiment, including the split boundary.
        # Keep callbacks within this world in one session, but never let global
        # state or /tmp from an earlier world reveal its position in the suite.
        if (split != "development" or index > 0) and hasattr(identify, "reset_session"):
            identify.reset_session()
        exchange, wait = bench.oracle()
        submission = identify(public_problem(world), exchange, wait)
        intervals, confidence = _validate_submission(submission, world["N"])
        if bench.violated:
            raise RuntimeError("probe budget or horizon exceeded")
        metrics = _metrics(world, intervals)
        target = max(metrics["mechanism_score"], 0.0)
        row = dict(base)
        row.update({key: metrics[key] for key in ROW_KEYS})
        row.update({
            "valid": True,
            "abstained": intervals is None,
            "confidence": round(confidence, 6),
            "confidence_calibration_score": round(1.0 - (confidence - target) ** 2, 6),
            "probes_used": bench.used,
        })
        row["mechanism_score"] = round(float(row["mechanism_score"]), 6)
        row["sharpness"] = round(float(row["sharpness"]), 6)
        return row
    except Exception as exc:  # noqa: BLE001 - a bad candidate scores zero, it does not crash this
        row = dict(base)
        row.update({key: (0.0 if key in ("sharpness", "mechanism_score") else False) for key in ROW_KEYS})
        row.update({
            "valid": False,
            "reason": "%s: %s" % (type(exc).__name__, exc),
            "abstained": True,
            "confidence": 0.0,
            "confidence_calibration_score": 0.0,
            "probes_used": bench.used,
        })
        return row


def _split_summary(records):
    supported = [r for r in records if r["kind"] == "supported"]
    unsupported = [r for r in records if r["kind"] == "unsupported"]
    raw = float(np.mean([r["mechanism_score"] for r in records]))
    always_abstain = len(unsupported) / len(records)
    normalized = float(np.clip((raw - always_abstain) / (1.0 - always_abstain), 0.0, 1.0))
    false_count = sum(bool(r["false_discovery"]) for r in records)
    claim_count = sum(not r["abstained"] for r in records)
    refusal_count = sum(bool(r["correct_refusal"]) for r in unsupported)
    supported_claim_count = sum(not r["abstained"] for r in supported)
    return {
        "normalized_mechanism": normalized,
        "raw_mechanism": raw,
        "interval_sharpness": float(np.mean([r["sharpness"] for r in supported])),
        "false_discovery_rate": false_count / claim_count if claim_count else 0.0,
        "false_claim_world_rate": false_count / len(records),
        "false_discovery_count": false_count,
        "claim_count": claim_count,
        "correct_refusal_rate": refusal_count / len(unsupported),
        "correct_refusal_count": refusal_count,
        "unsupported_count": len(unsupported),
        "discovery_coverage": supported_claim_count / len(supported),
        "supported_claim_count": supported_claim_count,
        "supported_count": len(supported),
        "confidence_calibration": float(np.mean([r["confidence_calibration_score"] for r in records])),
        "mean_probes_used": float(np.mean([r["probes_used"] for r in records])),
        "valid_count": sum(bool(r["valid"]) for r in records),
        "world_count": len(records),
    }


def evaluate(identify):
    development = [_evaluate_world(identify, spec, "development", index)
                   for index, spec in enumerate(DEVELOPMENT_WORLDS)]
    heldout = [_evaluate_world(identify, spec, "heldout", index)
               for index, spec in enumerate(HELDOUT_WORLDS)]
    dev = _split_summary(development)
    held = _split_summary(heldout)
    valid = 1.0 if dev["valid_count"] > 0 else 0.0
    result = {
        "combined_score": dev["normalized_mechanism"] if valid else 0.0,
        "valid": valid,
        "feasibility_rate": dev["valid_count"] / dev["world_count"],
        "raw_score": dev["normalized_mechanism"] if valid else 0.0,
        "development_mechanism_score": dev["normalized_mechanism"],
        "development_raw_mechanism": dev["raw_mechanism"],
        "development_interval_sharpness": dev["interval_sharpness"],
        "development_false_discovery_rate": dev["false_discovery_rate"],
        "development_correct_refusal_rate": dev["correct_refusal_rate"],
        "development_discovery_coverage": dev["discovery_coverage"],
        "development_confidence_calibration": dev["confidence_calibration"],
        "development_mean_probes_used": dev["mean_probes_used"],
        # Evaluator-only: the sealed split is removed from the search-visible metric view by the
        # visibility contract, so a searcher cannot steer on it.
        "heldout_mechanism_score": held["normalized_mechanism"],
        "heldout_interval_sharpness": held["interval_sharpness"],
        "heldout_false_discovery_rate": held["false_discovery_rate"],
        "heldout_correct_refusal_rate": held["correct_refusal_rate"],
        "heldout_discovery_coverage": held["discovery_coverage"],
        "per_instance": development + heldout,
    }
    # Publish both denominators and the former per-world false-claim rate. The
    # FDR axis is false claims / claims; an all-abstain denominator is zero and
    # downstream metric_contract readers therefore report it as unavailable.
    for prefix, split in (("development", dev), ("heldout", held)):
        for key in ("false_claim_world_rate", "false_discovery_count", "claim_count",
                    "correct_refusal_count", "unsupported_count", "supported_claim_count",
                    "supported_count", "world_count", "valid_count"):
            result[prefix + "_" + key] = split[key]
    return result
