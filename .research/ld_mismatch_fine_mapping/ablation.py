import os as _os, tempfile as _tempfile
TASK = _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "..", "benchmarks", "Biology", "LDMismatchFineMapping"))
OUT = _tempfile.gettempdir()
import sys, importlib.util
sys.path.insert(0, TASK + "/verification")
def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m
import evaluator as ev
import reference_conditional_rows as ref
base = _load(TASK + "/solution.py", "ld_baseline")

"""Difficulty ladder for LDMismatchFineMapping: the reference with one choice changed at a time."""
import os, json, time



probe = _load(os.path.join(os.path.dirname(os.path.abspath(__file__)), "probe.py"), "ld_probe")

REF_SRC = os.path.join(TASK, "verification", "reference_conditional_rows.py")


def variant(**consts):
    """A fresh copy of the reference module with some module constants replaced."""
    spec = importlib.util.spec_from_file_location("ref_variant", REF_SRC)
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    for k, v in consts.items():
        assert hasattr(mod, k), k
        setattr(mod, k, v)
    return mod.fine_map


def source_variant(*pairs):
    src = open(REF_SRC).read()
    for old, new in zip(pairs[0::2], pairs[1::2]):
        assert src.count(old) == 1, old
        src = src.replace(old, new)
    ns = {}
    exec(compile(src, "ref_source_variant", "exec"), ns)
    return ns["fine_map"]


def neighbourhood(r_min=0.5, alpha=0.01):
    """The reference, then a masking-aware local test: for each modelled variant, the typed variants
    in strong LD with it (from its exact row) are scanned conditionally on the model, at a
    Bonferroni line for that neighbourhood only; the best one is added if it passes."""
    import numpy as np
    from scipy.stats import chi2

    def run(problem, ld_row):
        out = ref.fine_map(problem, ld_row)
        config, margin, bought = ref.fine_map.last
        if out.get("verdict") != "typed":
            return out
        z = np.asarray(problem["z"], dtype=float); se = np.asarray(problem["standard_error"], dtype=float)
        R = np.asarray(problem["reference_ld"], dtype=float).copy()
        for v in bought:  # repeat rows are free
            row = np.asarray(ld_row(int(v)), dtype=float); R[v, :] = row; R[:, v] = row
        config = list(config); added = []
        chi = ev._conditional_chi(z, R, config)
        for v in list(config):
            nb = [u for u in range(len(z)) if u not in config and abs(R[v, u]) >= r_min]
            if not nb:
                continue
            best = max(nb, key=lambda u: chi[u])
            if chi[best] >= chi2.isf(alpha / len(nb), 1) and best not in added and len(config) + len(added) < int(problem["max_causal"]):
                added.append(best)
        config = config + added
        lam = np.linalg.solve(R[np.ix_(config, config)] + 1e-9 * np.eye(len(config)), z[config])
        return {"verdict": "typed", "causal": [int(v) for v in config],
                "effects": [float(l * se[v]) for l, v in zip(lam, config)], "confidence": 0.8}
    return run


def with_budget(fn, budget):
    def run(problem, ld_row):
        problem = dict(problem); problem["row_budget"] = budget
        return fn(problem, ld_row)
    return run



RUNGS = [
    ("reference: chase the residual, one proxy row per modelled variant, extended BIC over bought rows, swap-margin refusal, joint effects", ref.fine_map),
    ("same, trusting the reference panel instead of buying rows", probe.make_strategy(("ref",), ("ebic", 1.0), ("swap", 3.0), "joint")),
    ("same, rows bought for the six largest |z| instead of chased", probe.make_strategy(("topk", 6), ("ebic", 1.0), ("swap", 3.0), "joint")),
    ("same, stopping when the chase stops, no proxy rows at all", source_variant("    for s in sorted(config, key=lambda v: abs(z[v])):\n", "    for s in []:\n", "    for v in np.argsort(-predicted):\n", "    for v in []:\n")),
    ("same, proxy rows by the largest predicted z-score instead of one per modelled variant", source_variant("    for s in sorted(config, key=lambda v: abs(z[v])):\n", "    for s in []:\n")),
    ("same, the strongest modelled variant's proxy first instead of the weakest's", source_variant("    for s in sorted(config, key=lambda v: abs(z[v])):\n", "    for s in sorted(config, key=lambda v: -abs(z[v])):\n")),
    ("same, two proxy rows per modelled variant reserved instead of one", variant(RESOLUTION_ROWS=2)),
    ("same, no rows reserved for proxies (the chase may spend everything)", variant(RESOLUTION_ROWS=0)),
    ("same, never declining", variant(RESOLVE_MARGIN=-1.0)),
    ("same, refusal margin 1 instead of 3", variant(RESOLVE_MARGIN=1.0)),
    ("same, refusal margin 6 instead of 3", variant(RESOLVE_MARGIN=6.0)),
    ("same, declining on a near-duplicate at |r| >= 0.95 in the bought rows instead of the swap margin", probe.make_strategy(("chase", 2), ("ebic", 1.0), ("dup", 0.95), "joint")),
    ("same, marginal effects z*se instead of joint", probe.make_strategy(("chase", 2), ("ebic", 1.0), ("swap", 3.0), "marginal")),
    ("same, plain BIC (penalty log n) instead of extended", variant(BIC_PENALTY=__import__("math").log(ev.N_GWAS))),
    ("same, extended BIC penalty doubled", variant(BIC_PENALTY=2 * (__import__("math").log(ev.N_GWAS) + 2 * __import__("math").log(ev.N_SNP)))),
    ("same, extended BIC penalty halved", variant(BIC_PENALTY=0.5 * (__import__("math").log(ev.N_GWAS) + 2 * __import__("math").log(ev.N_SNP)))),
    ("same, penalty at the Bonferroni line for sixty variants at 0.05 (11.2)", variant(BIC_PENALTY=11.16)),
    ("same, then a masking-aware local test: the strong-LD neighbours (|r| >= 0.5) of each modelled variant scanned conditionally at a Bonferroni line for that neighbourhood alone", neighbourhood()),
    ("same, PLINK clumping at r^2 0.1 on the bought rows instead of the extended BIC", probe.make_strategy(("chase", 2), ("clump", 0.1), ("swap", 3.0), "joint")),
    ("same, stepwise conditional selection at t 5 on the bought rows instead of the extended BIC", probe.make_strategy(("chase", 2), ("cojo", 5.0), ("swap", 3.0), "joint")),
    ("same, chase threshold 2 instead of 3", variant(CHASE_T=2.0)),
    ("same, chase threshold 4.5 instead of 3", variant(CHASE_T=4.5)),
    ("same, a budget of 3 rows", with_budget(ref.fine_map, 3)),
    ("same, a budget of 4 rows", with_budget(ref.fine_map, 4)),
    ("same, a budget of 8 rows (more than the task allows: fails closed)", with_budget(ref.fine_map, 8)),
    ("baseline: PLINK clumping on the reference panel, marginal effects, never declining", base.fine_map),
    ("declining everything", lambda p, r: {"verdict": "unresolved", "confidence": 1.0}),
]

if __name__ == "__main__":
    only = os.environ.get("FM_ONLY")
    out = []
    t0 = time.time()
    for name, fn in RUNGS:
        if only and only not in name:
            continue
        m = ev.evaluate(fn)
        row = {"rung": name, "dev": m["combined_score"], "set_f1": m["development_set_f1"],
               "effect": m["development_effect_score"], "fdr": m["development_false_discovery_rate"],
               "refusal": m["development_correct_refusal_rate"], "coverage": m["development_discovery_coverage"],
               "rows": m["development_mean_rows_bought"], "held": m["heldout_mechanism_score"],
               "valid": m["valid"], "feasibility": m["feasibility_rate"]}
        out.append(row)
        print("%-110s dev %.3f f1 %.2f eff %.2f fdr %.2f ref %.2f cov %.2f rows %.1f held %.3f valid %d" % (
            name[:110], row["dev"], row["set_f1"], row["effect"], row["fdr"], row["refusal"], row["coverage"], row["rows"], row["held"], row["valid"]), flush=True)
    json.dump(out, open(os.path.join(OUT, "ld_mismatch_ablation_results.json"), "w"), indent=1)
    print("%.0fs" % (time.time() - t0))
