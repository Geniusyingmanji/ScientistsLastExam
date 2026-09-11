"""Score a strategy on the prototype worlds: python run.py NAME [shift ...]."""
import json
import sys
import time

import numpy as np

import engine as E
import ref
from worlds import DEV, HELD


def ntp(problem, exchange, wait, cfg=None):
    """Classic NTP: midpoint of min fwd and min back on a BFS tree, +-1us."""
    N = problem["nodes"]
    links = [tuple(l) for l in problem["links"]]
    n = problem["probe_budget"] // len(links)
    u = {}
    for (i, j) in links:
        X = exchange(i, j, n)
        u[(i, j)] = ((X[:, 1] - X[:, 0]).min() - (X[:, 3] - X[:, 2]).min()) / 2
    x, frontier = {0: 0.0}, [0]
    while frontier:
        a = frontier.pop()
        for (i, j), v in u.items():
            if i == a and j not in x:
                x[j] = x[a] + v; frontier.append(j)
            elif j == a and i not in x:
                x[i] = x[a] - v; frontier.append(i)
    return {j: [[x[j] - 1e-6, x[j] + 1e-6]] * 2 for j in range(1, N)}


def ntp_skew(problem, exchange, wait, cfg=None):
    """NTP with skew: per-round minima in both directions, a line through each, the midpoint on a
    BFS tree, +-5 us, never declining."""
    N = problem["nodes"]
    links = [tuple(l) for l in problem["links"]]
    R = 12
    n = problem["probe_budget"] // (R * len(links))
    gap = (problem["horizon_s"] - R * n * len(links) * problem["probe_spacing_s"]) / R
    data = {l: [] for l in links}
    for r in range(R):
        for l in links:
            X = exchange(l[0], l[1], n)
            data[l].append((X[:, 0].mean(), (X[:, 1] - X[:, 0]).min(), (X[:, 3] - X[:, 2]).min()))
        if r < R - 1:
            wait(gap)
    fit = {}
    for l, rows in data.items():
        t, f, b = map(np.array, zip(*rows))
        fit[l] = np.polyfit(t, (f - b) / 2, 1)
    E = problem["epochs_s"]
    x, frontier = {0: np.zeros(2)}, [0]
    while frontier:
        a = frontier.pop()
        for (i, j), c in fit.items():
            v = np.polyval(c, E)
            if i == a and j not in x:
                x[j] = x[a] + v; frontier.append(j)
            elif j == a and i not in x:
                x[i] = x[a] - v; frontier.append(i)
    return {j: [[x[j][k] - 5e-6, x[j][k] + 5e-6] for k in range(2)] for j in range(1, N)}


STRATS = {
    "ntp_skew": ntp_skew,
    "detect_only": lambda p, e, w: ref.identify(p, e, w, {"detect_only": True}),
    "detect_only_z3": lambda p, e, w: ref.identify(p, e, w, {"detect_only": True, "z": 3.0}),
    "atom_margin": lambda p, e, w: ref.identify(p, e, w, {"atom_bound": "margin"}),
    "min_upper": lambda p, e, w: ref.identify(p, e, w, {"upper": "min"}),
    "min_z3": lambda p, e, w: ref.identify(p, e, w, {"upper": "min", "z": 3.0}),
    "ref_z3": lambda p, e, w: ref.identify(p, e, w, {"z": 3.0}),
    "z3": lambda p, e, w: ref.identify(p, e, w, {"z": 3.0}),
    "z8": lambda p, e, w: ref.identify(p, e, w, {"z": 8.0}),
    "z3.5": lambda p, e, w: ref.identify(p, e, w, {"z": 3.5}),
    "z4.0": lambda p, e, w: ref.identify(p, e, w, {"z": 4.0}),
    "z4.5": lambda p, e, w: ref.identify(p, e, w, {"z": 4.5}),
    "rounds1": lambda p, e, w: ref.identify(p, e, w, {"rounds": 1, "groups": 1}),
    "rounds4": lambda p, e, w: ref.identify(p, e, w, {"rounds": 4}),
    "rounds24": lambda p, e, w: ref.identify(p, e, w, {"rounds": 24}),
    "keep1": lambda p, e, w: ref.identify(p, e, w, {"keep": 1}),
    "keep10": lambda p, e, w: ref.identify(p, e, w, {"keep": 10}),
    "groups2": lambda p, e, w: ref.identify(p, e, w, {"groups": 2}),
    "groups6": lambda p, e, w: ref.identify(p, e, w, {"groups": 6}),
    "reference": lambda p, e, w: ref.identify(p, e, w),
    "k3": lambda p, e, w: ref.identify(p, e, w, {"k": 3}),
    "k8": lambda p, e, w: ref.identify(p, e, w, {"k": 8}),
    "k12": lambda p, e, w: ref.identify(p, e, w, {"k": 12}),
    "k_multi": lambda p, e, w: ref.identify(p, e, w, {"k": [2, 4, 8, 16]}),
    "k_multi_z3": lambda p, e, w: ref.identify(p, e, w, {"k": [2, 4, 8, 16], "z": 3.0}),
    "z2.5": lambda p, e, w: ref.identify(p, e, w, {"z": 2.5}),
    "z2": lambda p, e, w: ref.identify(p, e, w, {"z": 2.0}),
    "z1.5": lambda p, e, w: ref.identify(p, e, w, {"z": 1.5}),
    "no_atoms": lambda p, e, w: ref.identify(p, e, w, {"atoms": False}),
    "no_group_atoms": lambda p, e, w: ref.identify(p, e, w, {"group_atoms": False}),
    "ntp": ntp,
}


def main(name, shifts):
    for shift in shifts:
        rows, t0 = [], time.time()
        for spec in DEV + HELD:
            w = E.make_world(spec)
            widths = E.identifiable(w, spec["horizon"]) if w["kind"] == "supported" else None
            c = E.Campaign(w, spec["budget"], spec["horizon"], shift)
            try:
                ans = STRATS[name](E.public(w, spec), c.exchange, c.wait)
            except Exception as exc:  # noqa: BLE001
                ans, note = "error", repr(exc)
            s, note = (0.0, note) if ans == "error" else E.score(w, ans, spec["horizon"], widths)
            wid = "" if not isinstance(ans, dict) else " ".join(
                "%.1f/%.1f" % ((ans[j][0][1] - ans[j][0][0]) * 1e6, widths[j, 0] * 1e6 if widths is not None else -1) for j in sorted(ans))
            rows.append((spec["name"], w["kind"], round(s, 3), note, c.used, wid))
        def split(rs):
            nref = sum(r[1] != "supported" for r in rs)
            raw = np.mean([r[2] for r in rs])
            return raw, max(0.0, (raw - nref / len(rs)) / (1 - nref / len(rs))), sum("FD" in r[3] for r in rs)
        raw, norm, fd = split(rows[:len(DEV)])
        hraw, hnorm, hfd = split(rows[len(DEV):])
        print(f"{name} shift {shift} dev {norm:.3f} held {hnorm:.3f} FD {fd}/{hfd} {time.time()-t0:.1f}s")
        for r in rows:
            print("  ", *r)
        with open("runs.jsonl", "a") as fh:
            fh.write(json.dumps({"name": name, "shift": shift, "dev": norm, "held": hnorm, "dev_fd": fd, "held_fd": hfd, "rows": rows}) + "\n")


if __name__ == "__main__":
    main(sys.argv[1], [int(s) for s in sys.argv[2:]] or [0])
