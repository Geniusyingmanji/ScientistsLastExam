"""Hidden oracle for CacheReplacementPolicyID.

One set of a set-associative cache sits behind a black box. When a block that is not in the set
is accessed, the replacement policy decides which resident block leaves, and the hardware
documents none of it. The candidate plays access traces from a fixed reset state, one charged
run at a time, and reads back which accesses hit, through a timing channel that misreports each
outcome with a known small probability. It then either writes the policy down as a deterministic
machine over the ways, or declines, which is the right answer when no deterministic policy
produced what it saw.

The machine is scored exactly. The oracle knows the policy, builds its reachable machine and
compares the submission with it by a search over pairs of states: the two agree on every trace
from reset or they do not, and nothing about the score is a statistical estimate. A machine
that differs anywhere is a false discovery, and it costs one world wherever it is made: minus one
where the policy is deterministic and declining scores zero, zero where the policy is randomised
and declining scores one. Without the first half a learner could submit whatever its last
hypothesis was in every world it could not finish, at no cost.

What makes it hard:

    noise              every outcome is misreported with probability 0.02, so one run proves
                       little; learning which way a miss evicts takes repeated runs of the same
                       prefix, and the budget is shared with every other question
    size               the reachable machines have 15 to 720 states, and the generic ways to
                       learn a machine run out of budget well before the largest of them
    unnamed policies   two development policies are textbook policies; the others are variants
                       of the kinds hardware ships, with their tables drawn at random, so a
                       library of known policies recovers little
    randomness that    three development policies are randomised, two of them rarely: one miss
    hides in noise     in 64 inserts at the other end, or one eviction in 32 picks a way at
                       random; majority votes over repeated runs absorb both into what looks like
                       a deterministic policy and the channel's own noise
    deep states        one deterministic policy changes how it inserts only after a run of
                       misses; a machine learned from short traces agrees with it on almost
                       every trace and is wrong
"""
from __future__ import annotations

import hashlib
import math
import random
from collections import deque

import numpy as np

NOISE = 0.02
RUN_BUDGET = 200_000
MAX_TRACE = 4096
MAX_STATES = 1024
MAX_BLOCK = 2 ** 31 - 1
TRUTH_CAP = 100_000


# ---- policies ----------------------------------------------------------------------------------
# A policy acts on one set of W ways. Its metadata is a tuple; `reset` gives the metadata after the
# set is flushed and blocks 0..W-1 are loaded into ways 0..W-1 in that order; `hit` updates it when
# the block in way i is accessed; `miss` returns the victim way and the metadata after the new
# block has taken that way. Randomised policies draw from the run's generator.

class _LRU:
    randomized = False

    def __init__(self, W):
        self.W = W

    def reset(self, rng=None):
        return tuple(range(self.W - 1, -1, -1))

    def hit(self, m, i, rng=None):
        return (i,) + tuple(x for x in m if x != i)

    def miss(self, m, rng=None):
        v = m[-1]
        return v, (v,) + m[:-1]


class _PLRU:
    """Tree pseudo-LRU over a power-of-two number of ways; each bit points to the half that is
    evicted next, and touching a way points every bit on its path away from it."""
    randomized = False

    def __init__(self, W):
        self.W = W

    def _touch(self, m, i):
        bits = list(m)
        node, lo, hi = 0, 0, self.W
        while hi - lo > 1:
            mid = (lo + hi) // 2
            if i < mid:
                bits[node] = 1
                node, hi = 2 * node + 1, mid
            else:
                bits[node] = 0
                node, lo = 2 * node + 2, mid
        return tuple(bits)

    def _victim(self, m):
        node, lo, hi = 0, 0, self.W
        while hi - lo > 1:
            mid = (lo + hi) // 2
            if m[node] == 0:
                node, hi = 2 * node + 1, mid
            else:
                node, lo = 2 * node + 2, mid
        return lo

    def reset(self, rng=None):
        m = (0,) * (self.W - 1)
        for i in range(self.W):
            m = self._touch(m, i)
        return m

    def hit(self, m, i, rng=None):
        return self._touch(m, i)

    def miss(self, m, rng=None):
        v = self._victim(m)
        return v, self._touch(m, v)


class _PLRUFallback(_PLRU):
    """Tree pseudo-LRU whose victim is, with probability `p`, a way drawn uniformly."""
    randomized = True

    def __init__(self, W, p):
        super().__init__(W)
        self.p = p

    def miss(self, m, rng=None):
        v = rng.randrange(self.W) if rng.random() < self.p else self._victim(m)
        return v, self._touch(m, v)


class _AgeTable:
    """A per-way age in 0..A-1. A hit maps the way's age through `table`; a new block enters at
    age `insert`. The victim is the leftmost way at the largest age; with `age_all`, every age is
    first raised until one reaches A-1, and with `tie_random` the victim is drawn uniformly among
    the ways at that age."""

    def __init__(self, W, A, table, insert, age_all=True, tie_random=False):
        self.W, self.A, self.table, self.insert = W, A, tuple(table), insert
        self.age_all, self.tie_random = age_all, tie_random
        self.randomized = tie_random

    def _fill(self, m, i):
        m = list(m)
        m[i] = self.insert
        return tuple(m)

    def reset(self, rng=None):
        m = (self.A - 1,) * self.W
        for i in range(self.W):
            m = self._fill(m, i)
        return m

    def hit(self, m, i, rng=None):
        m = list(m)
        m[i] = self.table[m[i]]
        return tuple(m)

    def miss(self, m, rng=None):
        top = max(m)
        if self.age_all:
            shift = self.A - 1 - top
            m = tuple(a + shift for a in m)
            top = self.A - 1
        candidates = [i for i, a in enumerate(m) if a == top]
        v = rng.choice(candidates) if self.tie_random else candidates[0]
        return v, self._fill(m, v)


class _AgeOnMiss(_AgeTable):
    """As `_AgeTable`, except that every fill ages each other way by one, saturating, and the
    victim is simply the leftmost way at the largest age."""

    def _fill(self, m, i):
        m = [min(a + 1, self.A - 1) for a in m]
        m[i] = self.insert
        return tuple(m)

    def reset(self, rng=None):
        m = (self.A - 1,) * self.W
        for i in range(self.W):
            m = self._fill(m, i)
        return m

    def miss(self, m, rng=None):
        top = max(m)
        v = [i for i, a in enumerate(m) if a == top][0]
        return v, self._fill(m, v)


class _Permutation:
    """A permutation policy in the sense of Abel and Reineke: the metadata is an order of the ways,
    position 0 first; a hit on the way at position p reorders by `hit[p]`; a miss evicts the way at
    the last position, puts the new block at position 0 and reorders by `miss`."""
    randomized = False

    def __init__(self, W, hit, miss, start):
        self.W = W
        self.hp = tuple(tuple(p) for p in hit)
        self.mp = tuple(miss)
        self.start = tuple(start)

    def reset(self, rng=None):
        return self.start

    def hit(self, m, i, rng=None):
        p = m.index(i)
        return tuple(m[k] for k in self.hp[p])

    def miss(self, m, rng=None):
        v = m[-1]
        order = (v,) + m[:-1]
        return v, tuple(order[k] for k in self.mp)


class _Switch:
    """LRU, except that after `k` misses in a row a new block enters at the evict-next end, until
    the next hit. The metadata is the order and the length of the current run of misses."""
    randomized = False

    def __init__(self, W, k):
        self.W, self.k = W, k

    def reset(self, rng=None):
        return tuple(range(self.W - 1, -1, -1)), 0

    def hit(self, m, i, rng=None):
        order, _run = m
        return (i,) + tuple(x for x in order if x != i), 0

    def miss(self, m, rng=None):
        order, run = m
        v, rest = order[-1], order[:-1]
        nxt = min(run + 1, self.k)
        return v, ((rest + (v,)) if run >= self.k else ((v,) + rest), nxt)


class _Bimodal:
    """LRU hits; a new block enters at the evict-next end, except with probability `eps` at the
    other end. The first W - 1 loads after a flush enter at the protected end."""
    randomized = True

    def __init__(self, W, eps):
        self.W, self.eps = W, eps

    def _fill(self, m, i, rng):
        if len(m) < self.W - 1 or rng.random() < self.eps:
            return (i,) + tuple(x for x in m if x != i)
        return tuple(x for x in m if x != i) + (i,)

    def reset(self, rng=None):
        m = ()
        for i in range(self.W):
            m = self._fill(m, i, rng)
        return m

    def hit(self, m, i, rng=None):
        return (i,) + tuple(x for x in m if x != i)

    def miss(self, m, rng=None):
        v = m[-1]
        return v, self._fill(m[:-1], v, rng)


# ---- machines ----------------------------------------------------------------------------------
def _minimise(n, hit, miss):
    """Moore partition refinement on a machine whose only outputs are the victims of misses; the
    result is renumbered breadth-first from the initial state."""
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


def policy_machine(policy, cap=TRUTH_CAP):
    """The reachable machine of a deterministic policy, minimised."""
    W = policy.W
    start = policy.reset()
    index, states, queue = {start: 0}, [start], deque([start])
    hit, miss = [], []
    while queue:
        m = queue.popleft()
        row = []
        for i in range(W):
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
            raise ValueError("policy machine above the cap")
    return _minimise(len(states), hit, miss)


def distinguishing_word(a, b):
    """Shortest input word from reset after which the two machines evict different ways, as a list
    of way indices and "M"; None when they agree on every word."""
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
        steps = [(i, (ha[s][i], hb[t][i])) for i in range(W)] + [("M", (ma[s][1], mb[t][1]))]
        for symbol, nxt in steps:
            if nxt not in parent:
                parent[nxt] = ((s, t), symbol)
                queue.append(nxt)
    return None


# ---- the black box -----------------------------------------------------------------------------
def _trace(value):
    if not isinstance(value, (list, tuple)) or not value:
        raise ValueError("a trace is a non-empty list of block addresses")
    if len(value) > MAX_TRACE:
        raise ValueError("a trace holds at most %d accesses" % MAX_TRACE)
    out = []
    for b in value:
        if isinstance(b, bool) or not isinstance(b, (int, np.integer)):
            raise ValueError("block addresses must be integers")
        b = int(b)
        if not 0 <= b <= MAX_BLOCK:
            raise ValueError("block addresses must lie in 0..%d" % MAX_BLOCK)
        out.append(b)
    return out


def _execute(policy, blocks, noise, rng):
    m = policy.reset(rng)
    ways = list(range(policy.W))
    where = {b: i for i, b in enumerate(ways)}
    out = []
    for b in blocks:
        i = where.get(b)
        if i is not None:
            m = policy.hit(m, i, rng)
            hit = True
        else:
            v, m = policy.miss(m, rng)
            del where[ways[v]]
            ways[v] = b
            where[b] = v
            hit = False
        out.append(hit != (rng.random() < noise))
    return out


class _Bench:
    """The candidate's only access to the cache. The candidate receives the closure, not this
    object, so the ledger is out of its reach. Each run is seeded by the world, the trace and how
    many times that trace has been run before, so what a candidate sees does not depend on the
    order of its calls."""

    def __init__(self, world):
        self.world = world
        self.budget = world["budget"]
        self.spent = 0
        self.calls = {}
        self.violated = False

    def oracle(self):
        world, state = self.world, self
        policy, seed, noise = world["policy"], int(world["spec"]["seed"]), world["noise"]

        def run(trace):
            try:
                blocks = _trace(trace)
            except (ValueError, TypeError):
                state.violated = True
                raise
            cost = policy.W + len(blocks)
            if state.spent + cost > state.budget:
                state.violated = True
                raise RuntimeError("run budget exhausted")
            state.spent += cost
            key = tuple(blocks)
            count = state.calls.get(key, 0)
            state.calls[key] = count + 1
            digest = hashlib.blake2b(np.asarray(blocks, dtype=np.int64).tobytes(),
                                     key=("%d:%d" % (seed, count)).encode(), digest_size=16)
            return _execute(policy, blocks, noise, random.Random(int.from_bytes(digest.digest(), "little")))

        return run


# ---- the problem and the answer ----------------------------------------------------------------
PUBLIC_PROBLEM = {
    "ways": None,
    "noise": NOISE,
    "run_budget": RUN_BUDGET,
    "max_trace_length": MAX_TRACE,
    "max_states": MAX_STATES,
    "reset": "every run starts from the policy's prescribed reset procedure with blocks "
             "0, 1, ..., ways-1 resident, block i in way i; deterministic policies reset to "
             "the same metadata, while a randomized policy may draw fresh reset metadata",
    "run_model": "run(trace) plays the trace, a list of integer block addresses in "
                 "0..2147483647 that all map to this set, from the reset state and returns one "
                 "boolean per access, True for a hit; a block is a hit exactly when it is in the "
                 "set, and a miss brings it in and evicts one resident block; each reported "
                 "outcome is flipped independently with probability noise; a run costs ways + "
                 "len(trace) accesses against run_budget, since the reset loads count",
    "machine_model": "a policy is written as a deterministic machine over the ways: states "
                     "0..n-1 with state 0 the state after reset; hit[s][i] is the next state when "
                     "the block in way i is accessed; miss[s] = [victim, next] when a block not "
                     "in the set is accessed, the block in way victim leaving and the new block "
                     "taking that way; two machines are the same policy when they evict the same "
                     "way after every sequence of accesses from reset",
    "answer_format": "verdict is policy or no_policy; a policy carries machine, a mapping with "
                     "hit, a list of n rows of ways next states, and miss, a list of n pairs "
                     "[victim way, next state], n at most max_states",
}


def _public_problem(world):
    problem = dict(PUBLIC_PROBLEM)
    problem.update({"ways": world["policy"].W, "noise": world["noise"], "run_budget": world["budget"]})
    return problem


def _integer(value, low, high, what):
    if isinstance(value, bool) or not isinstance(value, (int, np.integer)):
        raise ValueError("%s must be an integer" % what)
    value = int(value)
    if not low <= value <= high:
        raise ValueError("%s must lie in %d..%d" % (what, low, high))
    return value


def _validate_submission(submission, W):
    if not isinstance(submission, dict):
        raise ValueError("submission must be a mapping")
    confidence = float(submission.get("confidence", 0.0))
    if not math.isfinite(confidence):
        raise ValueError("confidence must be finite")
    confidence = float(np.clip(confidence, 0.0, 1.0))
    if submission.get("abstain", False) is True:
        return None, confidence
    verdict = submission.get("verdict")
    if verdict == "no_policy":
        return None, confidence
    if verdict != "policy":
        raise ValueError("verdict must be 'policy' or 'no_policy'")
    machine = submission.get("machine")
    if not isinstance(machine, dict):
        raise ValueError("machine must be a mapping with hit and miss")
    hit, miss = machine.get("hit"), machine.get("miss")
    if not isinstance(hit, (list, tuple)) or not isinstance(miss, (list, tuple)):
        raise ValueError("hit and miss must be lists")
    n = len(hit)
    if not 1 <= n <= MAX_STATES or len(miss) != n:
        raise ValueError("hit and miss must both have n rows, 1 <= n <= %d" % MAX_STATES)
    H, M = [], []
    for row in hit:
        if not isinstance(row, (list, tuple)) or len(row) != W:
            raise ValueError("every hit row lists one next state per way")
        H.append([_integer(t, 0, n - 1, "a next state") for t in row])
    for pair in miss:
        if not isinstance(pair, (list, tuple)) or len(pair) != 2:
            raise ValueError("every miss row is a pair [victim, next]")
        M.append((_integer(pair[0], 0, W - 1, "a victim way"), _integer(pair[1], 0, n - 1, "a next state")))
    return (n, H, M), confidence


def _metrics(world, machine):
    blank = {"recovered": False, "mechanism_score": 0.0, "false_discovery": False, "correct_refusal": False}
    refusal_world = world["kind"] == "randomized"
    if machine is None:
        blank.update({"mechanism_score": 1.0 if refusal_world else 0.0, "correct_refusal": refusal_world})
        return blank
    if refusal_world or distinguishing_word(machine, world["truth"]) is not None:
        # A machine that is not the policy is a false discovery, and in a randomised world every
        # machine is one. It costs one world wherever it is made: zero where declining would have
        # scored one, and minus one where declining scores zero.
        blank["false_discovery"] = True
        blank["mechanism_score"] = 0.0 if refusal_world else -1.0
        return blank
    blank.update({"recovered": True, "mechanism_score": 1.0})
    return blank


# ---- the worlds --------------------------------------------------------------------------------
# Tables for the permutation policies were drawn once with a seeded generator
# (.research/cache_policy/engine.py) and are written out here, so the worlds do not depend on how
# any library shuffles. Truth machines are rebuilt from the policies on every run.
def _w(name, kind, seed, policy):
    return {"name": name, "kind": kind, "seed": seed, "policy": policy}


DEVELOPMENT_WORLDS = (
    _w("dev-01", "deterministic", 61300101, lambda: _AgeTable(4, 4, (0, 0, 1, 1), 3)),
    _w("dev-02", "deterministic", 61300102, lambda: _AgeTable(4, 4, (0, 0, 0, 1), 2, age_all=False)),
    _w("dev-03", "deterministic", 61300103, lambda: _Permutation(
        4, [[0, 3, 2, 1], [1, 2, 0, 3], [0, 2, 3, 1], [0, 2, 3, 1]], [2, 3, 1, 0], [0, 1, 2, 3])),
    _w("dev-04", "deterministic", 61300104, lambda: _Permutation(
        4, [[3, 2, 1, 0], [1, 2, 3, 0], [0, 1, 2, 3], [3, 1, 0, 2]], [1, 2, 0, 3], [0, 1, 2, 3])),
    _w("dev-05", "deterministic", 61300105, lambda: _LRU(4)),
    _w("dev-06", "deterministic", 61300106, lambda: _Permutation(
        6, [[2, 3, 5, 0, 4, 1], [0, 1, 2, 4, 5, 3], [2, 5, 4, 3, 0, 1], [5, 1, 2, 0, 4, 3],
            [5, 3, 4, 0, 1, 2], [2, 3, 1, 4, 5, 0]], [0, 1, 2, 3, 4, 5], [0, 1, 2, 3, 4, 5])),
    _w("dev-07", "deterministic", 61300107, lambda: _PLRU(8)),
    _w("dev-08", "deterministic", 61300108, lambda: _Switch(4, 4)),
    _w("dev-09", "deterministic", 61300109, lambda: _AgeOnMiss(4, 4, (0, 0, 1, 1), 1)),
    _w("dev-10", "randomized", 61300110, lambda: _Bimodal(4, 1.0 / 64.0)),
    _w("dev-11", "randomized", 61300111, lambda: _PLRUFallback(4, 1.0 / 32.0)),
    _w("dev-12", "randomized", 61300112, lambda: _AgeTable(4, 4, (0, 0, 0, 0), 2, tie_random=True)),
)

HELDOUT_WORLDS = (
    _w("held-01", "deterministic", 72400201, lambda: _AgeTable(4, 4, (0, 1, 1, 2), 1)),
    _w("held-02", "deterministic", 72400202, lambda: _Permutation(
        4, [[3, 2, 1, 0], [3, 1, 0, 2], [2, 0, 1, 3], [0, 3, 2, 1]], [3, 2, 1, 0], [0, 1, 2, 3])),
    _w("held-03", "deterministic", 72400203, lambda: _Permutation(
        6, [[5, 0, 1, 2, 4, 3], [4, 5, 3, 2, 0, 1], [1, 5, 3, 2, 0, 4], [0, 4, 2, 1, 3, 5],
            [4, 2, 0, 1, 3, 5], [3, 4, 2, 1, 5, 0]], [0, 1, 2, 3, 4, 5], [0, 1, 2, 3, 4, 5])),
    _w("held-04", "deterministic", 72400204, lambda: _AgeOnMiss(4, 4, (0, 1, 1, 2), 2)),
    _w("held-05", "randomized", 72400205, lambda: _Bimodal(4, 1.0 / 32.0)),
    _w("held-06", "randomized", 72400206, lambda: _PLRUFallback(4, 1.0 / 16.0)),
)

_WORLDS = {}


def _world(spec):
    key = spec["name"]
    if key not in _WORLDS:
        policy = spec["policy"]()
        truth = None if policy.randomized else policy_machine(policy)
        _WORLDS[key] = {"spec": spec, "kind": spec["kind"], "policy": policy, "truth": truth,
                        "noise": NOISE, "budget": RUN_BUDGET}
    return _WORLDS[key]


ROW_KEYS = ("recovered", "mechanism_score", "false_discovery", "correct_refusal")


def _evaluate_world(identify, spec, split, index):
    # Reset only at a scientific-world boundary, preserving every run callback
    # within that world. Runtime reset failure must escape scientific scoring.
    reset_session = getattr(identify, "reset_session", None)
    if callable(reset_session):
        reset_session()
    world = _world(spec)
    bench = _Bench(world)
    problem = _public_problem(world)
    base = {"split": split, "world_index": int(index), "kind": world["kind"], "runs_used": 0}
    try:
        submission = identify(problem, bench.oracle())
        machine, confidence = _validate_submission(submission, world["policy"].W)
        if bench.violated:
            raise RuntimeError("invalid trace or run budget exceeded")
        metrics = _metrics(world, machine)
        target = max(metrics["mechanism_score"], 0.0)
        row = dict(base)
        row.update({key: metrics[key] for key in ROW_KEYS})
        row.update({
            "valid": True,
            "abstained": machine is None,
            "states_submitted": 0 if machine is None else machine[0],
            "confidence": round(confidence, 6),
            "confidence_calibration_score": round(1.0 - (confidence - target) ** 2, 6),
            "runs_used": bench.spent,
        })
        row["mechanism_score"] = round(float(row["mechanism_score"]), 6)
        return row
    except Exception as exc:  # noqa: BLE001 - a bad candidate scores zero, it does not crash this
        row = dict(base)
        row.update({key: (0.0 if key.endswith("_score") else False) for key in ROW_KEYS})
        row.update({
            "valid": False,
            "reason": "%s: %s" % (type(exc).__name__, exc),
            "abstained": True,
            "states_submitted": 0,
            "confidence": 0.0,
            "confidence_calibration_score": 0.0,
            "runs_used": bench.spent,
        })
        return row


def _split_summary(records):
    determinable = [r for r in records if r["kind"] == "deterministic"]
    unsupported = [r for r in records if r["kind"] == "randomized"]
    raw = float(np.mean([r["mechanism_score"] for r in records]))
    always_abstain = len(unsupported) / len(records)
    normalized = float(np.clip((raw - always_abstain) / (1.0 - always_abstain), 0.0, 1.0))
    claims = [r for r in records if r["valid"] and not r["abstained"]]
    false_claim_count = sum(bool(r["false_discovery"]) for r in claims)
    return {
        "normalized_mechanism": normalized,
        "raw_mechanism": raw,
        "policy_recovery": float(np.mean([r["recovered"] for r in determinable])),
        "false_discovery_rate": false_claim_count / len(claims) if claims else 0.0,
        "false_claim_world_rate": float(np.mean([r["false_discovery"] for r in records])),
        "false_claim_count": false_claim_count,
        "policy_claim_count": len(claims),
        "correct_refusal_rate": float(np.mean([r["correct_refusal"] for r in unsupported])),
        "discovery_coverage": float(np.mean([not r["abstained"] for r in determinable])),
        "confidence_calibration": float(np.mean([r["confidence_calibration_score"] for r in records])),
        "mean_runs_used": float(np.mean([r["runs_used"] for r in records])),
        "valid_count": sum(bool(r["valid"]) for r in records),
        "world_count": len(records),
        "determinable_world_count": len(determinable),
        "unsupported_world_count": len(unsupported),
        "false_discovery_count": sum(bool(r["false_discovery"]) for r in records),
        "correct_refusal_count": sum(bool(r["correct_refusal"]) for r in unsupported),
        "discovery_attempt_count": sum(not r["abstained"] for r in determinable),
        "mechanism_score_sum": sum(float(r["mechanism_score"]) for r in records),
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
        "development_policy_recovery": dev["policy_recovery"],
        "development_false_discovery_rate": dev["false_discovery_rate"],
        "development_correct_refusal_rate": dev["correct_refusal_rate"],
        "development_discovery_coverage": dev["discovery_coverage"],
        "development_confidence_calibration": dev["confidence_calibration"],
        "development_mean_runs_used": dev["mean_runs_used"],
        # Evaluator-only: the sealed split is removed from the search-visible metric view by the
        # visibility contract, so a searcher cannot steer on it.
        "heldout_mechanism_score": held["normalized_mechanism"],
        "heldout_policy_recovery": held["policy_recovery"],
        "heldout_false_discovery_rate": held["false_discovery_rate"],
        "heldout_correct_refusal_rate": held["correct_refusal_rate"],
        "heldout_discovery_coverage": held["discovery_coverage"],
        "per_instance": development + heldout,
    }
    for split, summary in (("development", dev), ("heldout", held)):
        for key in ("valid_count", "world_count", "determinable_world_count",
                    "unsupported_world_count", "false_discovery_count",
                    "correct_refusal_count", "discovery_attempt_count", "mechanism_score_sum",
                    "false_claim_count", "policy_claim_count", "false_claim_world_rate"):
            result[split + "_" + key] = summary[key]
    return result
