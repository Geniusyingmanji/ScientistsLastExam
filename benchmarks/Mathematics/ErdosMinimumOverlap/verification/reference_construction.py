"""Truth-blind reference construction for ErdosMinimumOverlap.

Local search: starts from several random balanced partitions, then repeatedly swaps one
element between A and B whenever that strictly lowers max_k M_k (first-improvement hill
climbing), until no single swap helps. Repeats with many random restarts and random swap
orders, keeping the best (lowest max-overlap) partition found. This is a real, standard
technique for this kind of combinatorial minimization -- not the Fourier-analytic /
step-function optimization the cited asymptotic-bound papers use -- and for the largest
size this task checks (n=15) it does not reach the true, exactly-known optimum, leaving
real headroom for a smarter search.
"""
from __future__ import annotations

import random

import numpy as np


def _max_overlap(labels: list[int]) -> int:
    arr = np.asarray(labels)
    ia = (arr == 0).astype(np.int64)
    ib = (arr == 1).astype(np.int64)
    return int(np.correlate(ia, ib, mode="full").max())


def _one_run(n: int, rng: random.Random) -> int:
    labels = [0] * n + [1] * n
    rng.shuffle(labels)
    current = _max_overlap(labels)
    improved = True
    while improved:
        improved = False
        idx_a = [i for i, v in enumerate(labels) if v == 0]
        idx_b = [i for i, v in enumerate(labels) if v == 1]
        rng.shuffle(idx_a)
        rng.shuffle(idx_b)
        for i in idx_a:
            for j in idx_b:
                labels[i], labels[j] = labels[j], labels[i]
                candidate = _max_overlap(labels)
                if candidate < current:
                    current = candidate
                    improved = True
                    break
                labels[i], labels[j] = labels[j], labels[i]
            if improved:
                break
    return current, labels


def construct_partition(n: int, restarts: int = 200, seed: int = 0):
    rng = random.Random(seed)
    best_score, best_labels = None, None
    for _ in range(restarts):
        score, labels = _one_run(n, rng)
        if best_score is None or score < best_score:
            best_score, best_labels = score, labels
    return best_labels
