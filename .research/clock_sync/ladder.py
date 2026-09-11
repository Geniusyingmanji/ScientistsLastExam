"""The ablation ladder, the headroom and the shortcut probe, on the package's own evaluator.

    .venv/bin/python .research/clock_sync/ladder.py NAME|all|ladder|probe [run seed shift ...]

Appends one JSON line per strategy and shift to probe.jsonl (probe) or ladder.jsonl (the rest). Ladder rows change one choice of the
reference at a time; probe rows are strategies that do not contain the reference's full pipeline.
"""
import json
import sys
import time
from collections import deque
from pathlib import Path

import numpy as np

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
from pkg_eval import base, record, ref, run  # noqa: E402


def cfg(**c):
    return lambda p, e, w: ref.identify(p, e, w, c)


LADDER = {
    "reference": cfg(),
    "no_order_rows": cfg(order=False),
    "no_atom_rows": cfg(atoms=False),
    "atoms_only_as_test": cfg(detect_only=True),
    "atom_margin_z": cfg(atom_bound="margin"),
    "groups1": cfg(groups=1),
    "groups2": cfg(groups=2),
    "groups6": cfg(groups=6),
    "rounds1": cfg(rounds=1, groups=1),
    "rounds4": cfg(rounds=4),
    "rounds24": cfg(rounds=24),
    "keep1": cfg(keep=1),
    "keep10": cfg(keep=10),
    "k3": cfg(k=3),
    "k8": cfg(k=8),
    "tilt0": cfg(tilt=0.0),
    "atoms_fixed_q2": cfg(atom_bound="fixed", q=2.0),
    "atoms_fixed_q1": cfg(atom_bound="fixed", q=1.0),
    "headroom_z3": cfg(z=3.0),
    "z3.5": cfg(z=3.5),
    "z2.5": cfg(z=2.5),
    "z2": cfg(z=2.0),
}


# ---- shortcut strategies -----------------------------------------------------------------------
def _tree(N, pairs):
    """Carry link differences out from node 0: pairs[(i, j)] = (value of x_j - x_i, half width)."""
    x, frontier = {0: (np.zeros(2), np.zeros(2))}, deque([0])
    while frontier:
        a = frontier.popleft()
        for (i, j), (v, h) in pairs.items():
            if i == a and j not in x:
                x[j] = (x[a][0] + v, x[a][1] + h); frontier.append(j)
            elif j == a and i not in x:
                x[i] = (x[a][0] - v, x[a][1] + h); frontier.append(i)
    return x


def _answer(N, x, margin=0.0):
    return {"verdict": "offsets", "confidence": 0.9, "intervals": {
        str(j): [[float(x[j][0][k] - x[j][1][k] - margin), float(x[j][0][k] + x[j][1][k] + margin)] for k in range(2)]
        for j in range(1, N)}}


def _rounds(problem, exchange, wait, R=12):
    links = [tuple(l) for l in problem["links"]]
    n = problem["probe_budget"] // (R * len(links))
    gap = (problem["horizon_s"] - R * n * len(links) * problem["probe_spacing_s"]) / R
    data = {l: [] for l in links}
    for r in range(R):
        for l in links:
            data[l].append(np.asarray(exchange(l[0], l[1], n), dtype=float))
        if r < R - 1:
            wait(gap)
    return links, data


def ntp_mid(margin):
    """NTP on all the data at once: minimum forward and backward delay, half the difference."""
    def f(problem, exchange, wait):
        links, data = _rounds(problem, exchange, wait, R=1)
        pairs = {}
        for l in links:
            X = data[l][0]
            v = ((X[:, 1] - X[:, 0]).min() - (X[:, 3] - X[:, 2]).min()) / 2
            pairs[l] = (np.full(2, v), np.zeros(2))
        return _answer(problem["nodes"], _tree(problem["nodes"], pairs), margin)
    return f


def ntp_rate(margin):
    """The baseline's NTP with a rate at other margins."""
    return lambda problem, exchange, wait: _ntp_rate(problem, exchange, wait, margin)


def _ntp_rate(problem, exchange, wait, margin):
    links, data = _rounds(problem, exchange, wait)
    E = np.array(problem["epochs_s"])
    pairs = {}
    for l in links:
        t = np.array([X[:, 0].mean() for X in data[l]])
        m = np.array([((X[:, 1] - X[:, 0]).min() - (X[:, 3] - X[:, 2]).min()) / 2 for X in data[l]])
        pairs[l] = (np.polyval(np.polyfit(t, m, 1), E), np.zeros(2))
    return _answer(problem["nodes"], _tree(problem["nodes"], pairs), margin)


def cristian(z, rate):
    """Per round a rigorous box for x_j - x_i from the minimum delays and the lower bounds,
    u <= min fwd - L_fwd + m and u >= L_back - min back - m; with rate, a line through the box
    centres and the widest half box plus the largest centre residual; without, the intersection."""
    def f(problem, exchange, wait):
        links, data = _rounds(problem, exchange, wait)
        L = {tuple(int(v) for v in k.split("->")): x for k, x in problem["lower_bound_s"].items()}
        sig = problem["timestamp_sigma_s"]
        E = np.array(problem["epochs_s"])
        pairs = {}
        for (i, j) in links:
            m = z * np.hypot(sig[i], sig[j])
            t = np.array([X[:, 0].mean() for X in data[(i, j)]])
            hi = np.array([(X[:, 1] - X[:, 0]).min() - L[(i, j)] + m for X in data[(i, j)]])
            lo = np.array([L[(j, i)] - (X[:, 3] - X[:, 2]).min() - m for X in data[(i, j)]])
            if np.any(lo > hi):
                return {"verdict": "no_model", "confidence": 0.9}
            if rate:
                c = (lo + hi) / 2
                fit = np.polyfit(t, c, 1)
                half = (hi - lo).max() / 2 + np.abs(c - np.polyval(fit, t)).max()
                pairs[(i, j)] = (np.polyval(fit, E), np.full(2, half))
            else:
                a, b = lo.max(), hi.min()
                if a > b:
                    return {"verdict": "no_model", "confidence": 0.9}
                pairs[(i, j)] = (np.full(2, (a + b) / 2), np.full(2, (b - a) / 2))
        return _answer(problem["nodes"], _tree(problem["nodes"], pairs))
    return f


def lp_line_test(threshold):
    """The reference's LP without atom rows, declining when a link's per-round NTP differences
    stray from a straight line by more than the threshold (a rate step or a jump bends them)."""
    def f(problem, exchange, wait):
        seen = {}

        def spy(i, j, n):
            X = np.asarray(exchange(i, j, n), dtype=float)
            seen.setdefault((i, j), []).append(X)
            return X
        answer = ref.identify(problem, spy, wait, {"atoms": False})
        if threshold is not None:
            for rounds in seen.values():
                t = np.array([X[:, 0].mean() for X in rounds])
                m = np.array([((X[:, 1] - X[:, 0]).min() - (X[:, 3] - X[:, 2]).min()) / 2 for X in rounds])
                if np.abs(m - np.polyval(np.polyfit(t, m, 1), t)).max() > threshold:
                    return {"verdict": "no_model", "confidence": 0.9}
        return answer
    return f


PROBE = {
    "decline_all": lambda p, e, w: {"verdict": "no_model"},
    "blind_wide_claim": lambda p, e, w: {"verdict": "offsets", "confidence": 0.5,
                                          "intervals": {str(j): [[-1.0, 1.0]] * 2 for j in range(1, p["nodes"])}},
    "baseline": base.identify,
    **{"ntp_mid_%gus" % (m * 1e6): ntp_mid(m) for m in (1e-6, 5e-6, 20e-6, 100e-6, 1e-3)},
    **{"ntp_rate_%gus" % (m * 1e6): ntp_rate(m) for m in (1e-6, 20e-6, 100e-6, 1e-3)},
    **{"cristian_z%g_%s" % (z, "rate" if r else "const"): cristian(z, r) for z in (3.0, 5.45) for r in (True, False)},
    **{"lp_no_atoms_test_%s" % ("none" if t is None else "%gus" % (t * 1e6)): lp_line_test(t) for t in (None, 2e-6, 5e-6, 10e-6)},
    **{"lp_floor_test_c%g_g%d" % (c, g): cfg(detect_only=True, atom_bound="fixed", q=c, groups=g)
       for c in (2.0, 3.0, 5.0) for g in (3, 12)},
    **{"lp_atoms_as_test_%s" % n: cfg(detect_only=True, **c) for n, c in (("default", {}), ("z3", {"z": 3.0}), ("z4", {"z": 4.0}))},
}

if __name__ == "__main__":
    which = sys.argv[1]
    shifts = [int(x) for x in sys.argv[2:]] or [0]
    names = list(LADDER) + list(PROBE) if which == "all" else list(LADDER) if which == "ladder" else list(PROBE) if which == "probe" else [which]
    with open(HERE / ("probe.jsonl" if which == "probe" else "ladder.jsonl"), "a") as fh:
        for name in names:
            strategy = LADDER.get(name) or PROBE[name]
            for shift in shifts:
                start = time.time()
                rec = record(name, shift, run(strategy, shift), time.time() - start)
                rec["group"] = "ladder" if name in LADDER else "probe"
                fh.write(json.dumps(rec) + "\n"); fh.flush()
                print(name, shift, rec["dev"], rec["held"], rec["dev_fdr"], rec["held_fdr"], flush=True)
