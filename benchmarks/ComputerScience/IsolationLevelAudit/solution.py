"""Baseline for IsolationLevelAudit: run contention and look for the symptoms you can see by eye.

It drives two sessions at the same keys so that transactions have something to conflict over, and
then scans the histories for the two things a reader can spot without ever building a dependency
graph: a read that returned an element whose writer went on to abort, and a key whose list came
back shorter than it had come back before. The first says the store publishes uncommitted data,
the second that a reader's view of a key can go backwards.

It never declines and it never asks whether the contention it bought actually produced a race.

Replace `audit` with your own. It takes the public `problem` and the `run` function described in
Task.md, and returns {"level": ...} or {"abstain": True}.
"""
from __future__ import annotations


def audit(problem, run):
    budget = problem["budget"]
    spent, key = 0, 0
    dirty = False
    backwards = False
    longest = {}
    while spent + 12 <= budget:
        a, b = key, key + 1
        key += 2
        batch = [[[["r", a], ["a", a], ["r", b], ["a", b]]],
                 [[["r", b], ["a", b], ["r", a], ["a", a]]]]
        spent += 8
        txns = run(batch)["transactions"]
        spent += 2
        txns += run([[], [[["r", a], ["r", b]]]])["transactions"]
        aborted = set()
        for t in txns:
            if t["status"] != "committed":
                aborted.update(v for kind, _k, v in t["ops"] if kind == "a")
        for t in txns:
            for kind, k, v in t["ops"]:
                if kind != "r":
                    continue
                if set(v) & aborted:
                    dirty = True
                if len(v) < longest.get(k, 0):
                    backwards = True
                longest[k] = max(longest.get(k, 0), len(v))
    if dirty:
        return {"level": "read_uncommitted", "confidence": 0.5}
    if backwards:
        return {"level": "read_committed", "confidence": 0.4}
    return {"level": "strict_serializable", "confidence": 0.3}
