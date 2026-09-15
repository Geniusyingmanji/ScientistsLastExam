"""Ablation ladder and shortcut probe: configurable strategies built from the reference's parts."""
import json, random, sys
import engine as E, learn as L, ref as R, worlds_proto as WP


def lru_hits(W):
    return [[p] + [k - 1 if 1 <= k <= p else k for k in range(1, W)] for p in range(W)]


def templates(W):
    out = {"lru": E.LRU(W), "fifo": E.FIFO(W), "nru": E.AgeTable(W, 2, [0, 0], 0),
           "srrip_hp": E.AgeTable(W, 4, [0, 0, 0, 0], 2), "srrip_fp": E.AgeTable(W, 4, [0, 0, 1, 2], 2),
           "lip": E.PermutationPolicy(W, lru_hits(W), list(range(1, W)) + [0], start=list(range(W - 1, -1, -1)))}
    if W & (W - 1) == 0:
        out["plru"] = E.PLRU(W)
    return out


def template_fit(box, rng, cap_frac=0.01):
    data = R.observe(box, R.mixed_traces(box.W, rng, box.fresh, 24), 3)
    total = sum(len(t) for t, _ in data)
    best = None
    for name, p in templates(box.W).items():
        b = R.mismatches(p, data, 10 ** 9)
        if best is None or b < best[0]:
            best = (b, p)
    if best[0] <= max(3, int(cap_frac * total)):
        return E.machine(best[1])
    return None


CONFIGS = {
    "reference": {},
    "headroom": {"permfit": True},
    "no_det2": {"det2": False},
    "no_det": {"det1": False, "det2": False},
    "cap_big": {"cap": 1024},
    "cap_big_no_det2": {"cap": 1024, "det2": False},
    "weak_check": {"checks": 4},
    "no_check": {"check": False},
    "family_only": {"lstar": False},
    "family_only_nocheck": {"lstar": False, "check": False},
    "lstar_only": {"family": False},
    "lstar_only_cap_big": {"family": False, "cap": 1024},
    "permfit_only": {"family": False, "lstar": False, "permfit": True},
    "permfit_only_nocheck": {"family": False, "lstar": False, "permfit": True, "check": False},
    "template": {"templates": True, "family": False, "lstar": False},
    "template_nodet": {"templates": True, "family": False, "lstar": False, "det1": False, "det2": False},
    "template_nocheck": {"templates": True, "family": False, "lstar": False, "check": False},
    "template_loose": {"templates": True, "family": False, "lstar": False, "check": False, "loose": 0.05, "det2": False},
    "family_loose": {"lstar": False, "check": False, "det2": False},
    "all_parts": {"templates": True, "permfit": True, "cap": 1024},
}


def strategy(box, rng, cfg):
    chk = cfg.get("check", True)

    def ok(m, n=16):
        return m is not None and (not chk or R.check(box, m, rng, n, 5) is None)
    try:
        if cfg.get("det1", True) and L.determinism(box, rng) > 6.0:
            return None, "det1"
        if cfg.get("det2", True):
            z, w = R.determinism2(box, rng)
            if z > 4.0 or w > 6.0:
                return None, "det2"
        if cfg.get("templates"):
            m = template_fit(box, rng, cfg.get("loose", 0.01))
            if ok(m):
                return m, "template"
        if cfg.get("family", True):
            m = R.fit_family(box, rng)
            if ok(m):
                return m, "family"
        if cfg.get("permfit"):
            import permfit as PF
            m = PF.permfit(box)
            if ok(m, cfg.get("checks", 64)):
                return m, "permfit"
        if cfg.get("lstar", True):
            ls = L.LStar(box, 1024)
            for _ in range(40):
                hyp = ls.hypothesis()
                if hyp[0] > cfg.get("cap", 32):
                    return None, "too_big"
                if not chk:
                    return hyp, "lstar_first"
                t = R.check(box, hyp, rng, cfg.get("checks", 64), 5)
                if t is None:
                    return hyp, "lstar"
                ce = L.counterexample(box, hyp, t)
                if ce is not None:
                    ls.add_counterexample(ce, hyp)
    except L.Budget:
        return None, "budget"
    except ValueError:
        return None, "error"
    return None, "none"


def score(p, m):
    if p.randomized:
        return (1.0, "refuse-ok") if m is None else (0.0, "FD")
    if m is None:
        return 0.0, "declined"
    return (1.0, "correct") if E.equivalent(m, E.machine(p, cap=10 ** 6)) is None else (-1.0, "WRONG")


def run(name, seed, split):
    worlds = WP.DEV if split == "dev" else WP.HELD
    if name.startswith("blind_"):
        tname = name[6:]
    rows = {}
    for wname, p in worlds.items():
        if name.startswith("blind_"):
            tp = templates(p.W).get(tname)
            m = E.machine(tp) if tp is not None else None
            why = "blind"
        else:
            rng = random.Random(seed)
            box = L.Box(E.Cache(p, 0.02, 10 ** 9, seed=seed * 31 + 1), p.W, 0.02, 200000, rng)
            box.lead = 9.2
            m, why = strategy(box, rng, CONFIGS[name])
        s, tag = score(p, m)
        rows[wname] = (s, tag, why)
    a = sum(1 for p in worlds.values() if p.randomized) / len(worlds)
    raw = sum(r[0] for r in rows.values()) / len(rows)
    norm = max(0.0, min(1.0, (raw - a) / (1 - a)))
    fd = sum(1 for r in rows.values() if r[1] in ("FD", "WRONG"))
    return {"strategy": name, "seed": seed, "split": split, "normalized": round(norm, 3), "raw": round(raw, 3),
            "false": fd, "rows": rows}


if __name__ == "__main__":
    print(json.dumps(run(sys.argv[1], int(sys.argv[2]), sys.argv[3])), flush=True)
