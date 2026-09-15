"""Prototype learners for CacheReplacementPolicyID, run against engine.Cache.

Abstract alphabet: 0..W-1 (hit the block in way i) and "M" (a fresh block). The learner only ever
sees block-level hit/miss through cache.run(trace), with flip noise q, and learns victims by
replaying a prefix, missing once and probing the old blocks: the first probe that misses is the
victim, because hits never change the contents.
"""
import itertools
import math
import random

import engine as E


class Budget(Exception):
    pass


class Box:
    """Learner-side view: counts spend, memoises victims by abstract prefix."""
    def __init__(self, cache, W, q, budget, rng, lead=math.log(200.0), max_rep=15):
        self.cache, self.W, self.q, self.budget = cache, W, q, budget
        self.rng, self.lead, self.max_rep = rng, lead, max_rep
        self.spent = 0
        self.victims = {}
        self.fresh = itertools.count(1000)

    def run(self, trace):
        cost = self.W + len(trace)
        if self.spent + cost > self.budget:
            raise Budget()
        self.spent += cost
        return self.cache.run(trace)

    def realise(self, word):
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
        for rep in range(self.max_rep):
            self.rng.shuffle(order)
            probe = [ways[i] for i in order]
            out = self.run(trace + [next(self.fresh)] + probe)[len(trace) + 1:]
            for pos, v in enumerate(order):
                # hypothesis v: probes before it hit, it misses
                s = sum(lp if out[j] else lq for j in range(pos)) + (lp if not out[pos] else lq)
                score[v] += s
            best = sorted(range(self.W), key=lambda v: -score[v])
            if rep >= 1 and score[best[0]] - score[best[1]] > self.lead:
                break
        v = best[0]
        self.victims[prefix] = v
        return v


def predict(machine, trace, W):
    """Hit/miss of a hypothesis machine on a concrete trace (blocks 0..W-1 start in ways 0..W-1)."""
    _n, H, M = machine
    s, ways, out = 0, list(range(W)), []
    for b in trace:
        if b in ways:
            s = H[s][ways.index(b)]; out.append(True)
        else:
            v, s = M[s]; ways[v] = b; out.append(False)
    return out


def random_trace(W, length, rng, fresh, recent=None):
    """Mix of re-accesses to recent blocks and fresh ones, so both hits and misses occur."""
    pool = list(range(W))
    trace = []
    for _ in range(length):
        if rng.random() < 0.35:
            b = next(fresh)
        else:
            b = rng.choice(pool[-(W + 2):])
        trace.append(b)
        pool.append(b)
    return trace


def determinism(box, rng, traces=6, length=40, reps=10):
    """Repeat traces; per position, is the hit count explained by one outcome plus flip noise?"""
    q = box.q
    worst = 0.0
    for _ in range(traces):
        t = random_trace(box.W, length, rng, box.fresh)
        counts = [0] * length
        for _ in range(reps):
            out = box.run(t)
            for j, h in enumerate(out):
                counts[j] += h
        for c in counts:
            lo = min(c, reps - c)  # disagreements with the majority
            # P(at least lo flips in reps) under noise q
            p = sum(math.comb(reps, j) * q ** j * (1 - q) ** (reps - j) for j in range(lo, reps + 1))
            worst = max(worst, -math.log10(max(p, 1e-300)))
    return worst


def verify(box, machine, rng, traces, length, reps, confirm=6):
    """Random concrete traces; a position whose majority disagrees with the prediction is rerun
    `confirm` more times and kept only if the disagreement survives. Returns the prefix or None."""
    for _ in range(traces):
        t = random_trace(box.W, length, rng, box.fresh)
        pred = predict(machine, t, box.W)
        counts = [0] * length
        for _ in range(reps):
            for j, h in enumerate(box.run(t)):
                counts[j] += h
        for j in range(length):
            if (counts[j] * 2 > reps) != pred[j]:
                c, n = counts[j], reps
                for _ in range(confirm):
                    c += box.run(t[: j + 1])[j]; n += 1
                if (c * 2 > n) != pred[j]:
                    return t[: j + 1]
    return None


def counterexample(box, machine, trace):
    """Walk the concrete prefix with true victims; the first miss where the hypothesis names a
    different victim ends an abstract counterexample."""
    _n, H, M = machine
    W = box.W
    ways, s, word = list(range(W)), 0, []
    for b in trace:
        if b in ways:
            i = ways.index(b); word.append(i); s = H[s][i]
        else:
            v = box.victim(tuple(word))
            if v != M[s][0]:
                return tuple(word) + ("M",)
            word.append("M"); ways[v] = b; s = M[s][1]
    return None


class LStar:
    def __init__(self, box, max_states):
        self.box, self.W, self.cap = box, box.W, max_states
        self.inputs = list(range(self.W)) + ["M"]
        self.E = [("M",)]
        self.S = [()]

    def cell(self, u, e):
        out = []
        w = tuple(u)
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
                        self.S.append(s + (a,)); rows[r] = s + (a,); added = True
                        if len(self.S) > self.cap:
                            raise Budget()
            if not added:
                return rows

    def hypothesis(self):
        rows = self.close()
        idx = {r: k for k, r in enumerate(rows)}
        # state 0 must be the empty prefix
        order = [self.row(())] + [r for r in rows if r != self.row(())]
        idx = {r: k for k, r in enumerate(order)}
        H, M = [None] * len(order), [None] * len(order)
        for r in order:
            s = rows[r]
            H[idx[r]] = [idx[self.row(s + (i,))] for i in range(self.W)]
            M[idx[r]] = (r[0][0], idx[self.row(s + ("M",))])
        return E.minimise(len(order), H, M)

    def add_counterexample(self, ce, hyp=None):
        if hyp is None:                       # Maler-Pnueli: every suffix
            for k in range(len(ce)):
                suf = tuple(ce[k:])
                if suf not in self.E:
                    self.E.append(suf)
            return
        # Rivest-Schapire: binary search for the index where swapping the prefix for the access
        # sequence of the state it reaches flips the last victim; add that one suffix.
        _n, H, M = hyp
        access = self.access(hyp)
        states = [0]
        for a in ce[:-1]:
            states.append(M[states[-1]][1] if a == "M" else H[states[-1]][a])

        def f(i):
            return self.box.victim(tuple(access[states[i]]) + tuple(ce[i:-1]))

        lo, hi = 0, len(ce) - 1          # f(lo) is the system's answer, f(hi) the hypothesis's
        target = f(lo)
        while hi - lo > 1:
            mid = (lo + hi) // 2
            if f(mid) == target:
                lo = mid
            else:
                hi = mid
        suf = tuple(ce[hi:])
        if suf not in self.E:
            self.E.append(suf)
        else:
            for k in range(len(ce)):
                suf = tuple(ce[k:])
                if suf not in self.E:
                    self.E.append(suf)

    def access(self, hyp):
        """Shortest abstract word reaching each hypothesis state."""
        _n, H, M = hyp
        acc = {0: ()}
        frontier = [0]
        while frontier:
            nxt = []
            for s in frontier:
                for a in self.inputs:
                    t = M[s][1] if a == "M" else H[s][a]
                    if t not in acc:
                        acc[t] = acc[s] + (a,); nxt.append(t)
            frontier = nxt
        return acc


def learn(box, rng, max_states=512, rounds=30, vtraces=12, vlen=20, vreps=5, det_threshold=6.0, rs=False):
    try:
        if determinism(box, rng) > det_threshold:
            return {"verdict": "no_policy", "why": "nondeterministic"}
        ls = LStar(box, max_states)
        for _ in range(rounds):
            hyp = ls.hypothesis()
            t = verify(box, hyp, rng, vtraces, vlen, vreps)
            if t is None:
                return {"verdict": "policy", "machine": hyp}
            ce = counterexample(box, hyp, t)
            if ce is None:
                continue
            ls.add_counterexample(ce, hyp if rs else None)
    except Budget:
        return {"verdict": "no_policy", "why": "budget"}
    return {"verdict": "no_policy", "why": "rounds"}


if __name__ == "__main__":
    import sys
    q = float(sys.argv[1]) if len(sys.argv) > 1 else 0.02
    budget = int(sys.argv[2]) if len(sys.argv) > 2 else 200000
    rs = len(sys.argv) > 3 and sys.argv[3] == "rs"
    worlds = {
        "fifo4": E.FIFO(4), "plru4": E.PLRU(4), "lru4": E.LRU(4), "nru4": E.AgeTable(4, 2, [0, 0], 0),
        "switch4": E.Switch(4, 4), "plru8": E.PLRU(8), "srrip_hp4": E.AgeTable(4, 4, [0, 0, 0, 0], 2),
        "bip4": E.BIP(4, 1 / 16), "srrip_rtie4": E.AgeTable(4, 4, [0, 0, 0, 0], 2, tie="random"),
    }
    for name, p in worlds.items():
        rng = random.Random(7)
        cache = E.Cache(p, q, 10 ** 9, seed=11)
        box = Box(cache, p.W, q, budget, rng)
        res = learn(box, rng, rs=rs)
        ok = None
        if res["verdict"] == "policy" and not p.randomized:
            ok = E.equivalent(res["machine"], E.machine(p)) is None
        print(name, res["verdict"], res.get("why", ""), "states", res["machine"][0] if "machine" in res else "-",
              "correct" if ok else ("WRONG" if ok is False else ""), "spent", box.spent, flush=True)


def predict_victim(machine, word):
    _n, H, M = machine
    s = 0
    for a in word[:-1]:
        s = M[s][1] if a == "M" else H[s][a]
    return M[s][0]
