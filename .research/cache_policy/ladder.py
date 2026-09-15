"""Ablation ladder and shortcut probe on the package's own evaluator.

Every strategy is assembled from the reference's own parts
(verification/reference_permutation_augmented.py: determinism tests, the age-table library, the
permutation-policy fit in the style of Abel and Reineke, capped L* with checks) with one choice
changed, plus a textbook-template fit and blind template claims. `no_permfit` is the original
builder reference, verification/reference_lstar_family.py, which the review rejected as an
omission of a published family; it is kept as an omission probe.

    .venv/bin/python .research/cache_policy/ladder.py NAME [shift ...]
"""
import json
import math
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from pkg_eval import TASK, ev, load  # noqa: E402

R = load(TASK / "verification/reference_permutation_augmented.py", "crp_reference_ladder")
B = load(TASK / "solution.py", "crp_baseline_ladder")


def templates(W):
    lru_hits = [[p] + [k - 1 if 1 <= k <= p else k for k in range(1, W)] for p in range(W)]
    out = {"lru": B._LRU(W), "fifo": B._FIFO(W), "nru": R._AgeTable(W, 2, (0, 0), 0, True),
           "srrip_hp": R._AgeTable(W, 4, (0, 0, 0, 0), 2, True),
           "srrip_fp": R._AgeTable(W, 4, (0, 0, 1, 2), 2, True),
           "lip": ev._Permutation(W, lru_hits, list(range(1, W)) + [0], list(range(W - 1, -1, -1)))}
    if W & (W - 1) == 0:
        out["plru"] = B._TreePLRU(W)
    return out


def template_fit(box, rng, loose):
    data = [(t, [c * 2 > 3 for c in R._counts(box, t, 3)]) for t in R._mixed_traces(box.W, rng, box.fresh, 24)]
    total = sum(len(t) for t, _ in data)
    best = None
    for policy in templates(box.W).values():
        bad = sum(p != o for t, seen in data for p, o in zip(R._simulate(policy, t), seen))
        if best is None or bad < best[0]:
            best = (bad, policy)
    return R._machine(best[1]) if best[0] <= max(3, int(loose * total)) else None


CONFIGS = {
    "strategy_reference": {},
    "no_permfit": {"permfit": False},
    "no_pooled": {"pooled": False},
    "no_determinism": {"per_position": False, "pooled": False},
    "cap_big": {"cap": 1024},
    "cap_big_no_pooled": {"cap": 1024, "pooled": False},
    "weak_check": {"checks": 4},
    "no_check": {"check": False},
    "library_only": {"lstar": False, "permfit": False},
    "library_only_no_check": {"lstar": False, "permfit": False, "check": False},
    "lstar_only": {"library": False, "permfit": False},
    "lstar_only_cap_big": {"library": False, "permfit": False, "cap": 1024},
    "permfit_only": {"library": False, "lstar": False},
    "permfit_only_no_check": {"library": False, "lstar": False, "check": False},
    "no_library": {"library": False},
    "no_lstar": {"lstar": False},
    "template": {"templates": True, "library": False, "lstar": False, "permfit": False},
    "template_no_determinism": {"templates": True, "library": False, "lstar": False, "permfit": False, "per_position": False, "pooled": False},
    "template_no_check": {"templates": True, "library": False, "lstar": False, "permfit": False, "check": False},
    "template_loose": {"templates": True, "library": False, "lstar": False, "permfit": False, "check": False, "loose": 0.05, "pooled": False},
    "library_loose": {"lstar": False, "permfit": False, "check": False, "pooled": False},
    "all_parts": {"templates": True, "cap": 1024},
}


def learn(box, rng, cfg):
    checked = cfg.get("check", True)

    def ok(m, n=R.FAMILY_CHECKS):
        return m is not None and (not checked or R._check(box, m, rng, n) is None)

    if cfg.get("per_position", True) and R._per_position(box, rng):
        return None
    if cfg.get("pooled", True) and R._pooled(box, rng):
        return None
    if cfg.get("templates"):
        m = template_fit(box, rng, cfg.get("loose", 0.01))
        if ok(m):
            return m
    if cfg.get("library", True):
        m = R._fit_library(box, rng)
        if ok(m):
            return m
    if cfg.get("permfit", True):
        m = R._fit_permutation(box)
        if ok(m, cfg.get("checks", R.LSTAR_CHECKS)):
            return m
    if cfg.get("lstar", True):
        learner = R._LStar(box)
        for _ in range(R.ROUNDS):
            hyp = learner.hypothesis()
            if hyp[0] > cfg.get("cap", R.CLAIM_CAP):
                return None
            if not checked:
                return hyp
            t = R._check(box, hyp, rng, cfg.get("checks", R.LSTAR_CHECKS))
            if t is None:
                return hyp
            ce = R._abstract_counterexample(box, hyp, t)
            if ce is not None:
                learner.add_counterexample(ce, hyp)
    return None


def answer(machine):
    # A fitted template can have more rows than the public submission cap.
    # Such a hypothesis is unavailable, not a valid zero-scoring policy claim.
    if machine is None or machine[0] > 1024:
        return {"verdict": "no_policy", "confidence": 0.7}
    _n, H, M = machine
    return {"verdict": "policy", "machine": {"hit": [list(r) for r in H], "miss": [[v, t] for v, t in M]},
            "confidence": 0.8}


CALLS = []
FLAGS = {"check", "pooled", "per_position", "library", "lstar", "templates", "permfit"}


def build(name):
    if name == "reference":
        base = R.identify
    elif name.startswith("blind_"):
        def base(problem, _run, t=name[6:]):
            policy = templates(int(problem["ways"])).get(t)
            return answer(None if policy is None else R._machine(policy))
    else:
        # NAME@key=value,... overrides one configuration's choices, for the parameter sweep
        base_name, _, params = name.partition("@")
        cfg = dict(CONFIGS[base_name])
        for item in filter(None, params.split(",")):
            key, value = item.split("=")
            cfg[key] = (value != "0") if key in FLAGS else (float(value) if "." in value else int(value))
        if cfg.get("cap", 0) > R.MAX_ROWS:
            R.MAX_ROWS = cfg["cap"]

        def base(problem, run):
            rng = random.Random(R.SEED)
            box = R._Box(problem, run, rng)
            try:
                machine = learn(box, rng, cfg)
            except R._Spent:
                machine = None
            return answer(machine)

    def identify(problem, run):
        count = [0]

        def counted(trace):
            count[0] += 1
            return run(trace)
        try:
            return base(problem, counted)
        finally:
            CALLS.append(count[0])
    return identify


if __name__ == "__main__":
    name = sys.argv[1]
    shifts = [int(x) for x in sys.argv[2:]] or [0]
    original = {s["name"]: s["seed"] for s in ev.DEVELOPMENT_WORLDS + ev.HELDOUT_WORLDS}
    for shift in shifts:
        for spec in ev.DEVELOPMENT_WORLDS + ev.HELDOUT_WORLDS:
            spec["seed"] = original[spec["name"]] + 7919 * shift
        ev._WORLDS.clear()
        CALLS.clear()
        start = time.time()
        m = ev.evaluate(build(name))
        rows = m["per_instance"]
        print(json.dumps({
            "name": name, "shift": shift, "seconds": round(time.time() - start, 1),
            "dev": round(m["development_mechanism_score"], 4), "held": round(m["heldout_mechanism_score"], 4),
            "dev_fd": sum(r["false_discovery"] for r in rows if r["split"] == "development"),
            "held_fd": sum(r["false_discovery"] for r in rows if r["split"] == "heldout"),
            "dev_coverage": round(m["development_discovery_coverage"], 3),
            "held_coverage": round(m["heldout_discovery_coverage"], 3),
            "dev_recovery": round(m["development_policy_recovery"], 3),
            "max_calls": max(CALLS), "total_calls": sum(CALLS),
            "rows": [(r["split"][0] + "%02d" % (r["world_index"] + 1), r["mechanism_score"],
                      "FD" if r["false_discovery"] else "", r["runs_used"]) for r in rows]}), flush=True)
