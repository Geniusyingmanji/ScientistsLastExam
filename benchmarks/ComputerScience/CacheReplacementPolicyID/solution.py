"""Weak but valid baseline for CacheReplacementPolicyID.

The textbook check: play ten short random traces once each, compare the outcomes with what LRU,
FIFO and tree pseudo-LRU would have produced, and submit whichever of the three disagrees least,
written out as its machine. It never declines.

Three things are wrong with it. A policy that is none of the three is still submitted as the
closest one. It never asks whether the policy is deterministic at all. And agreement on a few
short random traces says little about states those traces never reach.
"""
from __future__ import annotations

import random
from collections import deque

TRACES = 10
LENGTH = 32


class _LRU:
    def __init__(self, W):
        self.W = W

    def reset(self):
        return tuple(range(self.W - 1, -1, -1))     # most recently used first

    def hit(self, m, i):
        return (i,) + tuple(x for x in m if x != i)

    def miss(self, m):
        return m[-1], (m[-1],) + m[:-1]


class _FIFO(_LRU):
    def hit(self, m, i):
        return m


class _TreePLRU:
    def __init__(self, W):
        self.W = W

    def _touch(self, m, i):
        bits, node, lo, hi = list(m), 0, 0, self.W
        while hi - lo > 1:
            mid = (lo + hi) // 2
            if i < mid:
                bits[node], node, hi = 1, 2 * node + 1, mid
            else:
                bits[node], node, lo = 0, 2 * node + 2, mid
        return tuple(bits)

    def reset(self):
        m = (0,) * (self.W - 1)
        for i in range(self.W):
            m = self._touch(m, i)
        return m

    def hit(self, m, i):
        return self._touch(m, i)

    def miss(self, m):
        node, lo, hi = 0, 0, self.W
        while hi - lo > 1:
            mid = (lo + hi) // 2
            if m[node] == 0:
                node, hi = 2 * node + 1, mid
            else:
                node, lo = 2 * node + 2, mid
        return lo, self._touch(m, lo)


def _machine(policy, cap):
    start = policy.reset()
    index, queue, hit, miss = {start: 0}, deque([start]), [], []
    while queue:
        m = queue.popleft()
        nexts = [policy.hit(m, i) for i in range(policy.W)]
        victim, after = policy.miss(m)
        for nxt in nexts + [after]:
            if nxt not in index:
                index[nxt] = len(index)
                queue.append(nxt)
        if len(index) > cap:
            return None
        hit.append([index[n] for n in nexts])
        miss.append([victim, index[after]])
    return {"hit": hit, "miss": miss}


def _predict(policy, trace):
    m, ways, out = policy.reset(), list(range(policy.W)), []
    for b in trace:
        if b in ways:
            m = policy.hit(m, ways.index(b))
            out.append(True)
        else:
            v, m = policy.miss(m)
            ways[v] = b
            out.append(False)
    return out


def identify(problem, run):
    W = int(problem["ways"])
    rng = random.Random(0)
    fresh = iter(range(1000, 10 ** 6))
    data = []
    for _ in range(TRACES):
        pool, trace = list(range(W)), []
        for _ in range(LENGTH):
            b = next(fresh) if rng.random() < 0.35 else rng.choice(pool[-(W + 2):])
            trace.append(b)
            pool.append(b)
        data.append((trace, run(trace)))
    candidates = [_LRU(W), _FIFO(W)] + ([_TreePLRU(W)] if W & (W - 1) == 0 else [])
    best = None
    for policy in candidates:
        machine = _machine(policy, int(problem["max_states"]))
        if machine is None:
            continue
        bad = sum(p != o for trace, seen in data for p, o in zip(_predict(policy, trace), seen))
        if best is None or bad < best[0]:
            best = (bad, machine)
    return {"verdict": "policy", "machine": best[1], "confidence": 0.9}
