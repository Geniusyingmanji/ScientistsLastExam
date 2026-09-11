"""Weak but valid baseline for ClockSyncInversion.

NTP with a rate: twelve rounds of exchanges on every link, spread over the horizon; in each round
the smallest forward and the smallest backward delay; half their difference as the link's offset
difference, as NTP does; a straight line through the rounds for every link; offsets carried out
from node 0 along a breadth-first tree; five microseconds either side. It never declines.

Three things are wrong with it. Half the difference of the two minimum delays is the offset only
when the two directions have equal propagation, which nothing says. Five microseconds is a guess,
not a bound. And it never asks whether affine clocks can explain the exchanges at all.
"""
from __future__ import annotations

import numpy as np

ROUNDS = 12
HALF_WIDTH = 5e-6


def identify(problem, exchange, wait):
    N = problem["nodes"]
    links = [tuple(l) for l in problem["links"]]
    n = problem["probe_budget"] // (ROUNDS * len(links))
    gap = (problem["horizon_s"] - ROUNDS * n * len(links) * problem["probe_spacing_s"]) / ROUNDS
    data = {l: [] for l in links}
    for r in range(ROUNDS):
        for l in links:
            X = np.asarray(exchange(l[0], l[1], n), dtype=float)
            data[l].append((X[:, 0].mean(), (X[:, 1] - X[:, 0]).min(), (X[:, 3] - X[:, 2]).min()))
        if r < ROUNDS - 1:
            wait(gap)
    fit = {}
    for l, rows in data.items():
        t, f, b = map(np.array, zip(*rows))
        fit[l] = np.polyfit(t, (f - b) / 2, 1)
    epochs = np.array(problem["epochs_s"])
    x, frontier = {0: np.zeros(2)}, [0]
    while frontier:
        a = frontier.pop()
        for (i, j), c in fit.items():
            step = np.polyval(c, epochs)
            if i == a and j not in x:
                x[j] = x[a] + step; frontier.append(j)
            elif j == a and i not in x:
                x[i] = x[a] - step; frontier.append(i)
    intervals = {str(j): [[float(x[j][k] - HALF_WIDTH), float(x[j][k] + HALF_WIDTH)] for k in range(2)]
                 for j in range(1, N)}
    return {"verdict": "offsets", "intervals": intervals, "confidence": 0.9}
