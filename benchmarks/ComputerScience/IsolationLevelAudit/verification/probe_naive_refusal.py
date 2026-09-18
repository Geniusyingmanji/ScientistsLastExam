"""Shortcut probe: it refuses, but on the wrong question.

Same design and same detector as the reference. It declines whenever it saw no anomaly at all,
which throws away every store that really is strictly serializable, and it answers whenever it saw
anything, even a class that belongs to a level it never had the power to look below.
"""
from __future__ import annotations

from itertools import combinations

LEVELS = ["read_uncommitted", "read_committed", "parallel_snapshot", "snapshot_isolation",
          "serializable", "strict_serializable"]
PIN = {"dirty_write": "read_uncommitted", "aborted_read": "read_uncommitted",
       "intermediate_read": "read_uncommitted", "lost_update": "read_committed",
       "read_skew": "read_committed", "long_fork": "parallel_snapshot",
       "write_skew": "snapshot_isolation", "stale_read": "serializable"}
LADDER = ["dirty_write", "aborted_read", "intermediate_read", "lost_update", "read_skew",
          "long_fork", "write_skew", "stale_read"]
CYCLE_MAX = 4

def level_of(worst_class):
    return PIN[worst_class] if worst_class else "strict_serializable"


# ---- reading the history -----------------------------------------------------------------------
def parse(transactions):
    P = {"txns": {t["tid"]: t for t in transactions}, "reads": [], "writer": {},
         "aborted": set(), "own": {}}
    for t in transactions:
        for kind, k, v in t["ops"]:
            if kind == "a":
                P["writer"][v] = t["tid"]
                P["own"].setdefault((t["tid"], k), []).append(v)
                if t["status"] != "committed":
                    P["aborted"].add(v)
            elif t["status"] == "committed":
                # only a committed transaction's observations bind the store: what a transaction
                # saw on its way to rolling back is not an isolation violation
                P["reads"].append({"tid": t["tid"], "key": k, "prefix": list(v)})
    return P


def observed_order(P):
    seq = {}
    for r in P["reads"]:
        if len(r["prefix"]) > len(seq.get(r["key"], [])):
            seq[r["key"]] = [e for e in r["prefix"] if e not in P["aborted"]]
    return seq


def index(P, order):
    pos = {k: {e: i for i, e in enumerate(v)} for k, v in order.items()}
    for r in P["reads"]:
        last = r["prefix"][-1] if r["prefix"] else None
        if last is None:
            r["idx"] = 0
        elif last in pos.get(r["key"], {}):
            r["idx"] = pos[r["key"]][last] + 1
        else:
            r["idx"] = None                     # saw an element this order does not place
    return pos


def graph(P, order):
    E = {}

    def add(u, v, kind):
        if u is not None and v is not None and u != v:
            E.setdefault((u, v), set()).add(kind)

    for k, v in order.items():
        for i in range(len(v) - 1):
            for j in range(i + 1, len(v)):
                add(P["writer"].get(v[i]), P["writer"].get(v[j]), "ww")
    for r in P["reads"]:
        if r["prefix"]:
            add(P["writer"].get(r["prefix"][-1]), r["tid"], "wr")
        if r["idx"] is not None:
            for e in order.get(r["key"], [])[r["idx"]:]:
                add(r["tid"], P["writer"].get(e), "rw")
    return E


def find_cycle(E, allow, rw_min, rw_max):
    adj = {}
    for (u, v), kinds in E.items():
        if kinds & allow:
            adj.setdefault(u, []).append((v, kinds & allow))
    for start in sorted(adj):
        stack = [(start, [start], [])]
        while stack:
            node, path, kinds = stack.pop()
            for nxt, kk in adj.get(node, ()):
                if nxt == start and len(path) >= 2:
                    ks = kinds + [kk]
                    lo = sum(1 for k in ks if k == {"rw"})
                    hi = sum(1 for k in ks if "rw" in k)
                    if any(rw_min <= c <= rw_max for c in range(lo, hi + 1)):
                        return sorted(path)
                elif nxt not in path and len(path) < CYCLE_MAX:
                    stack.append((nxt, path + [nxt], kinds + [kk]))
    return None


def analyze(transactions):
    """Every anomaly class this history witnesses, as {class: witness}."""
    P = parse(transactions)
    order = observed_order(P)
    pos = index(P, order)
    E = graph(P, order)
    txns, reads = P["txns"], P["reads"]
    ALL = {"ww", "wr", "rw"}
    found = {}

    c = find_cycle(E, {"ww"}, 0, 0)
    if c:
        found["dirty_write"] = c

    for r in reads:
        if r["prefix"] and r["prefix"][-1] in P["aborted"]:
            found.setdefault("aborted_read", sorted({r["tid"], P["writer"][r["prefix"][-1]]}))

    for r in reads:
        if not r["prefix"]:
            continue
        e = r["prefix"][-1]
        w = P["writer"].get(e)
        own = P["own"].get((w, r["key"]), [])
        if w is not None and w != r["tid"] and e in own and e != own[-1]:
            found.setdefault("intermediate_read", sorted({r["tid"], w}))

    byk = {}
    for r in reads:
        if r["idx"] is None:
            continue
        later = [e for e in P["own"].get((r["tid"], r["key"]), [])
                 if pos.get(r["key"], {}).get(e, -1) >= r["idx"]]
        if later:
            byk.setdefault((r["key"], r["idx"]), set()).add(r["tid"])
    for (k, _), tids in byk.items():
        if len(tids) >= 2:
            found.setdefault("lost_update", sorted(tids)[:2])
            break

    c = find_cycle(E, ALL, 1, 1)
    if c:
        found["read_skew"] = c

    saw, missed = {}, {}
    for r in reads:
        saw.setdefault(r["tid"], set()).update(r["prefix"])
        if r["idx"] is not None:
            missed.setdefault(r["tid"], set()).update(order.get(r["key"], [])[r["idx"]:])
    for a, b in combinations(sorted(saw), 2):
        if (saw[a] & missed.get(b, set())) and (saw.get(b, set()) & missed.get(a, set())):
            found.setdefault("long_fork", [a, b])
            break

    c = find_cycle(E, ALL, 2, CYCLE_MAX)
    if c:
        found["write_skew"] = c

    for r in reads:
        if r["idx"] is None:
            continue
        for e in order.get(r["key"], [])[r["idx"]:]:
            w = P["writer"].get(e)
            if w is not None and txns[w]["status"] == "committed" and \
                    txns[w]["end"] < txns[r["tid"]]["start"]:
                found.setdefault("stale_read", sorted({r["tid"], w}))
                break
        if "stale_read" in found:
            break
    return found


# ---- the patterns ------------------------------------------------------------------------------
def _alternating(a, b):
    """A transaction on the lock path is never interrupted, so operations that interleave prove
    both transactions took the weak path."""
    return bool(a["at"]) and bool(b["at"]) and \
        any(a["at"][0] < x < a["at"][-1] for x in b["at"]) and \
        any(b["at"][0] < x < b["at"][-1] for x in a["at"])


def _any_alt(group, other):
    return any(_alternating(x, y) for x in group for y in other if x["tid"] != y["tid"])


def _by(txns, *sessions):
    """Transactions come back in commit order, so pick them out by the session that ran them."""
    return [t for t in txns if t["session"] in sessions]


def _watch(run, a, b):
    """Right after the writes, both sessions read both keys, then a third session places them.

    The readers sit in the writers' own sessions: a session always has its own write, so if the
    other one has not replicated there yet the two readers hold contradictory views, which is the
    only way a fork shows itself. The same read-only transactions are the chance for a store that
    answers from a lagging replica to come back stale."""
    r = run([[[["r", a], ["r", b]]], [[["r", b], ["r", a]]]])["transactions"]
    place = run([[], [], [[["r", a], ["r", b]]]])["transactions"]
    return r + place, _any_alt(r, r)


def p_conflict(run, a, b):
    """Two writers over the same pair of keys, in opposite orders."""
    t = run([[[["r", a], ["r", b], ["a", a], ["a", b]]],
             [[["r", b], ["r", a], ["a", b], ["a", a]]]])["transactions"]
    rest, rr = _watch(run, a, b)
    ww = _any_alt(t, t)
    return t + rest, {"read_uncommitted": ww, "read_committed": ww, "serializable": rr}


def p_disjoint(run, a, b):
    """Each writer reads the key the other one writes, which is the shape of write skew."""
    t = run([[[["r", a], ["a", b]]], [[["r", b], ["a", a]]]])["transactions"]
    rest, rr = _watch(run, a, b)
    ww = _any_alt(t, t)
    return t + rest, {"snapshot_isolation": ww, "serializable": rr}


def p_fork(run, a, b):
    """Two writers that read nothing, so neither is in the other's causal past and a replica is
    free to apply them in either order: the only way two sessions can end up disagreeing."""
    t = run([[[["a", a]]], [[["a", b]]]])["transactions"]
    rest, rr = _watch(run, a, b)
    return t + rest, {"parallel_snapshot": rr, "serializable": rr}


def p_repeat(run, a, b):
    """One writer appends twice to the same key: does the store publish what is in between?"""
    t = run([[[["a", a], ["a", a]]],
             [[["r", a], ["r", a]]],
             [[["r", a], ["r", a]]]])["transactions"]
    t2 = run([[], [], [], [[["r", a]]]])["transactions"]
    ww = _any_alt(_by(t, 0), _by(t, 1, 2))
    return t + t2, {"read_uncommitted": ww}


PATTERNS = [("conflict", p_conflict, 14), ("disjoint", p_disjoint, 10), ("fork", p_fork, 8),
            ("repeat", p_repeat, 7)]

def _seen(hits):
    return {c: n for c, n in hits.items() if n}



def _sweep(problem, run):
    """Cycle the four patterns over the whole budget and count what fires."""
    budget = problem["budget"]
    spent, key, rounds = 0, 0, 0
    hits = {c: 0 for c in LADDER}
    i = 0
    while spent + 14 <= budget:
        _name, fn, cost = PATTERNS[i % len(PATTERNS)]
        txns, _gave = fn(run, key, key + 1)
        key += 2
        spent += cost
        rounds += 1
        i += 1
        for c in analyze(txns):
            hits[c] += 1
        if level_of(next((c for c in LADDER if hits[c]), None)) == "read_uncommitted":
            break                                    # nothing can be worse, so stop paying
    return next((c for c in LADDER if hits[c]), None), rounds, _seen(hits)

def audit(problem, run):
    worst, _rounds, hits = _sweep(problem, run)
    if worst is None:
        return {"abstain": True, "confidence": 0.0, "evidence": {"hits": hits}}
    return {"level": level_of(worst), "confidence": 0.6, "evidence": {"hits": hits}}
