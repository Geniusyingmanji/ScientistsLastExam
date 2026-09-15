"""Truth-blind reference for CacheReplacementPolicyID.

It reads only the public problem and the hit/miss outcomes that `run` returns, and it works in
four stages.

    victims      the one question it asks of the cache is which way a miss evicts after a given
                 sequence of accesses. It replays the sequence, accesses a fresh block, then
                 re-accesses the old blocks in a shuffled order: hits change nothing that is in
                 the set, so the first of them that misses is the one that left. Each answer is
                 a likelihood over the ways, accumulated over repeated runs until one way leads
                 the next by a factor of 10^4, and remembered.
    determinism  before anything is claimed, the same traces are run many times. Under a
                 deterministic policy every position's outcome is one value flipped by the
                 published noise, so disagreement beyond that is randomness: a per-position tail
                 test on random traces, then a pooled test on bursts of misses and on loops over
                 more blocks than there are ways, where a random choice has the most chances to
                 show. Either one failing is a refusal.
    fit          a library of age-table policies, 2064 of them (two or four ages, every hit table,
                 every insertion age, with and without ageing to the top on a miss), is scored on
                 noisy traces by majority vote; survivors within two mismatches of the best that
                 still differ are settled by the victim query their difference names, and the
                 winner is checked.
    L*           otherwise, Angluin's L* for Mealy machines over the ways and a miss, with
                 Rivest-Schapire counterexample processing, learns a machine from victim
                 queries. Its equivalence queries are targeted checks: random traces, bursts of
                 misses and hit permutations, 64 of them at five runs each, every disagreement
                 with the hypothesis confirmed by six more runs before it counts. A hypothesis
                 above 32 states is not claimed.

What it does not do, on purpose: it knows only one family by name, and L* on a large machine runs
out of budget well before it is done, which is why it refuses to claim a hypothesis above 32
states. A policy that is neither an age table nor small is declined. That is where it leaves
room.
"""
from __future__ import annotations

import itertools
import math
import random
from collections import deque

LEAD = math.log(1e4)
MAX_REPEATS = 15
DET_TAIL = 6.0            # -log10 of the per-position tail probability that counts as random
DET_POOLED_Z = 4.0        # pooled minority count, in standard deviations above the noise
DET_TRACES = 32           # bursts and loops in the pooled test, 48 runs each
FAMILY_CHECKS = 16
LSTAR_CHECKS = 64
CHECK_RUNS = 5
CONFIRM_RUNS = 6
CLAIM_CAP = 32
ROUNDS = 40
MAX_ROWS = 512
SEED = 20260911


class _Spent(Exception):
    pass


# ---- the cache, as the reference sees it ------------------------------------------------------
class _Box:
    def __init__(self, problem, run, rng):
        self.W = int(problem["ways"])
        self.q = float(problem["noise"])
        self.budget = int(problem["run_budget"])
        self._run = run
        self.rng = rng
        self.spent = 0
        self.victims = {}
        self.fresh = itertools.count(1000)

    def run(self, trace):
        cost = self.W + len(trace)
        if self.spent + cost > self.budget:
            raise _Spent()
        self.spent += cost
        return self._run(trace)

    def realise(self, word):
        """A concrete trace for an abstract word (way indices and "M" for a fresh block)."""
        ways = list(range(self.W))
        trace = []
        for k, a in enumerate(word):
            if a == "M":
                b = next(self.fresh)
                trace.append(b)
                ways[self.victim(tuple(word[:k]))] = b
            else:
                trace.append(ways[a])
        return trace, ways

    def victim(self, prefix):
        prefix = tuple(prefix)
        if prefix in self.victims:
            return self.victims[prefix]
        trace, ways = self.realise(prefix)
        lq, lp = math.log(self.q), math.log(1 - self.q)
        score = [0.0] * self.W
        order = list(range(self.W))
        for rep in range(MAX_REPEATS):
            self.rng.shuffle(order)
            probe = [ways[i] for i in order]
            out = self.run(trace + [next(self.fresh)] + probe)[len(trace) + 1:]
            for pos, v in enumerate(order):
                # if v was evicted, the probes before it hit and it missed
                score[v] += sum(lp if out[j] else lq for j in range(pos)) + (lp if not out[pos] else lq)
            best = sorted(range(self.W), key=lambda v: -score[v])
            if rep >= 1 and score[best[0]] - score[best[1]] > LEAD:
                break
        self.victims[prefix] = best[0]
        return best[0]


# ---- machines ---------------------------------------------------------------------------------
def _minimise(n, hit, miss):
    part = [miss[s][0] for s in range(n)]
    while True:
        signature = [(part[s], tuple(part[t] for t in hit[s]), part[miss[s][1]]) for s in range(n)]
        ids = {}
        refined = [ids.setdefault(sig, len(ids)) for sig in signature]
        if len(ids) == len(set(part)):
            break
        part = refined
    representative = {}
    for s in range(n):
        representative.setdefault(part[s], s)
    number = {part[0]: 0}
    queue = deque([0])
    while queue:
        s = queue.popleft()
        for t in list(hit[s]) + [miss[s][1]]:
            if part[t] not in number:
                number[part[t]] = len(number)
                queue.append(representative[part[t]])
    k = len(number)
    H, M = [None] * k, [None] * k
    for block, idx in number.items():
        s = representative[block]
        H[idx] = [number[part[t]] for t in hit[s]]
        M[idx] = (miss[s][0], number[part[miss[s][1]]])
    return k, H, M


def _machine(policy, cap=5000):
    start = policy.reset()
    index, states, queue = {start: 0}, [start], deque([start])
    hit, miss = [], []
    while queue:
        m = queue.popleft()
        row = []
        for i in range(policy.W):
            nxt = policy.hit(m, i)
            if nxt not in index:
                index[nxt] = len(states)
                states.append(nxt)
                queue.append(nxt)
            row.append(index[nxt])
        v, nxt = policy.miss(m)
        if nxt not in index:
            index[nxt] = len(states)
            states.append(nxt)
            queue.append(nxt)
        hit.append(row)
        miss.append((v, index[nxt]))
        if len(states) > cap:
            return None
    return _minimise(len(states), hit, miss)


def _difference(a, b):
    (_na, ha, ma), (_nb, hb, mb) = a, b
    W = len(ha[0])
    parent = {(0, 0): None}
    queue = deque([(0, 0)])
    while queue:
        s, t = queue.popleft()
        if ma[s][0] != mb[t][0]:
            word, cur = ["M"], (s, t)
            while parent[cur] is not None:
                cur, symbol = parent[cur]
                word.append(symbol)
            return word[::-1]
        for symbol, nxt in [(i, (ha[s][i], hb[t][i])) for i in range(W)] + [("M", (ma[s][1], mb[t][1]))]:
            if nxt not in parent:
                parent[nxt] = ((s, t), symbol)
                queue.append(nxt)
    return None


def _predict(machine, trace, W):
    _n, H, M = machine
    s, ways, out = 0, list(range(W)), []
    for b in trace:
        if b in ways:
            s = H[s][ways.index(b)]
            out.append(True)
        else:
            v, s = M[s]
            ways[v] = b
            out.append(False)
    return out


def _predict_victim(machine, word):
    _n, H, M = machine
    s = 0
    for a in word[:-1]:
        s = M[s][1] if a == "M" else H[s][a]
    return M[s][0]


# ---- traces -----------------------------------------------------------------------------------
def _random_trace(W, length, rng, fresh):
    pool, trace = list(range(W)), []
    for _ in range(length):
        b = next(fresh) if rng.random() < 0.35 else rng.choice(pool[-(W + 2):])
        trace.append(b)
        pool.append(b)
    return trace


def _stress_trace(W, rng, fresh):
    """Some hits, a burst of misses, then re-accesses of the burst and of the older blocks."""
    base = list(range(W))
    t = [rng.choice(base) for _ in range(rng.randint(0, 3))]
    burst = [next(fresh) for _ in range(rng.randint(1, 2 * W))]
    t += burst
    tail = burst[-W:] + base
    rng.shuffle(tail)
    return t + tail[: rng.randint(2, W + 2)]


def _perm_trace(W, rng, fresh):
    """Hits that reorder the resident blocks, a short burst, then re-accesses."""
    base = list(range(W))
    t = [rng.choice(base) for _ in range(rng.randint(W, 2 * W))]
    burst = [next(fresh) for _ in range(rng.randint(1, W))]
    tail = base + burst
    rng.shuffle(tail)
    return t + burst + tail[: rng.randint(2, W + 2)]


def _mixed_traces(W, rng, fresh, n):
    out = []
    for k in range(n):
        if k % 3 == 1:
            out.append(_stress_trace(W, rng, fresh))
        elif k % 3 == 2:
            out.append(_perm_trace(W, rng, fresh))
        else:
            rate = rng.choice([0.2, 0.35, 0.6])
            pool, t = list(range(W)), []
            for _ in range(24):
                b = next(fresh) if rng.random() < rate else rng.choice(pool[-(W + 2):])
                t.append(b)
                pool.append(b)
            out.append(t)
    return out


def _burst_trace(W, rng, fresh):
    base = list(range(W))
    t = [rng.choice(base) for _ in range(rng.randint(0, W))]
    burst = [next(fresh) for _ in range(rng.randint(W // 2, 2 * W))]
    tail = burst + base
    rng.shuffle(tail)
    return t + burst + tail


def _cyclic_trace(W, rng, fresh):
    blocks = list(range(W)) + [next(fresh) for _ in range(rng.randint(1, W // 2 + 1))]
    rng.shuffle(blocks)
    return blocks * rng.randint(2, 4)


def _counts(box, trace, reps):
    counts = [0] * len(trace)
    for _ in range(reps):
        for j, h in enumerate(box.run(trace)):
            counts[j] += h
    return counts


def _tail(reps, q, m):
    return sum(math.comb(reps, j) * q ** j * (1 - q) ** (reps - j) for j in range(m, reps + 1))


# ---- determinism ------------------------------------------------------------------------------
def _per_position(box, rng):
    """Random traces, ten runs each: is any position's disagreement beyond the noise?"""
    worst = 0.0
    for _ in range(6):
        for c in _counts(box, _random_trace(box.W, 40, rng, box.fresh), 10):
            worst = max(worst, -math.log10(max(_tail(10, box.q, min(c, 10 - c)), 1e-300)))
    return worst > DET_TAIL


def _pooled(box, rng):
    """Bursts and loops, 48 runs each: under a deterministic policy each position's minority count
    is at most Binomial(48, noise), and randomness adds to it; pooled over every position, and the
    worst single position."""
    q = box.q
    minority, total, worst = 0, 0, 0.0
    for k in range(DET_TRACES):
        trace = (_burst_trace if k % 2 else _cyclic_trace)(box.W, rng, box.fresh)
        for c in _counts(box, trace, 48):
            m = min(c, 48 - c)
            minority += m
            total += 48
            worst = max(worst, -math.log10(max(_tail(48, q, m), 1e-300)))
    z = (minority - total * q) / math.sqrt(total * q * (1 - q))
    return z > DET_POOLED_Z or worst > DET_TAIL


def _random_looking(box, rng):
    return _per_position(box, rng) or _pooled(box, rng)


# ---- checks -----------------------------------------------------------------------------------
def _check(box, machine, rng, n):
    """A trace prefix on which the cache disagrees with the machine, confirmed; None if none."""
    for t in _mixed_traces(box.W, rng, box.fresh, n):
        pred = _predict(machine, t, box.W)
        counts = _counts(box, t, CHECK_RUNS)
        for j in range(len(t)):
            if (counts[j] * 2 > CHECK_RUNS) != pred[j]:
                c, k = counts[j], CHECK_RUNS
                for _ in range(CONFIRM_RUNS):
                    c += box.run(t[: j + 1])[j]
                    k += 1
                if (c * 2 > k) != pred[j]:
                    return t[: j + 1]
    return None


# ---- the age-table library --------------------------------------------------------------------
class _AgeTable:
    def __init__(self, W, A, table, insert, age_all):
        self.W, self.A, self.table, self.insert, self.age_all = W, A, tuple(table), insert, age_all

    def reset(self):
        m = [self.A - 1] * self.W
        for i in range(self.W):
            m[i] = self.insert
        return tuple(m)

    def hit(self, m, i):
        m = list(m)
        m[i] = self.table[m[i]]
        return tuple(m)

    def miss(self, m):
        top = max(m)
        if self.age_all:
            m = tuple(a + self.A - 1 - top for a in m)
            top = self.A - 1
        v = m.index(top)
        m = list(m)
        m[v] = self.insert
        return v, tuple(m)


def _library(W):
    for A in (2, 4):
        for table in itertools.product(range(A), repeat=A):
            for insert in range(A):
                for age_all in (True, False):
                    yield _AgeTable(W, A, table, insert, age_all)


def _simulate(policy, trace):
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


def _fit_library(box, rng):
    data = []
    for t in _mixed_traces(box.W, rng, box.fresh, 24):
        data.append((t, [c * 2 > 3 for c in _counts(box, t, 3)]))
    cap = max(3, int(0.01 * sum(len(t) for t, _ in data)))
    scored = []
    for policy in _library(box.W):
        bad = 0
        for t, seen in data:
            bad += sum(p != o for p, o in zip(_simulate(policy, t), seen))
            if bad > cap:
                break
        if bad <= cap:
            scored.append((bad, policy))
    if not scored:
        return None
    best = min(b for b, _ in scored)
    machines = []
    for _b, policy in sorted(((b, p) for b, p in scored if b <= best + 2), key=lambda r: r[0]):
        m = _machine(policy)
        if m is not None and all(_difference(m, o) is not None for o in machines):
            machines.append(m)
    # inequivalent survivors: the victim query their difference names settles them
    while len(machines) > 1:
        word = _difference(machines[0], machines[1])
        v = box.victim(tuple(word[:-1]))
        keep = [m for m in machines if _predict_victim(m, word) == v]
        if not keep:
            return None
        if len(keep) == len(machines):
            break
        machines = keep
    return machines[0] if len(machines) == 1 else None


# ---- L* ---------------------------------------------------------------------------------------
class _LStar:
    def __init__(self, box):
        self.box, self.W = box, box.W
        self.inputs = list(range(self.W)) + ["M"]
        self.E = [("M",)]
        self.S = [()]

    def cell(self, u, e):
        out, w = [], tuple(u)
        for a in e:
            if a == "M":
                out.append(self.box.victim(w))
            w = w + (a,)
        return tuple(out)

    def row(self, u):
        return tuple(self.cell(u, e) for e in self.E)

    def close(self):
        while True:
            rows = {self.row(s): s for s in self.S}
            added = False
            for s in list(self.S):
                for a in self.inputs:
                    r = self.row(s + (a,))
                    if r not in rows:
                        self.S.append(s + (a,))
                        rows[r] = s + (a,)
                        added = True
                        if len(self.S) > MAX_ROWS:
                            raise _Spent()
            if not added:
                return rows

    def hypothesis(self):
        rows = self.close()
        order = [self.row(())] + [r for r in rows if r != self.row(())]
        idx = {r: k for k, r in enumerate(order)}
        H, M = [None] * len(order), [None] * len(order)
        for r in order:
            s = rows[r]
            H[idx[r]] = [idx[self.row(s + (i,))] for i in range(self.W)]
            M[idx[r]] = (r[0][0], idx[self.row(s + ("M",))])
        return _minimise(len(order), H, M)

    def access(self, hyp):
        _n, H, M = hyp
        acc, frontier = {0: ()}, [0]
        while frontier:
            nxt = []
            for s in frontier:
                for a in self.inputs:
                    t = M[s][1] if a == "M" else H[s][a]
                    if t not in acc:
                        acc[t] = acc[s] + (a,)
                        nxt.append(t)
            frontier = nxt
        return acc

    def add_counterexample(self, ce, hyp):
        """Rivest-Schapire: the index where swapping the prefix for the access word of the state it
        reaches flips the last victim names one distinguishing suffix."""
        _n, H, M = hyp
        access = self.access(hyp)
        states = [0]
        for a in ce[:-1]:
            states.append(M[states[-1]][1] if a == "M" else H[states[-1]][a])

        def victim_after(i):
            return self.box.victim(tuple(access[states[i]]) + tuple(ce[i:-1]))

        lo, hi = 0, len(ce) - 1
        target = victim_after(lo)
        while hi - lo > 1:
            mid = (lo + hi) // 2
            if victim_after(mid) == target:
                lo = mid
            else:
                hi = mid
        suffix = tuple(ce[hi:])
        if suffix not in self.E:
            self.E.append(suffix)
            return
        for k in range(len(ce)):
            suffix = tuple(ce[k:])
            if suffix not in self.E:
                self.E.append(suffix)


def _abstract_counterexample(box, machine, trace):
    """Walk a disagreeing trace with the cache's own victims; the first miss where the machine
    names another way ends an abstract counterexample."""
    _n, H, M = machine
    ways, s, word = list(range(box.W)), 0, []
    for b in trace:
        if b in ways:
            i = ways.index(b)
            word.append(i)
            s = H[s][i]
        else:
            v = box.victim(tuple(word))
            if v != M[s][0]:
                return tuple(word) + ("M",)
            word.append("M")
            ways[v] = b
            s = M[s][1]
    return None


# ---- the audit --------------------------------------------------------------------------------
def _learn(box, rng):
    if _random_looking(box, rng):
        return None
    m = _fit_library(box, rng)
    if m is not None and _check(box, m, rng, FAMILY_CHECKS) is None:
        return m
    learner = _LStar(box)
    for _ in range(ROUNDS):
        hyp = learner.hypothesis()
        if hyp[0] > CLAIM_CAP:
            return None
        t = _check(box, hyp, rng, LSTAR_CHECKS)
        if t is None:
            return hyp
        ce = _abstract_counterexample(box, hyp, t)
        if ce is not None:
            learner.add_counterexample(ce, hyp)
    return None


def identify(problem, run):
    rng = random.Random(SEED)
    box = _Box(problem, run, rng)
    try:
        machine = _learn(box, rng)
    except _Spent:
        machine = None
    if machine is None:
        return {"verdict": "no_policy", "confidence": 0.7}
    _n, H, M = machine
    return {"verdict": "policy", "machine": {"hit": [list(r) for r in H], "miss": [[v, t] for v, t in M]},
            "confidence": 0.8}
