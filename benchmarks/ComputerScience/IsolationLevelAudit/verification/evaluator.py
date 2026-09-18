"""Hidden oracle for IsolationLevelAudit.

A black-box transactional store implements exactly one isolation level. The candidate may run
batches of concurrent transactions against it, under an operation budget, and must name the level
or decline. The level is a property of the world, fixed before the candidate runs, so the score is
exact and campaign independent.

The store's weak behaviour is a rare race. Most transactions take a global lock and run atomically,
so they read the authoritative state and no other operation falls inside theirs; with probability
`rate`, drawn per transaction and hidden, one takes the store's own concurrency control instead.
The lock is not granted while anything is in flight, so a transaction on the weak path is never
interrupted by a transaction on the lock path: an anomaly needs two weak transactions at once, and
its rate is quadratic in a number the candidate cannot change. The budget therefore buys
opportunities, not operations, and in some worlds it does not buy enough of them.

What makes it hard:

    design            an anomaly appears only under the contention that admits it. Write skew
                      needs two writers with disjoint write sets whose reads cross; a long fork
                      needs two writes with no causal relation and two readers in the writers' own
                      sessions; a dirty write needs two writers touching the same keys in opposite
                      orders. A probe that does not build the shape never sees the class, and the
                      level below the verdict stays alive
    analysis          the observed history is all the candidate gets: per-transaction operations,
                      status and per-operation clocks. The version order of a key has to be
                      recovered from the reads before any dependency edge can be drawn
    power             a round that happened to run two weak transactions at once and a round that
                      did not look the same in the anomaly count and different in the clocks. A
                      strict transaction holds the lock, so interleaved operations prove both
                      transactions took the weak path; nothing else does
    refusal           naming the level above the truth because the evidence for the truth never
                      fired costs a world. Where the opportunities are too few, declining is the
                      answer that is worth more than a guess
"""
from __future__ import annotations

import math
import random

LEVELS = ("read_uncommitted", "read_committed", "parallel_snapshot", "snapshot_isolation",
          "serializable", "strict_serializable")

# The strongest level that still permits each anomaly class. The worst class a history witnesses
# therefore names the level, and a weaker store may also show anything milder.
PIN = {
    "dirty_write": "read_uncommitted",
    "aborted_read": "read_uncommitted",
    "intermediate_read": "read_uncommitted",
    "lost_update": "read_committed",
    "read_skew": "read_committed",
    "long_fork": "parallel_snapshot",
    "write_skew": "snapshot_isolation",
    "stale_read": "serializable",
}

BUDGET = 9000
MIN_WEAK_RATE = 0.04
MAX_SESSIONS = 4
MAX_OPS = 8
MAX_BATCH_OPS = 400


def allowed(level):
    """The classes a store at this level may exhibit."""
    i = LEVELS.index(level)
    return {c for c, p in PIN.items() if LEVELS.index(p) >= i}


def level_of(worst_class):
    return PIN[worst_class] if worst_class else "strict_serializable"


# ---- the store ---------------------------------------------------------------------------------
class Store:
    """One key holds a list; an append adds a globally unique element and a read returns the list.

    `lag` is how far a read replica may sit behind at serializable, `delay` how late a replica may
    apply a commit at parallel snapshot, `skew` how often it is late at all, and `base_abort` the
    rate at which any transaction on either path aborts for reasons of its own, so that an abort
    says nothing about which path a transaction took.
    """

    def __init__(self, level, rate, seed, lag=4, delay=25, base_abort=0.04, skew=0.5):
        if level not in LEVELS:
            raise ValueError(level)
        self.level, self.rate, self.lag, self.delay = level, rate, lag, delay
        self.skew, self.base_abort = skew, base_abort
        self.rng = random.Random(seed)
        self.committed = {}          # key -> [elem], the version order
        self.ctime = {}              # elem -> commit clock
        self.deliver = {}            # (session, elem) -> clock it becomes visible to that session
        self.last_deliver = {}       # (session, key) -> delivery is FIFO per key, so views are prefixes
        self.deliver_txn = {}        # (session, tid) -> when that whole transaction landed there
        self.owner = {}              # elem -> the transaction that appended it
        self.clock = 0
        self.elem = 0
        self.tid = 0

    # ---------- views ----------
    def _fresh(self, k):
        return list(self.committed.get(k, ()))

    def _at(self, k, t):
        return [e for e in self.committed.get(k, ()) if self.ctime[e] <= t]

    def _session_view(self, s, k):
        return [e for e in self.committed.get(k, ())
                if self.deliver.get((s, e), self.ctime[e]) <= self.clock]

    def _put(self, k, e, tid):
        self.committed.setdefault(k, []).append(e)
        self.ctime[e] = self.clock
        self.owner[e] = tid

    def _install(self, t):
        for k, e in t["writes"]:
            if e not in self.ctime:                      # read_uncommitted installs as it writes
                self._put(k, e, t["tid"])
        if self.level != "parallel_snapshot":
            return
        keys = {k for k, _ in t["writes"]}
        for s in range(MAX_SESSIONS):                    # a transaction is delivered atomically,
            lagged = s != t["session"] and self.rng.random() < self.skew
            when = self.clock + (self.rng.randrange(1, self.delay + 1) if lagged else 0)
            when = max([when] + [self.last_deliver.get((s, k), 0) for k in keys]
                       # and never before anything it read: delivery respects causal order
                       + [self.deliver_txn.get((s, d), 0) for d in t["deps"]])
            for k, e in t["writes"]:
                self.deliver[(s, e)] = when
            for k in keys:
                self.last_deliver[(s, k)] = when
            self.deliver_txn[(s, t["tid"])] = when

    def _rollback(self, t):
        for k, e in t["writes"]:
            if e in self.ctime:
                self.committed[k] = [x for x in self.committed[k] if x != e]
                del self.ctime[e]

    # ---------- one transaction ----------
    def _begin(self, session, ops, weak):
        self.tid += 1
        self.clock += 1                                  # begin, commit and every operation get
        t = {"tid": self.tid, "session": session, "ops": list(ops), "i": 0, "done": [], "at": [],
             "writes": [], "reads": set(), "deps": set(), "weak": weak, "start": self.clock,
             "snap": None}                               # their own instant, so real time is total
        t["readonly"] = all(kind == "r" for kind, _ in ops)
        if not weak:
            return t
        if self.level == "serializable" and t["readonly"]:
            # a read-only transaction may be answered by a lagging replica: it is serialized before
            # the writes it missed, which is serializable but disagrees with real time
            t["snap"] = {k: self._at(k, self.clock - self.lag) for k in self.committed}
        elif self.level == "snapshot_isolation":
            t["snap"] = {k: self._fresh(k) for k in self.committed}
        elif self.level == "parallel_snapshot":
            t["snap"] = {k: self._session_view(session, k) for k in self.committed}
        return t

    def _read(self, t, k):
        own = [e for kk, e in t["writes"] if kk == k and e not in self.ctime]
        if t["snap"] is not None:
            return list(t["snap"].get(k, ())) + own
        return self._fresh(k) + own                      # the lock path, and the fresh weak paths

    def _unseen(self, t, k):
        """Did key k take a commit this transaction's snapshot does not contain?"""
        base = t["snap"].get(k, []) if t["snap"] is not None else self._at(k, t["start"])
        return len(self._fresh(k)) > len(base)

    def _commit(self, t):
        abort = self.rng.random() < self.base_abort
        lv = self.level
        if t["weak"]:
            if lv == "read_uncommitted":
                abort = abort or self.rng.random() < 0.3     # the dirty writer may roll back
            elif lv in ("parallel_snapshot", "snapshot_isolation"):
                abort = abort or any(self._unseen(t, k) for k, _ in t["writes"])
            elif lv in ("serializable", "strict_serializable") and t["snap"] is None:
                # optimistic concurrency control: interleaves freely, certifies both ways
                abort = abort or any(self._unseen(t, k) for k, _ in t["writes"]) \
                    or any(self._unseen(t, k) for k in t["reads"])
        self.clock += 1
        if abort:
            self._rollback(t)
        else:
            self._install(t)
        return "aborted" if abort else "committed"

    # ---------- the interleaving engine ----------
    def run(self, batch):
        state = [{"session": si, "queue": [list(t) for t in s], "cur": None, "pending": None}
                 for si, s in enumerate(batch)]
        out, lock = [], None

        def step(st):
            t = st["cur"]
            if t["i"] >= len(t["ops"]):
                status = self._commit(t)
                out.append({"tid": t["tid"], "session": t["session"], "start": t["start"],
                            "end": self.clock, "status": status, "ops": t["done"], "at": t["at"]})
                st["cur"] = None
                return "done"
            kind, k = t["ops"][t["i"]]
            self.clock += 1
            t["at"].append(self.clock)
            if kind == "r":
                t["reads"].add(k)
                seen = list(self._read(t, k))
                t["deps"].update(self.owner[e] for e in seen if e in self.owner)
                t["done"].append(["r", k, seen])
            else:
                self.elem += 1
                e = self.elem
                t["writes"].append((k, e))
                t["done"].append(["a", k, e])
                if self.level == "read_uncommitted" and t["weak"]:
                    self._put(k, e, t["tid"])            # installed before commit, so others see it
            t["i"] += 1
            return "step"

        while any(st["queue"] or st["cur"] for st in state):
            if lock is not None:
                st = state[lock]
                if step(st) == "done":
                    lock = None
                continue
            started = False
            for st in self.rng.sample(state, len(state)):   # the caller does not pick the schedule
                if st["cur"] is None:
                    if not st["queue"]:
                        continue
                    if st["pending"] is None:
                        st["pending"] = self.rng.random() < self.rate
                    if not st["pending"] and any(o["cur"] for o in state):
                        continue                     # the lock drains first: wait for those in flight
                    st["cur"] = self._begin(st["session"], st["queue"].pop(0), st["pending"])
                    st["pending"] = None
                    if not st["cur"]["weak"]:        # a strict transaction runs under the lock
                        lock = st["session"]
                        started = True
                        break
                step(st)
            if started:
                continue
        return out


class _Bench:
    """Budgeted access to one store."""

    def __init__(self, level, rate, seed, budget=BUDGET):
        self.store = Store(level, rate, seed)
        self.budget, self.used, self.calls, self.violated = budget, 0, 0, False

    def api(self):
        def run(batch):
            batch = [[[list(op) for op in t] for t in s] for s in batch]
            if not batch or len(batch) > MAX_SESSIONS:
                raise ValueError("a batch runs 1..%d sessions" % MAX_SESSIONS)
            cost = 0
            for s in batch:
                for t in s:
                    if not 1 <= len(t) <= MAX_OPS:
                        raise ValueError("a transaction runs 1..%d operations" % MAX_OPS)
                    for op in t:
                        if len(op) != 2 or op[0] not in ("r", "a") or not isinstance(op[1], int) \
                                or isinstance(op[1], bool) or op[1] < 0:
                            raise ValueError('an operation is ["r", key] or ["a", key],'
                                             ' key a non-negative integer')
                    cost += len(t)
            if cost == 0 or cost > MAX_BATCH_OPS:
                raise ValueError("a batch runs at most %d operations" % MAX_BATCH_OPS)
            if self.used + cost > self.budget:
                self.violated = True
                raise RuntimeError("operation budget exhausted")
            self.used += cost
            self.calls += 1
            return {"transactions": self.store.run(batch)}
        return run


# ---- the public problem ------------------------------------------------------------------------
PUBLIC_PROBLEM = {
    "store_model": "a store that implements exactly one of `levels`. Most transactions take a "
                   "global lock and run atomically against the authoritative state; with a hidden "
                   "probability at least min_weak_rate a transaction takes the store's own "
                   "concurrency control instead. The lock is not granted while any transaction is "
                   "in flight, so a transaction on the weak path is never interrupted by one on "
                   "the lock path. Every transaction on either path may also abort on its own at a "
                   "fixed rate.",
    "batch_model": "run(batch) takes a list of sessions, each a list of transactions, each a list "
                   "of operations. The engine chooses the interleaving; the caller chooses the "
                   "contention. Sessions run their transactions in order.",
    "answer_format": "{'level': one of levels} to name the level, or {'abstain': True} to decline.",
}


def public_problem():
    problem = dict(PUBLIC_PROBLEM)
    problem.update({"budget": BUDGET, "levels": list(LEVELS), "min_weak_rate": MIN_WEAK_RATE,
                    "max_sessions": MAX_SESSIONS, "max_ops_per_txn": MAX_OPS,
                    "max_ops_per_batch": MAX_BATCH_OPS})
    return problem


# ---- the worlds --------------------------------------------------------------------------------
# `rate` is how often the store takes its weak path and `seed` draws both the schedule and the
# races. In half of the worlds the budget buys full power at every boundary; in the rest it does
# not, and there the level below the truth is the one that cannot be ruled out. A starved world is
# not a quiet one: classes stronger than the truth still fire in it, so the evidence points
# somewhere and an uncalibrated answer is wrong rather than absent.
#
# Three rules shape the set. Every level has exactly one settleable world in the development split,
# so a searcher sees what naming each of the six looks like when the evidence is there. No
# unsettleable world is strict serializable: with nothing witnessed the verdict defaults to the top
# of the ladder, so a starved world at the top would pay a candidate that never declines the same
# +1 as one that reasoned, and could not tell them apart. And no unsettleable world is read
# uncommitted, because there is no such world to build: a dirty write is the cheapest class to
# catch, and even at `min_weak_rate` the budget still settles a read uncommitted store about half
# the time, so the level only ever appears where the evidence is reachable.
#
# `settleable` says which is which, and it is measured rather than assumed. One draw counts as
# settled when a full-budget round-robin over the four contention patterns both witnesses the class
# that pins the world's own level, so the verdict can reach the truth at all, and would have caught
# a store at every level below it run at the same weak rate on the same seed, so a quiet run really
# is evidence against those levels. Neither clause mentions the reference's thresholds or its
# allocation: an unsettleable world is one where declining is the only answer that is not a guess,
# whoever is asking. The flag is the share of 50 re-drawn seeds at the world's own level and rate
# that come out settled, since a single run fails now and then even where the budget is ample.
# .research/isolation_level_audit/settleable.py recomputes the table and checks that no world sits
# between 0.35 and 0.80, so no flag here turns on where the line was drawn.
def _w(name, level, rate, seed, settleable):
    return {"name": name, "level": level, "rate": rate, "seed": seed,
            "settleable": bool(settleable)}


DEVELOPMENT_WORLDS = (
    _w("dev-01", "read_uncommitted", 0.30, 101, True),
    _w("dev-02", "read_committed", 0.24, 102, True),
    _w("dev-03", "snapshot_isolation", 0.24, 103, True),
    _w("dev-04", "serializable", 0.22, 104, True),
    _w("dev-05", "strict_serializable", 0.28, 105, True),
    _w("dev-06", "read_committed", 0.04, 106, False),
    _w("dev-07", "parallel_snapshot", 0.18, 107, True),
    _w("dev-08", "parallel_snapshot", 0.08, 108, False),
    _w("dev-09", "read_committed", 0.045, 109, False),
    _w("dev-10", "parallel_snapshot", 0.05, 110, False),
    _w("dev-11", "parallel_snapshot", 0.07, 111, False),
    _w("dev-12", "snapshot_isolation", 0.04, 112, False),
)

HELDOUT_WORLDS = (
    _w("held-01", "read_committed", 0.28, 201, True),
    _w("held-02", "parallel_snapshot", 0.25, 202, True),
    _w("held-03", "serializable", 0.26, 203, True),
    _w("held-04", "strict_serializable", 0.23, 204, True),
    _w("held-05", "read_uncommitted", 0.10, 205, True),
    _w("held-06", "snapshot_isolation", 0.04, 206, False),
    _w("held-07", "parallel_snapshot", 0.06, 207, False),
    _w("held-08", "read_committed", 0.04, 208, False),
)


# ---- scoring -----------------------------------------------------------------------------------
def _validate(submission):
    """Return (level or None for a decline, confidence)."""
    if not isinstance(submission, dict):
        raise ValueError("submission must be a mapping")
    conf = submission.get("confidence", 0.0)
    if isinstance(conf, bool) or not isinstance(conf, (int, float)):
        raise ValueError("confidence must be a number")
    conf = float(conf)
    if not math.isfinite(conf):
        raise ValueError("confidence must be finite")
    confidence = min(1.0, max(0.0, conf))
    if submission.get("abstain", False) is True:
        return None, confidence
    level = submission.get("level")
    if level in (None, "unknown", "decline"):
        return None, confidence
    if level not in LEVELS:
        raise ValueError("level must be one of %s" % (", ".join(LEVELS)))
    return level, confidence


ROW_KEYS = ("mechanism_score", "named", "correct", "wrong")


def _evaluate_world(audit, spec, split, index):
    bench = _Bench(spec["level"], spec["rate"], spec["seed"])
    base = {"split": split, "world_index": int(index), "name": spec["name"],
            "truth": spec["level"], "weak_rate": spec["rate"],
            "settleable": spec["settleable"], "ops_used": 0}
    try:
        run = bench.api()
        submission = audit(public_problem(), run)
        level, confidence = _validate(submission)
        if bench.violated:
            raise RuntimeError("operation budget exceeded")
        correct = level is not None and level == spec["level"]
        wrong = level is not None and not correct
        score = 1.0 if correct else (-1.0 if wrong else 0.0)
        target = 1.0 if correct else 0.0
        row = dict(base)
        row.update({"mechanism_score": score, "named": level is not None,
                    "correct": correct, "wrong": wrong, "valid": True,
                    "said": level or "declined", "confidence": round(confidence, 6),
                    "confidence_calibration_score": round(1.0 - (confidence - target) ** 2, 6),
                    "ops_used": bench.used})
        return row
    except Exception as exc:  # noqa: BLE001 - a bad candidate scores the world, it does not crash
        row = dict(base)
        row.update({"mechanism_score": -1.0, "named": False, "correct": False, "wrong": True,
                    "valid": False, "reason": "%s: %s" % (type(exc).__name__, exc),
                    "said": "invalid", "confidence": 0.0, "confidence_calibration_score": 0.0,
                    "ops_used": bench.used})
        return row


def _mean(values):
    values = list(values)
    return float(sum(values) / len(values)) if values else 0.0


def _split_summary(records):
    raw = _mean(r["mechanism_score"] for r in records)
    # The three discovery axes are read against what each world could have supported. A claim is a
    # world the candidate actually named, so the false-discovery denominator is claims and not
    # worlds; a refusal is only *correct* where the budget could not have settled the world; and
    # coverage is how much of what was settleable the candidate went on to settle. A candidate that
    # declines everything is perfect on false discovery and on correct refusal and has discovered
    # nothing, which is exactly the 0.0 the mechanism score gives it.
    claims = [r for r in records if r["valid"] and r["named"]]
    starved = [r for r in records if not r["settleable"]]
    settled = [r for r in records if r["settleable"]]
    return {
        # declining every world is exactly 0.0, so the clip is the whole normalization
        "normalized_mechanism": float(min(1.0, max(0.0, raw))),
        "raw_mechanism": raw,
        "identification_rate": _mean(r["correct"] for r in records),
        "misidentification_rate": _mean(r["wrong"] for r in records),
        # a world that raised is a failure, not a refusal
        "refusal_rate": _mean(r["valid"] and not r["named"] for r in records),
        "false_discovery_rate": sum(bool(r["wrong"]) for r in claims) / max(1, len(claims)),
        "false_discovery_count": sum(bool(r["wrong"]) for r in claims),
        "false_discovery_denominator": len(claims),
        "correct_refusal_rate": _mean(r["valid"] and not r["named"] for r in starved),
        "correct_refusal_count": sum(bool(r["valid"] and not r["named"]) for r in starved),
        "correct_refusal_denominator": len(starved),
        "discovery_coverage": _mean(r["valid"] and r["named"] for r in settled),
        "discovery_count": sum(bool(r["valid"] and r["named"]) for r in settled),
        "discovery_denominator": len(settled),
        "confidence_calibration": _mean(r["confidence_calibration_score"] for r in records),
        "mean_ops_used": _mean(r["ops_used"] for r in records),
        "valid_count": sum(bool(r["valid"]) for r in records),
        "world_count": len(records),
    }


def evaluate(audit):
    development = [_evaluate_world(audit, spec, "development", i)
                   for i, spec in enumerate(DEVELOPMENT_WORLDS)]
    heldout = [_evaluate_world(audit, spec, "heldout", i)
               for i, spec in enumerate(HELDOUT_WORLDS)]
    dev = _split_summary(development)
    held = _split_summary(heldout)
    valid = 1.0 if dev["valid_count"] > 0 else 0.0
    return {
        "combined_score": dev["normalized_mechanism"] if valid else 0.0,
        "valid": valid,
        "feasibility_rate": dev["valid_count"] / dev["world_count"],
        "raw_score": dev["normalized_mechanism"] if valid else 0.0,
        "development_mechanism_score": dev["normalized_mechanism"],
        "development_raw_mechanism": dev["raw_mechanism"],
        "development_identification_rate": dev["identification_rate"],
        "development_misidentification_rate": dev["misidentification_rate"],
        "development_refusal_rate": dev["refusal_rate"],
        "development_false_discovery_rate": dev["false_discovery_rate"],
        "development_correct_refusal_rate": dev["correct_refusal_rate"],
        "development_discovery_coverage": dev["discovery_coverage"],
        # Each rate travels with the count it is a rate of. A refusal rate of 1.0 is one world out
        # of one or six out of six, and the difference is the whole resolution of the axis: the
        # denominators here are the worlds the candidate named, the six starved worlds and the six
        # settleable ones, not twelve in each case.
        "development_false_discovery_count": dev["false_discovery_count"],
        "development_false_discovery_denominator": dev["false_discovery_denominator"],
        "development_correct_refusal_count": dev["correct_refusal_count"],
        "development_correct_refusal_denominator": dev["correct_refusal_denominator"],
        "development_discovery_count": dev["discovery_count"],
        "development_discovery_denominator": dev["discovery_denominator"],
        "development_confidence_calibration": dev["confidence_calibration"],
        "development_mean_probes_used": dev["mean_ops_used"],
        # Evaluator-only: the sealed split is removed from the search-visible metric view by the
        # visibility contract, so a searcher cannot steer on it.
        "heldout_mechanism_score": held["normalized_mechanism"],
        "heldout_identification_rate": held["identification_rate"],
        "heldout_misidentification_rate": held["misidentification_rate"],
        "heldout_refusal_rate": held["refusal_rate"],
        "heldout_false_discovery_rate": held["false_discovery_rate"],
        "heldout_correct_refusal_rate": held["correct_refusal_rate"],
        "heldout_discovery_coverage": held["discovery_coverage"],
        "heldout_false_discovery_count": held["false_discovery_count"],
        "heldout_false_discovery_denominator": held["false_discovery_denominator"],
        "heldout_correct_refusal_count": held["correct_refusal_count"],
        "heldout_correct_refusal_denominator": held["correct_refusal_denominator"],
        "heldout_discovery_count": held["discovery_count"],
        "heldout_discovery_denominator": held["discovery_denominator"],
        "per_instance": development + heldout,
    }
