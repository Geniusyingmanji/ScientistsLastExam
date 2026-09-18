"""IsolationLevelAudit: identify the isolation level a black-box store implements.

Strategy
--------
The six levels form a ladder.  For each level ``i`` there is exactly one anomaly class
``S(i)`` that the level permits and the level above forbids:

    0  read_uncommitted   S(0) = dirty write (ww cycle) / dirty read
    1  read_committed     S(1) = fractured read (atomic-visibility violation)
    2  parallel_snapshot  S(2) = long fork (two incomparable snapshots)
    3  snapshot_isolation S(3) = write skew (rw/rw cycle on disjoint write sets)
    4  serializable       S(4) = stale read (real-time order violation)
    5  strict_serializable                (nothing)

A store at level L exhibits exactly the classes ``S(i)`` for ``i >= L``.  Therefore

    L_upper = min { i : S(i) observed }        (5 when nothing was observed)

is an upper bound on the level, and it is *the* level as soon as ``S(L_upper - 1)`` has
been given enough genuine chances to fire and did not.  Because ``S(L_upper - 1)`` is
permitted at every level at or below ``L_upper - 1``, ruling it out rules out the whole
tail of the ladder at once.

Every detector below is a logically sound witness: it exhibits a cycle or a real-time
violation that the stronger level cannot produce, so a single occurrence is conclusive.
What is *not* conclusive is silence, so the solver counts opportunities: a pair of
transactions whose operation clocks interleave proves both took the store's weak path
(a lock-path transaction is never interrupted and the lock is never granted while
anything is in flight).  Only interleaved pairs of the right designed shape are counted.

Budget use: a short round-robin sweep locates ``L_upper`` cheaply, then the whole
remaining budget is poured into the single shape that separates ``L_upper`` from the
level below it.  If that shape fires, ``L_upper`` drops and the focus moves down one
rung; the cascade is monotone and terminates.  We name a level only when the decisive
shape reached its opportunity threshold, and decline otherwise.
"""
from __future__ import annotations

_LEVELS = ["read_uncommitted", "read_committed", "parallel_snapshot",
           "snapshot_isolation", "serializable", "strict_serializable"]

# Interleaved designed pairs required before silence on class i is treated as evidence.
_THRESH = (6, 6, 7, 6, 8)

_PHASE1 = (0, 1, 3, 2, 4)
_PHASE1_HINT = 240
_PHASE2_HINT = 320


def _h(x):
    """Hashable stand-in for a store element."""
    try:
        hash(x)
        return x
    except Exception:
        return repr(x)


def _num(x, d=0.0):
    try:
        return float(x)
    except Exception:
        return d


def _norm(raw):
    """Turn the engine's transaction records into validated dicts; drop malformed ones."""
    out = []
    if not isinstance(raw, list):
        return out
    for t in raw:
        if not isinstance(t, dict):
            continue
        ops = t.get("ops")
        at = t.get("at")
        if not isinstance(ops, (list, tuple)):
            continue
        if not isinstance(at, (list, tuple)) or len(at) != len(ops):
            continue
        clocks = []
        ok = True
        for c in at:
            if isinstance(c, bool) or not isinstance(c, (int, float)):
                ok = False
                break
            clocks.append(float(c))
        if not ok:
            continue
        reads = []
        writes = []
        for o, c in zip(ops, clocks):
            if not isinstance(o, (list, tuple)) or len(o) < 2:
                ok = False
                break
            kind = o[0]
            key = o[1]
            if kind == "r":
                vals = o[2] if len(o) > 2 else []
                if not isinstance(vals, (list, tuple)):
                    vals = []
                reads.append((key, list(vals), c))
            elif kind == "a":
                reads_e = o[2] if len(o) > 2 else None
                writes.append((key, reads_e, c))
            else:
                ok = False
                break
        if not ok:
            continue
        lo = min(clocks) if clocks else 0.0
        hi = max(clocks) if clocks else 0.0
        rec = {
            "tid": t.get("tid"),
            "session": t.get("session"),
            "start": _num(t.get("start"), lo),
            "end": _num(t.get("end"), hi),
            "committed": t.get("status") == "committed",
            "clocks": clocks,
            "lo": lo,
            "hi": hi,
            "reads": reads,
            "writes": writes,
        }
        out.append(rec)
    return out


def _inter(a, b):
    """True when an operation of one transaction fell strictly inside the other's span.

    A lock-path transaction runs with nothing falling inside it and cannot start while
    anything is in flight, so this proves both transactions took the weak path.
    """
    ca = a["clocks"]
    cb = b["clocks"]
    if not ca or not cb:
        return False
    if a["hi"] <= b["lo"] or b["hi"] <= a["lo"]:
        return False
    lo_a, hi_a = a["lo"], a["hi"]
    lo_b, hi_b = b["lo"], b["hi"]
    for c in cb:
        if lo_a < c < hi_a:
            return True
    for c in ca:
        if lo_b < c < hi_b:
            return True
    return False


def _inter_pairs(txs):
    """All index pairs whose operations interleave (sweep over start clocks)."""
    pairs = []
    n = len(txs)
    if n < 2:
        return pairs
    order = sorted(range(n), key=lambda i: txs[i]["lo"])
    for a in range(n):
        i = order[a]
        hi_i = txs[i]["hi"]
        seen = 0
        for b in range(a + 1, n):
            j = order[b]
            if txs[j]["lo"] >= hi_i:
                break
            seen += 1
            if seen > 48:
                break
            if _inter(txs[i], txs[j]):
                pairs.append((i, j))
    return pairs


class _Auditor:
    def __init__(self, problem, run):
        p = problem if isinstance(problem, dict) else {}
        lv = p.get("levels")
        if isinstance(lv, (list, tuple)) and len(lv) == 6:
            self.levels = [str(v) for v in lv]
        else:
            self.levels = list(_LEVELS)
        self.budget = int(max(0.0, _num(p.get("budget"), 9000.0)))
        self.S = max(1, min(4, int(_num(p.get("max_sessions"), 4.0))))
        self.mot = max(1, int(_num(p.get("max_ops_per_txn"), 8.0)))
        self.mob = max(1, int(_num(p.get("max_ops_per_batch"), 400.0)))
        self.run = run
        self.spent = 0
        self.dead = False
        self.anom = [0] * 5
        self.opps = [0] * 5
        self._key = 11

    # -- plumbing ---------------------------------------------------------

    def _nk(self):
        self._key += 1
        return self._key

    @property
    def rem(self):
        return self.budget - self.spent

    def _call(self, sessions):
        """Validate a batch locally, charge it, and run it.  Never raises."""
        if self.dead:
            return None
        try:
            if not isinstance(sessions, list) or len(sessions) > self.S:
                return None
            ops = 0
            for s in sessions:
                for t in s:
                    n = len(t)
                    if n < 1 or n > self.mot:
                        return None
                    ops += n
            if ops < 1 or ops > self.mob or ops > self.rem:
                return None
        except Exception:
            return None
        self.spent += ops
        try:
            res = self.run(sessions)
            raw = res["transactions"]
        except Exception:
            self.dead = True
            return None
        return _norm(raw)

    # -- scans that apply to every batch ----------------------------------

    def _scan_common(self, txs):
        """Dirty reads, real-time violations and staleness opportunities, for free."""
        if not txs:
            return []
        # Dirty read: a transaction saw an element some *other* transaction appended and
        # then failed to commit.  Reading one's own uncommitted write is not an anomaly.
        aborted = {}
        for n, t in enumerate(txs):
            if not t["committed"]:
                for (_k, e, _c) in t["writes"]:
                    aborted[_h(e)] = n
        if aborted:
            for n, t in enumerate(txs):
                hit = False
                for (_k, vals, _c) in t["reads"]:
                    for v in vals:
                        if aborted.get(_h(v), n) != n:
                            hit = True
                            break
                    if hit:
                        break
                if hit:
                    self.anom[0] += 1

        comm = {}
        for t in txs:
            if t["committed"]:
                for (k, e, _c) in t["writes"]:
                    comm.setdefault(k, []).append((_h(e), t["end"]))
        if comm:
            for t in txs:
                if not t["committed"]:
                    continue
                st = t["start"]
                flagged = False
                for (k, vals, _c) in t["reads"]:
                    lst = comm.get(k)
                    if not lst:
                        continue
                    seen = set(_h(v) for v in vals)
                    for (e, te) in lst:
                        if te < st and e not in seen:
                            flagged = True
                            break
                    if flagged:
                        break
                if flagged:
                    self.anom[4] += 1

        pairs = _inter_pairs(txs)
        if comm:
            weak = set()
            for (i, j) in pairs:
                weak.add(i)
                weak.add(j)
            earliest = {}
            for k, lst in comm.items():
                earliest[k] = min(te for (_e, te) in lst)
            for i in weak:
                t = txs[i]
                if not t["committed"] or t["writes"] or not t["reads"]:
                    continue
                for (k, _vals, _c) in t["reads"]:
                    e0 = earliest.get(k)
                    if e0 is not None and t["start"] > e0:
                        self.opps[4] += 1
                        break
        return pairs

    def _count_opps(self, cls, txs, pairs, roles):
        for (i, j) in pairs:
            ri = roles[i]
            rj = roles[j]
            if ri is None or rj is None or ri == rj:
                continue
            if txs[i]["committed"] and txs[j]["committed"]:
                self.opps[cls] += 1

    # -- shape 0: dirty write --------------------------------------------

    def _probe_dw(self, hint):
        S = self.S
        slots = min(self.mob, hint, self.rem - 4) // (2 * S)
        if slots < 1:
            return
        a = self._nk()
        b = self._nk()
        sessions = []
        for s in range(S):
            if s % 2 == 0:
                sessions.append([[["a", a], ["a", b]] for _ in range(slots)])
            else:
                sessions.append([[["a", b], ["a", a]] for _ in range(slots)])
        txs = self._call(sessions)
        if txs is None:
            return
        pairs = self._scan_common(txs)

        roles = []
        for t in txs:
            w = t["writes"]
            if len(w) == 2 and not t["reads"]:
                if w[0][0] == a and w[1][0] == b:
                    roles.append(0)
                elif w[0][0] == b and w[1][0] == a:
                    roles.append(1)
                else:
                    roles.append(None)
            else:
                roles.append(None)
        self._count_opps(0, txs, pairs, roles)

        rd = self._call([[[["r", a], ["r", b], ["r", a], ["r", b]]]])
        if rd:
            self._scan_common(rd)
        pos_a = {}
        pos_b = {}
        for t in (rd or []):
            for (k, vals, _c) in t["reads"]:
                if k == a and len(vals) >= len(pos_a):
                    pos_a = dict((_h(v), i) for i, v in enumerate(vals))
                elif k == b and len(vals) >= len(pos_b):
                    pos_b = dict((_h(v), i) for i, v in enumerate(vals))
        if not pos_a or not pos_b:
            return
        A = []
        B = []
        for t, r in zip(txs, roles):
            if r is None or not t["committed"]:
                continue
            if r == 0:
                ea, eb = _h(t["writes"][0][1]), _h(t["writes"][1][1])
            else:
                ea, eb = _h(t["writes"][1][1]), _h(t["writes"][0][1])
            ia = pos_a.get(ea)
            ib = pos_b.get(eb)
            if ia is None or ib is None:
                continue
            (A if r == 0 else B).append((ia, ib))
        for (ia, ib) in A:
            for (ja, jb) in B:
                if (ia < ja) != (ib < jb):
                    self.anom[0] += 1

    # -- shape 1: fractured read ------------------------------------------

    def _probe_fr(self, hint):
        S = self.S
        slots = min(self.mob, hint, self.rem) // (2 * S)
        if slots < 1:
            return
        a = self._nk()
        b = self._nk()
        sessions = []
        for s in range(S):
            if s % 2 == 0:
                sessions.append([[["a", a], ["a", b]] for _ in range(slots)])
            else:
                sessions.append([[["r", a], ["r", b]] for _ in range(slots)])
        txs = self._call(sessions)
        if txs is None:
            return
        pairs = self._scan_common(txs)

        roles = []
        for t in txs:
            w, r = t["writes"], t["reads"]
            if len(w) == 2 and not r and w[0][0] == a and w[1][0] == b:
                roles.append(0)
            elif len(r) == 2 and not w and r[0][0] == a and r[1][0] == b:
                roles.append(1)
            else:
                roles.append(None)
        self._count_opps(1, txs, pairs, roles)

        readers = []
        for t, r in zip(txs, roles):
            if r == 1 and t["committed"]:
                readers.append((set(_h(v) for v in t["reads"][0][1]),
                                set(_h(v) for v in t["reads"][1][1])))
        if not readers:
            return
        for t, r in zip(txs, roles):
            if r != 0 or not t["committed"]:
                continue
            wa = _h(t["writes"][0][1])
            wb = _h(t["writes"][1][1])
            for (La, Lb) in readers:
                # Atomic visibility means a reader sees both of a committed writer's
                # appends or neither; seeing exactly one fractures the write.
                if (wa in La) != (wb in Lb):
                    self.anom[1] += 1

    # -- shape 2: long fork -----------------------------------------------

    def _probe_lf(self, hint):
        S = self.S
        slots = min(self.mob, hint, self.rem) // (4 * S)
        if slots < 1:
            return
        x = self._nk()
        y = self._nk()
        sessions = []
        for s in range(S):
            K, O = (x, y) if s % 2 == 0 else (y, x)
            txns = []
            for _ in range(slots):
                txns.append([["a", K], ["r", K]])
                txns.append([["r", O], ["r", K]])
            sessions.append(txns)
        txs = self._call(sessions)
        if txs is None:
            return
        pairs = self._scan_common(txs)

        roles = []
        for t in txs:
            w, r = t["writes"], t["reads"]
            if len(w) == 1 and len(r) == 1 and w[0][0] == r[0][0]:
                if w[0][0] == x:
                    roles.append(0)
                elif w[0][0] == y:
                    roles.append(1)
                else:
                    roles.append(None)
            else:
                roles.append(None)
        self._count_opps(2, txs, pairs, roles)

        own = {}
        for t in txs:
            if not t["committed"]:
                continue
            for (k, e, _c) in t["writes"]:
                own.setdefault((t["session"], k), []).append((_h(e), t["end"]))
        for lst in own.values():
            lst.sort(key=lambda p: p[1])

        rx = []
        ry = []
        for t in txs:
            if not t["committed"] or t["writes"] or len(t["reads"]) != 2:
                continue
            ko = t["reads"][0][0]
            kk = t["reads"][1][0]
            if kk == x and ko == y:
                bucket, K = rx, x
            elif kk == y and ko == x:
                bucket, K = ry, y
            else:
                continue
            Lk = set(_h(v) for v in t["reads"][1][1])
            Lo = set(_h(v) for v in t["reads"][0][1])
            held = [p for p in own.get((t["session"], K), ()) if p[0] in Lk][-3:]
            if not held:
                continue
            bucket.append((held, Lo, t["start"]))

        for (heldx, view_y, st_x) in rx:
            for (heldy, view_x, st_y) in ry:
                # The x-holder must be missing a y-write that had already committed
                # when it started, and symmetrically: two incomparable snapshots.
                fx = False
                for (e, te) in heldx:
                    if te < st_y and e not in view_x:
                        fx = True
                        break
                if not fx:
                    continue
                for (e, te) in heldy:
                    if te < st_x and e not in view_y:
                        self.anom[2] += 1
                        break

    # -- shape 3: write skew ----------------------------------------------

    def _probe_ws(self, hint):
        S = self.S
        slots = min(self.mob, hint, self.rem) // (2 * S)
        if slots < 1:
            return
        x = self._nk()
        y = self._nk()
        sessions = []
        for s in range(S):
            if s % 2 == 0:
                sessions.append([[["r", y], ["a", x]] for _ in range(slots)])
            else:
                sessions.append([[["r", x], ["a", y]] for _ in range(slots)])
        txs = self._call(sessions)
        if txs is None:
            return
        pairs = self._scan_common(txs)

        roles = []
        for t in txs:
            w, r = t["writes"], t["reads"]
            if len(w) == 1 and len(r) == 1:
                if r[0][0] == y and w[0][0] == x:
                    roles.append(0)
                elif r[0][0] == x and w[0][0] == y:
                    roles.append(1)
                else:
                    roles.append(None)
            else:
                roles.append(None)
        self._count_opps(3, txs, pairs, roles)

        A = []
        B = []
        for t, r in zip(txs, roles):
            if r is None or not t["committed"]:
                continue
            item = (_h(t["writes"][0][1]),
                    set(_h(v) for v in t["reads"][0][1]),
                    t["lo"], t["hi"])
            (A if r == 0 else B).append(item)
        for (ex, Ly, lo0, hi0) in A:
            for (ey, Lx, lo1, hi1) in B:
                if hi0 <= lo1 or hi1 <= lo0:
                    continue  # a genuine rw/rw cycle forces overlapping spans
                if ey not in Ly and ex not in Lx:
                    self.anom[3] += 1

    # -- shape 4: stale read ----------------------------------------------

    def _probe_stale(self, hint):
        S = self.S
        k = self._nk()
        w = self._call([[[["a", k], ["a", k]]]])
        if w is None:
            return
        marks = []
        for t in w:
            if t["committed"]:
                for (kk, e, _c) in t["writes"]:
                    if kk == k:
                        marks.append((_h(e), t["end"]))
        if not marks:
            return
        slots = min(self.mob, hint - 2, self.rem) // (2 * S)
        if slots < 1:
            return
        sessions = [[[["r", k], ["r", k]] for _ in range(slots)] for _ in range(S)]
        txs = self._call(sessions)
        if txs is None:
            return
        pairs = self._scan_common(txs)
        weak = set()
        for (i, j) in pairs:
            weak.add(i)
            weak.add(j)
        first = min(te for (_e, te) in marks)
        for i in weak:
            t = txs[i]
            if t["committed"] and not t["writes"] and t["start"] > first:
                self.opps[4] += 1
        for t in txs:
            if not t["committed"]:
                continue
            st = t["start"]
            flagged = False
            for (kk, vals, _c) in t["reads"]:
                if kk != k:
                    continue
                seen = set(_h(v) for v in vals)
                for (e, te) in marks:
                    if te < st and e not in seen:
                        flagged = True
                        break
                if flagged:
                    break
            if flagged:
                self.anom[4] += 1

    # -- driver -----------------------------------------------------------

    def _probe(self, shape, hint):
        try:
            if shape == 0:
                self._probe_dw(hint)
            elif shape == 1:
                self._probe_fr(hint)
            elif shape == 2:
                self._probe_lf(hint)
            elif shape == 3:
                self._probe_ws(hint)
            else:
                self._probe_stale(hint)
        except Exception:
            pass

    def _level(self):
        for i in range(5):
            if self.anom[i] >= 1:
                return i
        return 5

    def solve(self):
        if self.S < 2 or self.mot < 2 or self.budget < 64:
            return {"abstain": True, "confidence": 0.0}
        for shape in _PHASE1:
            if self.dead:
                break
            if self._level() == 0:
                break
            self._probe(shape, _PHASE1_HINT)
        guard = 0
        while not self.dead and guard < 400:
            guard += 1
            lvl = self._level()
            if lvl == 0:
                break
            before = self.spent
            self._probe(lvl - 1, _PHASE2_HINT)
            if self.spent <= before:
                break
        return self._answer()

    def _answer(self):
        lvl = self._level()
        if lvl == 0:
            return {"level": self.levels[0], "confidence": 0.9}
        need = lvl - 1
        got = self.opps[need]
        if got >= _THRESH[need]:
            conf = 0.55 + 0.035 * min(got, 12)
            return {"level": self.levels[lvl], "confidence": round(min(0.95, conf), 3)}
        conf = 0.10 + 0.05 * got
        return {"abstain": True, "confidence": round(min(0.5, max(0.0, conf)), 3)}


def audit(problem, run):
    try:
        out = _Auditor(problem, run).solve()
    except Exception:
        return {"abstain": True, "confidence": 0.0}
    if not isinstance(out, dict):
        return {"abstain": True, "confidence": 0.0}
    return out
