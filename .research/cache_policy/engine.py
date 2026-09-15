"""Prototype engine for CacheReplacementPolicyID: policies, their abstract Mealy machines, equivalence.

A policy acts on one cache set of W ways. Its metadata is a hashable tuple. The abstract machine has
inputs Hit(i) (the block in way i is accessed) and Miss (a fresh block arrives); Miss outputs the
victim way. After reset, block i sits in way i and the metadata is what W fills produced.
"""
import itertools
import random
from collections import deque


class Policy:
    randomized = False

    def __init__(self, W):
        self.W = W

    def empty(self):
        raise NotImplementedError

    def hit(self, m, i, rng=None):
        raise NotImplementedError

    def fill(self, m, i, rng=None):
        """Metadata after inserting into way i (used both for the reset fills and after a miss)."""
        raise NotImplementedError

    def victim(self, m, rng=None):
        """(way, metadata before the fill) on a miss with every way valid."""
        raise NotImplementedError

    def reset(self, rng=None):
        m = self.empty()
        for i in range(self.W):
            m = self.fill(m, i, rng)
        return m

    def miss(self, m, rng=None):
        v, m = self.victim(m, rng)
        return v, self.fill(m, v, rng)


# ---- permutation-style: metadata is the order of ways, most protected first --------------------
class LRU(Policy):
    def empty(self):
        return ()

    def hit(self, m, i, rng=None):
        return (i,) + tuple(x for x in m if x != i)

    def fill(self, m, i, rng=None):
        return (i,) + tuple(x for x in m if x != i)

    def victim(self, m, rng=None):
        return m[-1], m[:-1]


class FIFO(LRU):
    def hit(self, m, i, rng=None):
        return m


class LIP(LRU):
    """Insert at the LRU end; hits promote to MRU."""
    def fill(self, m, i, rng=None):
        if len(m) < self.W - 0 and len(m) < self.W and self._filling(m):
            return (i,) + tuple(x for x in m if x != i)
        return tuple(x for x in m if x != i) + (i,)

    def _filling(self, m):
        return len(m) < self.W - 0 and not hasattr(self, "_steady")


class BIP(LRU):
    randomized = True

    def __init__(self, W, eps):
        super().__init__(W)
        self.eps = eps

    def fill(self, m, i, rng=None):
        if len(m) < self.W - 1 or (rng is not None and rng.random() < self.eps):
            return (i,) + tuple(x for x in m if x != i)
        return tuple(x for x in m if x != i) + (i,)


class PLRU(Policy):
    """Tree pseudo-LRU; W a power of two. Bits point toward the side to evict next."""
    def empty(self):
        return (0,) * (self.W - 1)

    def _touch(self, m, i):
        bits = list(m)
        node, lo, hi = 0, 0, self.W
        while hi - lo > 1:
            mid = (lo + hi) // 2
            if i < mid:
                bits[node] = 1          # point away: to the right half
                node, hi = 2 * node + 1, mid
            else:
                bits[node] = 0
                node, lo = 2 * node + 2, mid
        return tuple(bits)

    def hit(self, m, i, rng=None):
        return self._touch(m, i)

    def fill(self, m, i, rng=None):
        return self._touch(m, i)

    def victim(self, m, rng=None):
        node, lo, hi = 0, 0, self.W
        while hi - lo > 1:
            mid = (lo + hi) // 2
            if m[node] == 0:
                node, hi = 2 * node + 1, mid
            else:
                node, lo = 2 * node + 2, mid
        return lo, m


class AgeTable(Policy):
    """RRIP / QLRU-like: per-way age in 0..A-1; hit maps age by a table; insert at a fixed age;
    victim is the leftmost way at the maximum age, all ages aged until one reaches it
    (or, for tie='random', a random way among those at the maximum)."""
    def __init__(self, W, A, hit_table, insert_age, tie="left", age_all=True):
        super().__init__(W)
        self.A, self.table, self.ins, self.tie, self.age_all = A, tuple(hit_table), insert_age, tie, age_all
        self.randomized = tie == "random"

    def empty(self):
        return (self.A - 1,) * self.W

    def hit(self, m, i, rng=None):
        m = list(m)
        m[i] = self.table[m[i]]
        return tuple(m)

    def fill(self, m, i, rng=None):
        m = list(m)
        m[i] = self.ins
        return tuple(m)

    def victim(self, m, rng=None):
        top = self.A - 1
        if self.age_all:
            d = top - max(m)
            m = tuple(a + d for a in m)
            cands = [i for i, a in enumerate(m) if a == top]
        else:
            mx = max(m)
            cands = [i for i, a in enumerate(m) if a == mx]
        if self.tie == "random" and rng is not None:
            return rng.choice(cands), m
        return cands[0], m


class PermutationPolicy(Policy):
    """Abel-Reineke permutation policy: order of ways; a hit at position p applies hit[p]; a miss
    evicts position W-1, inserts at position 0, then applies miss."""
    def __init__(self, W, hit_perms, miss_perm, start=None):
        super().__init__(W)
        self.hp, self.mp = [tuple(p) for p in hit_perms], tuple(miss_perm)
        self.start = tuple(start) if start is not None else tuple(range(W))

    def empty(self):
        return ()

    def fill(self, m, i, rng=None):
        if len(m) < self.W:
            return (i,) + m if len(m) == self.W - 1 else (i,) + m
        raise AssertionError

    def reset(self, rng=None):
        return self.start

    def hit(self, m, i, rng=None):
        p = m.index(i)
        return tuple(m[self.hp[p][k]] for k in range(self.W))

    def miss(self, m, rng=None):
        v = m[-1]
        order = (v,) + m[:-1]
        return v, tuple(order[self.mp[k]] for k in range(self.W))


class Switch(Policy):
    """Deterministic adaptive insertion: LRU, but after `k` misses in a row it inserts at the LRU end
    until the next hit. Metadata is (order, run length)."""
    def __init__(self, W, k):
        super().__init__(W)
        self.k = k

    def reset(self, rng=None):
        return (tuple(range(self.W - 1, -1, -1)), 0)

    def hit(self, m, i, rng=None):
        order, _ = m
        return ((i,) + tuple(x for x in order if x != i), 0)

    def miss(self, m, rng=None):
        order, run = m
        v, rest = order[-1], order[:-1]
        if run >= self.k:
            return v, (rest + (v,), min(run + 1, self.k))
        return v, ((v,) + rest, min(run + 1, self.k))


# ---- machines ------------------------------------------------------------------------------------
def machine(policy, cap=100000):
    """Reachable abstract machine of a deterministic policy, minimised. Returns (n, hit, miss) with
    state 0 initial, hit[s][i] the next state, miss[s] = (victim, next state)."""
    W = policy.W
    start = policy.reset()
    index, states, queue = {start: 0}, [start], deque([start])
    raw_hit, raw_miss = [], []
    while queue:
        m = queue.popleft()
        row = []
        for i in range(W):
            n = policy.hit(m, i)
            if n not in index:
                index[n] = len(states); states.append(n); queue.append(n)
            row.append(index[n])
        v, n = policy.miss(m)
        if n not in index:
            index[n] = len(states); states.append(n); queue.append(n)
        raw_hit.append(row); raw_miss.append((v, index[n]))
        if len(states) > cap:
            raise ValueError("over cap")
    return minimise(len(states), raw_hit, raw_miss)


def minimise(n, hit, miss):
    part = [miss[s][0] for s in range(n)]
    while True:
        sig = [(part[s], tuple(part[t] for t in hit[s]), part[miss[s][1]]) for s in range(n)]
        ids = {}
        new = [ids.setdefault(x, len(ids)) for x in sig]
        if len(ids) == len(set(part)):
            break
        part = new
    # renumber so the initial state is 0, in BFS order
    order, seen, q = [], {part[0]: 0}, deque([0])
    rep = {}
    for s in range(n):
        rep.setdefault(part[s], s)
    while q:
        s = q.popleft(); order.append(s)
        for t in list(hit[s]) + [miss[s][1]]:
            if part[t] not in seen:
                seen[part[t]] = len(seen); q.append(rep[part[t]])
    k = len(seen)
    H = [None] * k; M = [None] * k
    for c, idx in seen.items():
        s = rep[c]
        H[idx] = [seen[part[t]] for t in hit[s]]
        M[idx] = (miss[s][0], seen[part[miss[s][1]]])
    return k, H, M


def equivalent(a, b):
    """Product BFS of two abstract machines; returns None if equivalent, else a distinguishing word."""
    (_, h1, m1), (_, h2, m2) = a, b
    W = len(h1[0])
    seen = {(0, 0): None}
    q = deque([(0, 0)])
    while q:
        s, t = q.popleft()
        if m1[s][0] != m2[t][0]:
            word, cur = ["M"], (s, t)
            while seen[cur] is not None:
                prev, sym = seen[cur]; word.append(sym); cur = prev
            return word[::-1]
        for sym, nxt in [(i, (h1[s][i], h2[t][i])) for i in range(W)] + [("M", (m1[s][1], m2[t][1]))]:
            if nxt not in seen:
                seen[nxt] = ((s, t), sym); q.append(nxt)
    return None


# ---- the concrete, noisy black box ----------------------------------------------------------------
class Cache:
    def __init__(self, policy, noise, budget, seed):
        self.p, self.q, self.left = policy, noise, budget
        self.rng = random.Random(seed)

    def run(self, trace):
        W = self.p.W
        cost = W + len(trace)
        if cost > self.left:
            raise ValueError("budget")
        self.left -= cost
        rng = self.rng
        m = self.p.reset(rng)
        ways = list(range(W))
        out = []
        for b in trace:
            if b in ways:
                i = ways.index(b)
                m = self.p.hit(m, i, rng); h = True
            else:
                v, m = self.p.miss(m, rng); ways[v] = b; h = False
            out.append(h if rng.random() >= self.q else not h)
        return out


if __name__ == "__main__":
    W4 = 4
    cases = {
        "lru4": LRU(4), "fifo4": FIFO(4), "plru4": PLRU(4), "plru8": PLRU(8),
        "srrip_hp4": AgeTable(4, 4, [0, 0, 0, 0], 2), "srrip_fp4": AgeTable(4, 4, [0, 0, 1, 2], 2),
        "nru4": AgeTable(4, 2, [0, 0], 0), "nru8": AgeTable(8, 2, [0, 0], 0),
        "qlru_like4": AgeTable(4, 4, [0, 0, 1, 1], 3, age_all=True),
        "switch4_k4": Switch(4, 4), "switch4_k8": Switch(4, 8),
        "lru6": LRU(6), "srrip_hp8": AgeTable(8, 4, [0, 0, 0, 0], 2),
    }
    for name, p in cases.items():
        try:
            k, H, M = machine(p, cap=200000)
            print(name, "states", k)
        except ValueError as e:
            print(name, e)
    # PLRU as a permutation policy? compare to LRU etc.
    a = machine(LRU(4)); b = machine(FIFO(4))
    print("lru vs fifo distinguishing", equivalent(a, b))
    print("lru vs lru", equivalent(a, machine(LRU(4))))


class AgeOnMiss(AgeTable):
    """Unnamed variant: after every fill, each other way ages by one (saturating); no aging loop."""
    def fill(self, m, i, rng=None):
        m = [min(a + 1, self.A - 1) for a in m]
        m[i] = self.ins
        return tuple(m)

    def victim(self, m, rng=None):
        mx = max(m)
        return [i for i, a in enumerate(m) if a == mx][0], m


class PLRUFallback(PLRU):
    """Tree PLRU whose victim is, with probability p, a uniformly random way."""
    randomized = True

    def __init__(self, W, p):
        super().__init__(W)
        self.p = p

    def victim(self, m, rng=None):
        if rng is not None and rng.random() < self.p:
            return rng.randrange(self.W), m
        return super().victim(m, rng)


def random_permutation_policy(W, seed):
    r = random.Random(seed)
    def perm():
        p = list(range(W)); r.shuffle(p); return p
    return PermutationPolicy(W, [perm() for _ in range(W)], perm())


def lip_like(W, insert_at, seed):
    """Permutation policy that inserts at position `insert_at` (W-1 is LIP) with random hit vectors."""
    r = random.Random(seed)
    hp = []
    for _ in range(W):
        p = list(range(W)); r.shuffle(p); hp.append(p)
    order = list(range(1, W))
    order.insert(insert_at, 0)
    return PermutationPolicy(W, hp, order)
