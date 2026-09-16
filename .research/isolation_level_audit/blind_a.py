"""IsolationLevelAudit: name the level only when the budget bought enough real races.

Strategy
--------
Five anomaly classes, each one the thing that separates a rung of the ladder from the
rung above it:

    D  dirty read            -- permitted at most by read_uncommitted
    S  broken snapshot read  -- permitted at most by read_committed
    F  long fork             -- permitted at most by parallel_snapshot
    K  write skew            -- permitted at most by snapshot_isolation
    T  stale (non-real-time) -- permitted at most by serializable
    (nothing)                -- strict_serializable

Each witness is self-certifying: the pattern itself is impossible at any level above
the one listed, so no interleaving evidence is needed to trust it.  The candidate level
is the weakest level compatible with every class that fired, i.e. the minimum over the
classes observed.

Naming that candidate additionally requires *power*: enough genuine races of the shape
that would have exposed the level directly below.  A race is only genuine when both
participants provably took the weak path, and the only proof available is the operation
clock -- a lock-path transaction is never interrupted, so a foreign operation landing
strictly inside another transaction's operation span proves that transaction weak.
Opportunities are counted that way and compared against a per-class threshold; below it
the audit declines, which is worth 0 where a wrong name is worth -1.

Budget is spent adaptively: a short sweep over all four shapes locates the candidate,
then every remaining operation goes into the single shape that separates the candidate
from the rung below it.  If a weaker class fires along the way the candidate drops and
the target shape changes, so the search walks down the ladder on its own.
"""
from __future__ import annotations

import bisect

CANON = [
    "read_uncommitted",
    "read_committed",
    "parallel_snapshot",
    "snapshot_isolation",
    "serializable",
    "strict_serializable",
]

# anomaly class -> index of the strongest level that still permits it
CLASS_LEVEL = {"D": 0, "S": 1, "F": 2, "K": 3, "T": 4}

# to name level i we must rule out level i-1, whose distinguishing class is:
RULE_OUT = {1: "D", 2: "S", 3: "F", 4: "K", 5: "T"}

# how many proven races of a class we want before believing its absence
THRESH = {"D": 10, "S": 12, "F": 12, "K": 12, "T": 40}

# operation cost of one round of each batch shape (four sessions)
SHAPES = ("S", "K", "F", "T")


def _hashable(v):
    try:
        hash(v)
        return v
    except Exception:
        return repr(v)


def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _parse(rec):
    """Turn one transaction record into the derived form the detectors want."""
    if not isinstance(rec, dict):
        return None
    ops = rec.get("ops") or []
    at = rec.get("at") or []
    if not isinstance(ops, (list, tuple)):
        return None
    if not isinstance(at, (list, tuple)):
        at = []
    writes = {}          # key -> list of elements appended
    reads = []           # (key, set of elements, clock)
    seen = {}            # key -> union of elements read there
    clocks = []
    own = set()
    for i, op in enumerate(ops):
        if not isinstance(op, (list, tuple)) or len(op) < 2:
            continue
        kind, key = op[0], op[1]
        try:
            hash(key)
        except Exception:
            continue
        clk = at[i] if i < len(at) else None
        if _num(clk):
            clocks.append(clk)
        if kind == "a":
            e = _hashable(op[2]) if len(op) > 2 else None
            writes.setdefault(key, []).append(e)
            own.add(e)
        elif kind == "r":
            vals = op[2] if len(op) > 2 else []
            if not isinstance(vals, (list, tuple, set, frozenset)):
                vals = []
            s = set(_hashable(v) for v in vals)
            reads.append((key, s, clk))
            cur = seen.get(key)
            if cur is None:
                seen[key] = set(s)
            else:
                cur |= s
    clocks.sort()
    start = rec.get("start")
    end = rec.get("end")
    if not _num(start):
        start = clocks[0] if clocks else None
    if not _num(end):
        end = clocks[-1] if clocks else None
    return {
        "tid": rec.get("tid"),
        "session": rec.get("session"),
        "start": start,
        "end": end,
        "ok": rec.get("status") == "committed",
        "writes": writes,
        "reads": reads,
        "seen": seen,
        "own": own,
        "clocks": clocks,
        "weak": False,
        "keys": set(writes) | set(seen),
    }


def _overlap(a, b):
    if not (_num(a["start"]) and _num(a["end"]) and _num(b["start"]) and _num(b["end"])):
        return False
    return a["start"] < b["end"] and b["start"] < a["end"]


class _Auditor(object):
    def __init__(self, problem, run):
        self.run_fn = run
        lv = problem.get("levels")
        self.levels = list(lv) if isinstance(lv, (list, tuple)) and lv else list(CANON)
        self.budget = int(problem.get("budget") or 0)
        self.max_sessions = int(problem.get("max_sessions") or 4)
        self.max_txn = int(problem.get("max_ops_per_txn") or 8)
        self.max_batch = int(problem.get("max_ops_per_batch") or 400)
        if self.max_sessions < 1:
            self.max_sessions = 1
        if self.max_txn < 1:
            self.max_txn = 1
        if self.max_batch < 1:
            self.max_batch = 1
        self.spent = 0
        self.nextkey = 0
        self.fired = dict((c, 0) for c in CLASS_LEVEL)
        self.opp = dict((c, 0) for c in CLASS_LEVEL)
        self.weak_txns = 0
        self.total_txns = 0
        self.broken = False

    # ---------------------------------------------------------------- budget

    def left(self):
        return self.budget - self.spent

    def fresh(self, n):
        k = self.nextkey
        self.nextkey += n
        return [k + i for i in range(n)]

    # ---------------------------------------------------------------- shapes

    def _sessions(self):
        return min(4, self.max_sessions)

    def _emit(self, rows, rounds):
        """rows: callable(round) -> list of four per-session transaction lists."""
        ns = self._sessions()
        batch = [[] for _ in range(ns)]
        for _ in range(rounds):
            per = rows()
            for s in range(ns):
                for txn in per[s]:
                    if 1 <= len(txn) <= self.max_txn:
                        batch[s].append(list(txn))
        return batch

    def _round_K(self):
        a, b = self.fresh(2)
        return [
            [[["r", a], ["r", b], ["a", a]]],
            [[["r", a], ["r", b], ["a", b]]],
            [[["r", b], ["r", a], ["a", a]]],
            [[["r", b], ["r", a], ["a", b]]],
        ]

    def _round_F(self):
        # Four unrelated writes, then four observers that each already hold one
        # of them.  Every session both writes and observes, so one round offers
        # six candidate writer pairs instead of one.  The writers carry a second
        # operation purely so that an interleaving can prove them weak.
        a, b, c, d = self.fresh(4)
        obs = [["r", a], ["r", b], ["r", c], ["r", d]]
        if self.max_txn < 4:
            obs = obs[:self.max_txn]
        return [
            [[["a", a], ["r", a]], list(obs)],
            [[["a", b], ["r", b]], list(obs)],
            [[["a", c], ["r", c]], list(obs)],
            [[["a", d], ["r", d]], list(obs)],
        ]

    def _round_S(self):
        a, b = self.fresh(2)
        return [
            [[["a", a], ["a", b]]],
            [[["r", a], ["r", b]]],
            [[["r", b], ["r", a]]],
            [[["a", b], ["a", a]]],
        ]

    def _round_T(self):
        # one pair of keys for the whole batch, so every later read has committed
        # writes that finished before it in real time.  The readers take two
        # distinct keys rather than the same key twice: a repeated read would
        # confuse replica lag with a non-repeatable read, and reading both keys
        # also lets the fork detector work on this traffic.
        a, b = self._tkeys
        return [
            [[["a", a]]],
            [[["r", a], ["r", b]]],
            [[["a", b]]],
            [[["r", b], ["r", a]]],
        ]

    def _builder(self, shape):
        if shape == "K":
            return self._round_K
        if shape == "F":
            return self._round_F
        if shape == "T":
            self._tkeys = self.fresh(2)
            return self._round_T
        return self._round_S

    def do_batch(self, shape):
        if self.broken:
            return False
        rows = self._builder(shape)
        probe = self._emit(rows, 1)
        cost1 = sum(len(t) for s in probe for t in s)
        if cost1 <= 0:
            return False
        rounds = min(self.max_batch // cost1, self.left() // cost1)
        if rounds < 1:
            return False
        batch = self._emit(rows, rounds)
        cost = sum(len(t) for s in batch for t in s)
        if cost <= 0 or cost > self.max_batch or cost > self.left():
            return False
        self.spent += cost
        try:
            out = self.run_fn(batch)
        except Exception:
            self.broken = True
            return False
        recs = None
        if isinstance(out, dict):
            recs = out.get("transactions")
        if not isinstance(recs, (list, tuple)):
            return True
        try:
            self._analyze(recs)
        except Exception:
            pass
        return True

    # -------------------------------------------------------------- analysis

    def _analyze(self, recs):
        txs = []
        for rec in recs:
            t = _parse(rec)
            if t is not None:
                txs.append(t)
        if not txs:
            return
        self.total_txns += len(txs)

        # --- which transactions provably took the weak path -----------------
        events = []
        for t in txs:
            events.extend(t["clocks"])
        events.sort()
        for t in txs:
            cs = t["clocks"]
            if len(cs) < 2:
                continue
            lo, hi = cs[0], cs[-1]
            inside = bisect.bisect_left(events, hi) - bisect.bisect_right(events, lo)
            own_inside = len(cs) - 2
            if inside > own_inside:
                t["weak"] = True
                self.weak_txns += 1

        # --- indexes --------------------------------------------------------
        owner = {}                 # element -> transaction that wrote it
        aborted_elems = set()
        for t in txs:
            for k, es in t["writes"].items():
                for e in es:
                    owner[e] = t
                    if not t["ok"]:
                        aborted_elems.add(e)

        key_writers = {}           # key -> list of committed writers
        key_readers = {}           # key -> list of committed readers
        key_touch = {}             # key -> list of transactions
        for t in txs:
            for k in t["writes"]:
                key_touch.setdefault(k, []).append(t)
                if t["ok"]:
                    key_writers.setdefault(k, []).append(t)
            for k in t["seen"]:
                if k not in t["writes"]:
                    key_touch.setdefault(k, []).append(t)
                if t["ok"]:
                    key_readers.setdefault(k, []).append(t)

        # committed elements per key, ordered by commit clock
        comm = {}
        for k, ws in key_writers.items():
            rows = []
            for w in ws:
                if not _num(w["end"]):
                    continue
                for e in w["writes"].get(k, ()):
                    rows.append((w["end"], e, w))
            rows.sort(key=lambda r: r[0])
            comm[k] = rows

        self._detect_dirty(txs, owner, aborted_elems)
        self._detect_skew(txs, owner, key_writers)
        self._detect_fork(txs, comm)
        self._detect_write_skew(txs, key_touch)
        self._detect_stale(txs, comm)
        self._count_opportunities(txs, comm)

    # --- D: a committed reader saw an element whose writer aborted ----------

    def _detect_dirty(self, txs, owner, aborted_elems):
        if not aborted_elems:
            return
        for t in txs:
            if not t["ok"]:
                continue
            for k, s, _clk in t["reads"]:
                for e in (s & aborted_elems):
                    if owner.get(e) is not t:
                        self.fired["D"] += 1
                        return

    # --- S: reads that cannot all come from one snapshot --------------------

    def _detect_skew(self, txs, owner, key_writers):
        # (b) non-repeatable read inside one transaction
        for t in txs:
            if not t["ok"]:
                continue
            per = {}
            for k, s, _clk in t["reads"]:
                prev = per.get(k)
                cur = s - t["own"]
                if prev is not None and prev != cur:
                    self.fired["S"] += 1
                    return
                per[k] = cur
        # (a) partial visibility of one committed multi-key write
        for t in txs:
            if not t["ok"] or len(t["writes"]) < 2:
                continue
            for r in txs:
                if r is t or not r["ok"]:
                    continue
                saw = False
                lost = False
                for k, es in t["writes"].items():
                    got = r["seen"].get(k)
                    if got is None:
                        continue
                    hit = False
                    for e in es:
                        if e in got:
                            hit = True
                            break
                    if hit:
                        saw = True
                    else:
                        lost = True
                if saw and lost:
                    self.fired["S"] += 1
                    return

    # --- F: two observers that disagree about the order of two writes -------

    def _detect_fork(self, txs, comm):
        obs = []
        for t in txs:
            if not t["ok"] or not t["seen"]:
                continue
            seen = set()
            lost = set()
            for k, got in t["seen"].items():
                rows = comm.get(k)
                if not rows:
                    continue
                for _end, e, w in rows:
                    if w is t:
                        continue
                    if e in got:
                        seen.add(e)
                    else:
                        lost.add(e)
            if seen and lost:
                obs.append((frozenset(t["seen"]), t, seen, lost))
        if len(obs) < 2:
            return
        groups = {}
        for g, t, seen, lost in obs:
            groups.setdefault(g, []).append((t, seen, lost))
        ownerof = {}
        for k, rows in comm.items():
            for _end, e, w in rows:
                ownerof[e] = w
        for g, members in groups.items():
            members = members[:70]
            n = len(members)
            for i in range(n):
                t1, seen1, lost1 = members[i]
                for j in range(i + 1, n):
                    t2, seen2, lost2 = members[j]
                    a = seen1 & lost2
                    if not a:
                        continue
                    b = seen2 & lost1
                    if not b:
                        continue
                    ws = set()
                    for e in a:
                        ws.add(id(ownerof.get(e)))
                    for e in b:
                        ws.add(id(ownerof.get(e)))
                    if len(ws) >= 2:
                        self.fired["F"] += 1
                        return

    # --- K: two writers with disjoint write sets, blind to each other -------

    @staticmethod
    def _blind(t1, t2):
        """t1 read a key t2 wrote and saw none of t2's elements there."""
        for k, es in t2["writes"].items():
            got = t1["seen"].get(k)
            if got is None:
                continue
            hit = False
            for e in es:
                if e in got:
                    hit = True
                    break
            if not hit:
                return True
        return False

    @staticmethod
    def _disjoint(t1, t2):
        for k in t1["writes"]:
            if k in t2["writes"]:
                return False
        return True

    def _detect_write_skew(self, txs, key_touch):
        seenpair = set()
        for k, group in key_touch.items():
            group = group[:60]
            n = len(group)
            for i in range(n):
                t1 = group[i]
                if not t1["ok"] or not t1["writes"]:
                    continue
                for j in range(i + 1, n):
                    t2 = group[j]
                    if not t2["ok"] or not t2["writes"]:
                        continue
                    if t1["session"] == t2["session"]:
                        continue
                    tag = (id(t1), id(t2))
                    if tag in seenpair:
                        continue
                    seenpair.add(tag)
                    if not self._disjoint(t1, t2):
                        continue
                    if not _overlap(t1, t2):
                        continue
                    if self._blind(t1, t2) and self._blind(t2, t1):
                        self.fired["K"] += 1
                        return

    # --- T: a read-only transaction missing a write that finished before it -

    def _detect_stale(self, txs, comm):
        # Strict serializability only orders a write before a read when the write
        # committed before the reading transaction *began*; an overlapping write
        # may legitimately be ordered after it.  So the real-time test uses the
        # reader's start clock, never the clock of the individual read.
        for t in txs:
            if not t["ok"] or t["writes"] or not _num(t["start"]):
                continue
            begin = t["start"]
            for k, s, _clk in t["reads"]:
                rows = comm.get(k)
                if not rows:
                    continue
                for _end, e, w in rows:
                    if _end >= begin:
                        break
                    if w is t:
                        continue
                    if e not in s:
                        self.fired["T"] += 1
                        return

    # --- how many genuine races of each shape the budget actually bought ----

    def _count_opportunities(self, txs, comm):
        weak = [t for t in txs if t["weak"]][:200]
        if weak:
            wr = [t for t in weak if t["writes"]][:120]
            n = len(wr)
            readers_ok = [t for t in txs if t["ok"] and t["seen"]]
            for i in range(n):
                t1 = wr[i]
                for j in range(i + 1, n):
                    t2 = wr[j]
                    if t1["session"] == t2["session"]:
                        continue
                    if not _overlap(t1, t2):
                        continue
                    # K: mutually visible shape with disjoint write sets
                    if t1["ok"] and t2["ok"] and self._disjoint(t1, t2):
                        r12 = any(k in t1["seen"] for k in t2["writes"])
                        r21 = any(k in t2["seen"] for k in t1["writes"])
                        if r12 and r21:
                            self.opp["K"] += 1
                        # F: two unrelated writes with two later observers
                        cnt = 0
                        for o in readers_ok:
                            if o is t1 or o is t2:
                                continue
                            if any(k in o["seen"] for k in t1["writes"]) and \
                               any(k in o["seen"] for k in t2["writes"]):
                                cnt += 1
                                if cnt >= 2:
                                    break
                        if cnt >= 2:
                            self.opp["F"] += 1
            # S and D need a writer and a separate reader of its keys
            for w in weak:
                if len(w["writes"]) < 2:
                    continue
                for r in weak:
                    if r is w or not r["ok"]:
                        continue
                    if not _overlap(w, r):
                        continue
                    shared = sum(1 for k in w["writes"] if k in r["seen"])
                    if shared >= 2 and w["ok"]:
                        self.opp["S"] += 1
                    if shared >= 1 and not w["ok"]:
                        self.opp["D"] += 1
        # T is linear in the weak rate: a weak read-only transaction with a
        # write that committed before it in real time is already an exposure
        for t in txs:
            if not t["ok"] or t["writes"] or not t["weak"]:
                continue
            if not _num(t["start"]):
                continue
            got = False
            for k, _s, _clk in t["reads"]:
                rows = comm.get(k)
                if rows and rows[0][0] < t["start"]:
                    got = True
                    break
            if got:
                self.opp["T"] += 1

    # -------------------------------------------------------------- decision

    def candidate(self):
        hit = [CLASS_LEVEL[c] for c in CLASS_LEVEL if self.fired[c] > 0]
        return min(hit) if hit else 5

    def target_shape(self, cand):
        if cand >= 5:
            # the top rung has to rule out two things: staleness (serializable)
            # and write skew (snapshot isolation), because a fresh single-copy
            # store below serializable need not show staleness at all
            rt = self.opp["T"] / float(THRESH["T"])
            rk = self.opp["K"] / float(THRESH["K"])
            return "T" if rt <= rk else "K"
        cls = RULE_OUT.get(cand, "K")
        if cls == "K":
            return "K"
        if cls == "F":
            return "F"
        if cls == "T":
            return "T"
        return "S"

    def go(self):
        missing = [n for n in CANON if n not in self.levels]
        if missing:
            return {"abstain": True, "confidence": 0.0}
        for shape in SHAPES:
            if self.left() <= 0 or self.broken:
                break
            self.do_batch(shape)
        guard = 0
        while not self.broken and guard < 500:
            guard += 1
            cand = self.candidate()
            if cand == 0:
                break
            if not self.do_batch(self.target_shape(cand)):
                break
        return self.decide()

    def decide(self):
        cand = self.candidate()
        if cand == 0:
            return {"level": CANON[0], "confidence": 0.9}
        needs = ["T", "K"] if cand == 5 else [RULE_OUT[cand]]
        ratios = []
        for c in needs:
            th = THRESH[c]
            ratios.append(self.opp[c] / float(th) if th > 0 else 0.0)
        r = min(ratios) if ratios else 0.0
        if r < 1.0:
            return {"abstain": True, "confidence": round(max(0.05, min(0.45, 0.45 * r)), 3)}
        conf = 0.6 + 0.1 * min(3.0, r - 1.0)
        return {"level": CANON[cand], "confidence": round(min(0.95, conf), 3)}


def audit(problem, run):
    """Name the store's isolation level, or decline when the races never came."""
    try:
        if not isinstance(problem, dict):
            return {"abstain": True, "confidence": 0.0}
        out = _Auditor(problem, run).go()
        if not isinstance(out, dict):
            return {"abstain": True, "confidence": 0.0}
        return out
    except Exception:
        return {"abstain": True, "confidence": 0.0}
