"""IsolationLevelAudit solver.

Strategy
--------
The six levels form a ladder, and each adjacent pair is separated by one anomaly class:

    c=0 dirty write / dirty read      allowed only by read_uncommitted
    c=1 lost update / fractured read  allowed up to read_committed
    c=2 long fork                     allowed up to parallel_snapshot
    c=3 write skew                    allowed up to snapshot_isolation
    c=4 stale (non-real-time) read    allowed up to serializable

A level j permits exactly the classes c >= j.  So the true level is the smallest class index
that ever fires (5 if none does), and -- this is the useful part -- observing *no* firing of
class i-1 while having had many genuine chances at it rules out every level <= i-1 at once.

So the audit walks the ladder down: probe the class just below the current hypothesis; if it
fires, the hypothesis drops a rung and the next shape is used.  When it stops dropping, the
whole remaining budget goes into that one critical shape, which is exactly where the power is
needed.  A "chance" is only counted when two transactions provably took the weak path: a
lock-path transaction is never interrupted and the lock is never granted while anything is in
flight, so interleaved operation clocks prove both partners were weak.  If the critical class
never accumulates enough such chances, we decline (0) instead of guessing (-1).
"""
from __future__ import annotations

import bisect

_LEVELS = ("read_uncommitted", "read_committed", "parallel_snapshot",
           "snapshot_isolation", "serializable", "strict_serializable")

# How many proven races a class must go through in silence before we believe it cannot happen.
_THRESH = (18, 18, 12, 20, 35)


def audit(problem, run):
    """Name the isolation level of the black-box store, or decline."""
    try:
        return _audit(problem, run)
    except Exception:
        return {"abstain": True, "confidence": 0.0}


# --------------------------------------------------------------------------- state


class _St(object):
    def __init__(self, budget, ns, mt, mb):
        self.budget = budget
        self.spent = 0
        self.ns = ns
        self.mt = mt
        self.mb = mb
        self.key = 1
        self.hits = [0, 0, 0, 0, 0]
        self.opp = [0, 0, 0, 0, 0]
        self.dirty_reads = 0
        self.appends = {}          # key -> [(commit clock, element), ...] committed only
        self.aborted = {}          # element -> (start, end) of the transaction that aborted
        self.elem_owner = {}       # element -> transaction id that appended it
        self.committed_elems = set()
        self.dead = False          # run() misbehaved; stop spending

    def next_key(self):
        self.key += 1
        return self.key


def _iget(problem, name, default):
    try:
        v = problem[name]
        v = int(v)
        return v if v > 0 else default
    except Exception:
        return default


def _fired(st):
    return [st.hits[0] >= 1 or st.dirty_reads >= 2,
            st.hits[1] >= 1,
            st.hits[2] >= 1,
            st.hits[3] >= 1,
            st.hits[4] >= 2]


def _hypothesis(st):
    f = _fired(st)
    for c in range(5):
        if f[c]:
            return c
    return 5


# --------------------------------------------------------------------------- history parsing


def _parse(txns):
    recs = []
    for t in txns:
        if not isinstance(t, dict):
            continue
        ops = t.get("ops") or []
        at = t.get("at") or []
        if not isinstance(ops, (list, tuple)) or not isinstance(at, (list, tuple)):
            continue
        n = min(len(ops), len(at))
        if n <= 0:
            continue
        rseq = []
        wseq = []
        reads = {}
        writes = {}
        clocks = []
        for i in range(n):
            o = ops[i]
            c = at[i]
            if not isinstance(c, (int, float)):
                continue
            if not isinstance(o, (list, tuple)) or len(o) < 2:
                continue
            clocks.append(c)
            kind = o[0]
            k = o[1]
            if kind == "r":
                vals = o[2] if len(o) > 2 else []
                try:
                    seq = list(vals)
                except Exception:
                    seq = []
                rseq.append((k, seq, c))
                s = reads.get(k)
                if s is None:
                    s = set()
                    reads[k] = s
                s.update(seq)
            elif kind == "a":
                e = o[2] if len(o) > 2 else None
                wseq.append((k, e))
                writes.setdefault(k, []).append(e)
        if not clocks:
            continue
        lo = min(clocks)
        hi = max(clocks)
        start = t.get("start")
        end = t.get("end")
        if not isinstance(start, (int, float)):
            start = lo
        if not isinstance(end, (int, float)):
            end = hi
        recs.append({"tid": t.get("tid"),
                     "committed": t.get("status") == "committed",
                     "start": start, "end": end, "lo": lo, "hi": hi,
                     "clocks": clocks, "rseq": rseq, "wseq": wseq,
                     "reads": reads, "writes": writes, "weak": False})
    return recs


def _mark_weak(recs):
    """A transaction is provably on the weak path if a foreign operation falls inside its own
    span (it was interrupted, so it did not hold the global lock) or if one of its operations
    falls inside another transaction's span (the lock is not granted while anything is in
    flight, so it cannot have been holding it either)."""
    events = []
    for idx, r in enumerate(recs):
        for c in r["clocks"]:
            events.append((c, idx))
    events.sort()
    cl = [e[0] for e in events]
    ow = [e[1] for e in events]
    for idx, r in enumerate(recs):
        a = bisect.bisect_right(cl, r["lo"])
        b = bisect.bisect_left(cl, r["hi"])
        hit = False
        for j in range(a, b):
            o = ow[j]
            if o != idx:
                hit = True
                recs[o]["weak"] = True
        if hit:
            r["weak"] = True


def _overlap(a, b):
    return not (a["hi"] < b["lo"] or b["hi"] < a["lo"])


def _interleaved(a, b):
    alo, ahi = a["lo"], a["hi"]
    for c in b["clocks"]:
        if alo < c < ahi:
            return True
    blo, bhi = b["lo"], b["hi"]
    for c in a["clocks"]:
        if blo < c < bhi:
            return True
    return False


# --------------------------------------------------------------------------- detectors


def _analyze(st, txns):
    recs = _parse(txns)
    if not recs:
        return
    _mark_weak(recs)

    # version order at a key is the longest list anybody saw there
    order = {}
    for r in recs:
        for (k, seq, _c) in r["rseq"]:
            cur = order.get(k)
            if cur is None or len(seq) > len(cur):
                order[k] = seq
    pos = {}
    for k, seq in order.items():
        d = {}
        for i, e in enumerate(seq):
            if e not in d:
                d[e] = i
        pos[k] = d

    for r in recs:
        tid = r["tid"]
        if r["committed"]:
            for (k, e) in r["wseq"]:
                st.appends.setdefault(k, []).append((r["end"], e))
                st.elem_owner[e] = tid
                st.committed_elems.add(e)
        else:
            for (k, e) in r["wseq"]:
                st.aborted[e] = (r["start"], r["end"])
                st.elem_owner[e] = tid

    _c4_stale_read(st, recs)
    _c0_dirty(st, recs, pos)
    _c1_lost_update(st, recs)
    _c2_long_fork(st, recs)
    _c3_write_skew(st, recs)


def _c4_stale_read(st, recs):
    """Strict serializability orders a transaction after everything that committed before it
    began.  A committed read that misses such an element is a real-time violation."""
    for r in recs:
        if not r["committed"]:
            continue
        start = r["start"]
        eligible = False
        stale = False
        for (k, seq, _c) in r["rseq"]:
            lst = st.appends.get(k)
            if not lst:
                continue
            seen = set(seq)
            for (endc, e) in lst:
                if endc < start:
                    eligible = True
                    if e not in seen:
                        stale = True
                        break
            if stale:
                break
        if eligible and r["weak"]:
            st.opp[4] += 1
        if stale:
            st.hits[4] += 1


def _c0_dirty(st, recs, pos):
    """Dirty write: two committed transactions touching the same two keys in opposite version
    orders (a ww cycle).  Dirty read: a committed read of an element whose writer was still in
    flight and then aborted."""
    n = len(recs)
    for i in range(n):
        a = recs[i]
        if len(a["wseq"]) != 2:
            continue
        (ka, ea), (kb, eb) = a["wseq"]
        if ka == kb:
            continue
        pxa = pos.get(ka)
        pxb = pos.get(kb)
        for j in range(i + 1, n):
            b = recs[j]
            if len(b["wseq"]) != 2:
                continue
            (kc, ec), (kd, ed) = b["wseq"]
            if kc == kd or kc != kb or kd != ka:
                continue
            # b writes the same two keys in the opposite order: the designed shape
            if _interleaved(a, b):
                st.opp[0] += 1
            if not (a["committed"] and b["committed"]):
                continue
            if not pxa or not pxb:
                continue
            # ed is b's element at ka, ec is b's element at kb
            if ea in pxa and ed in pxa and eb in pxb and ec in pxb:
                if (pxa[ea] - pxa[ed]) * (pxb[eb] - pxb[ec]) < 0:
                    st.hits[0] += 1

    for r in recs:
        if not r["committed"]:
            continue
        for (k, seq, c) in r["rseq"]:
            bad = False
            for e in seq:
                w = st.aborted.get(e)
                if w is not None and w[0] < c < w[1]:
                    bad = True
                    break
            if bad:
                st.dirty_reads += 1
                break


def _c1_lost_update(st, recs):
    """Lost update: two committed concurrent transactions append to the same key and neither
    read saw the other's element.  Fractured read: a committed reader that saw part of one
    committed writer's appends and missed another part."""
    n = len(recs)
    for i in range(n):
        a = recs[i]
        if not a["writes"] or not a["reads"]:
            continue
        for j in range(i + 1, n):
            b = recs[j]
            if not b["writes"] or not b["reads"]:
                continue
            for k in a["writes"]:
                if k not in b["writes"] or k not in a["reads"] or k not in b["reads"]:
                    continue
                if _interleaved(a, b):
                    st.opp[1] += 1
                if a["committed"] and b["committed"] and _overlap(a, b):
                    ea = a["writes"][k][0]
                    eb = b["writes"][k][0]
                    if eb not in a["reads"][k] and ea not in b["reads"][k]:
                        st.hits[1] += 1
                break

    for r in recs:
        if not r["committed"] or not r["reads"]:
            continue
        hit = False
        for w in recs:
            if w is r or not w["committed"] or len(w["writes"]) < 2:
                continue
            saw = miss = False
            for k, es in w["writes"].items():
                seen = r["reads"].get(k)
                if seen is None:
                    continue
                if es[0] in seen:
                    saw = True
                else:
                    miss = True
            if saw and miss:
                hit = True
                break
        if hit:
            st.hits[1] += 1


def _c2_long_fork(st, recs):
    """Long fork: two read-only committed transactions with incomparable views of two keys
    written by two different transactions.  Snapshot isolation totally orders its snapshots, so
    it cannot produce one; parallel snapshot can."""
    groups = {}
    for i, r in enumerate(recs):
        if r["wseq"]:
            continue
        keys = tuple(sorted(r["reads"].keys()))
        if len(keys) != 2:
            continue
        groups.setdefault(keys, []).append(i)
    for keys, idxs in groups.items():
        if len(idxs) < 2:
            continue
        x, y = keys
        have = bool(st.appends.get(x)) and bool(st.appends.get(y))
        for ia in range(len(idxs)):
            r1 = recs[idxs[ia]]
            for ib in range(ia + 1, len(idxs)):
                r2 = recs[idxs[ib]]
                if have and r1["weak"] and r2["weak"]:
                    st.opp[2] += 1
                if not (r1["committed"] and r2["committed"]):
                    continue
                for (kx, ky) in ((x, y), (y, x)):
                    only1 = r1["reads"].get(kx, ()) and \
                        (set(r1["reads"][kx]) - set(r2["reads"].get(kx, ())))
                    only2 = r2["reads"].get(ky, ()) and \
                        (set(r2["reads"][ky]) - set(r1["reads"].get(ky, ())))
                    if not only1 or not only2:
                        continue
                    ex = _pick_committed(st, only1)
                    ey = _pick_committed(st, only2)
                    if ex is None or ey is None:
                        continue
                    if st.elem_owner.get(ex) == st.elem_owner.get(ey):
                        continue
                    st.hits[2] += 1
                    break


def _pick_committed(st, elems):
    for e in elems:
        if e in st.committed_elems:
            return e
    return None


def _c3_write_skew(st, recs):
    """Write skew: two committed concurrent transactions with disjoint single-key write sets,
    each reading the key the other wrote and each missing the other's element."""
    n = len(recs)
    for i in range(n):
        a = recs[i]
        if len(a["writes"]) != 1 or not a["reads"]:
            continue
        ka = next(iter(a["writes"]))
        for j in range(i + 1, n):
            b = recs[j]
            if len(b["writes"]) != 1 or not b["reads"]:
                continue
            kb = next(iter(b["writes"]))
            if ka == kb:
                continue
            if kb not in a["reads"] or ka not in b["reads"]:
                continue
            if _interleaved(a, b):
                st.opp[3] += 1
            if not (a["committed"] and b["committed"] and _overlap(a, b)):
                continue
            ea = a["writes"][ka][0]
            eb = b["writes"][kb][0]
            if eb not in a["reads"][kb] and ea not in b["reads"][ka]:
                st.hits[3] += 1
