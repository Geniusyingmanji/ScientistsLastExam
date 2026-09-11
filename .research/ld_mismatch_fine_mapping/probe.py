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

"""Shortcut probe for LDMismatchFineMapping: a grid of low-dimensional strategies."""
import os, json, math, itertools, time

import numpy as np



N_TOP = 12  # exhaustive configurations are drawn from the top-N_TOP variants by |z| among the usable ones


def make_strategy(ld, model, refusal, effects):
    def fine_map(problem, ld_row):
        z = np.asarray(problem["z"], float); se = np.asarray(problem["standard_error"], float)
        n = int(problem["n_gwas"]); budget = int(problem["row_budget"]); p = len(z)
        R = np.asarray(problem["reference_ld"], float).copy()
        bought = []; verify = []
        def buy(v):
            row = np.asarray(ld_row(int(v)), float); R[v, :] = row; R[:, v] = row; bought.append(int(v))
        order = [int(v) for v in np.argsort(-np.abs(z))]
        if ld[0] == "topk":
            for v in order[:ld[1]]:
                buy(v)
        elif ld[0] == "chase":
            nverify = ld[1]
            buy(order[0])
            while len(bought) < budget - nverify:
                _s, config, lam = ref._best_config(z, R, bought, math.log(n) + 2 * math.log(p))
                t = ref._residual_t(z, R, config, lam); t[bought] = 0
                nxt = int(np.argmax(np.abs(t)))
                if abs(t[nxt]) < 3.0:
                    break
                buy(nxt)
            _s, config, lam = ref._best_config(z, R, bought, math.log(n) + 2 * math.log(p))
            predicted = np.abs(R[:, list(config)] @ lam)
            for v in np.argsort(-predicted):
                v = int(v)
                if len(bought) >= budget:
                    break
                if v not in bought:
                    buy(v); verify.append(v)
        # model
        model_rows = [v for v in bought if v not in verify] if bought else []
        if model[0] == "top1":
            config = [order[0]]
        elif model[0] == "clump":
            config = []
            for v in order:
                if abs(z[v]) < 5.45 and config:
                    break
                if all(R[v, c] ** 2 < model[1] for c in config):
                    config.append(v)
                if len(config) == 3:
                    break
        elif model[0] == "cojo":
            config = [order[0]]
            while len(config) < 3:
                S = config; lam = np.linalg.solve(R[np.ix_(S, S)] + 1e-6 * np.eye(len(S)), z[S])
                inv = np.linalg.inv(R[np.ix_(S, S)] + 1e-6 * np.eye(len(S)))
                var = np.maximum(1 - np.einsum("is,st,it->i", R[:, S], inv, R[:, S]), 0.05)
                t = (z - R[:, S] @ lam) / np.sqrt(var); t[S] = 0
                nxt = int(np.argmax(np.abs(t)))
                if abs(t[nxt]) < model[1]:
                    break
                config.append(nxt)
        else:  # ebic over candidates
            pen = model[1] * (math.log(n) + 2 * math.log(p))
            cand = model_rows if (bought and ld[0] == "chase") else (bought if bought else order[:N_TOP])
            best = None
            for k in range(1, 4):
                for S in itertools.combinations(cand, k):
                    S = list(S)
                    test = [v for v in (bought if bought else order[:N_TOP]) if v not in S]
                    inv = np.linalg.inv(R[np.ix_(S, S)] + 1e-9 * np.eye(k)); lam = inv @ z[S]
                    if test:
                        resid = z[test] - R[np.ix_(test, S)] @ lam
                        C = R[np.ix_(test, test)] - R[np.ix_(test, S)] @ inv @ R[np.ix_(S, test)] + 1e-6 * np.eye(len(test))
                        chi = float(resid @ np.linalg.solve(C, resid))
                    else:
                        chi = 0.0
                    sc = chi + pen * k
                    if best is None or sc < best[0]:
                        best = (sc, S)
            config = best[1]
        S = config
        inv = np.linalg.inv(R[np.ix_(S, S)] + 1e-9 * np.eye(len(S))); lam = inv @ z[S]
        # refusal
        abstain = False
        pool = bought if bought else order[:N_TOP]   # what the strategy can compare against
        if refusal[0] == "dup":
            # decline when a modelled variant has a close proxy in whatever LD the strategy holds
            abstain = any(abs(R[v, u]) >= refusal[1] for v in S for u in pool if u != v)
        elif refusal[0] == "swap":
            own = float(z[S] @ np.linalg.solve(R[np.ix_(S, S)] + 1e-9 * np.eye(len(S)), z[S]))
            margin = math.inf
            for i in range(len(S)):
                for u in pool:
                    if u in S:
                        continue
                    alt = list(S); alt[i] = u
                    fit = float(z[alt] @ np.linalg.solve(R[np.ix_(alt, alt)] + 1e-9 * np.eye(len(alt)), z[alt]))
                    margin = min(margin, own - fit)
            abstain = margin < refusal[1]
        elif refusal[0] == "maxt":
            var = np.maximum(1 - np.einsum("is,st,it->i", R[:, S], inv, R[:, S]), 0.05)
            t = (z - R[:, S] @ lam) / np.sqrt(var); t[S] = 0
            abstain = float(np.abs(t).max()) > refusal[1]
        if abstain:
            return {"verdict": "unresolved", "confidence": 0.8}
        if effects == "joint":
            eff = [float(lam[i] * se[v]) for i, v in enumerate(S)]
        else:
            eff = [float(z[v] * se[v]) for v in S]
        return {"verdict": "typed", "causal": [int(v) for v in S], "effects": eff, "confidence": 0.8}
    return fine_map


LD = [("ref",), ("topk", 2), ("topk", 4), ("topk", 6), ("chase", 0), ("chase", 2), ("chase", 4)]
MODEL = [("top1",), ("clump", 0.1), ("clump", 0.2), ("clump", 0.5), ("cojo", 4.0), ("cojo", 5.0), ("cojo", 5.45),
         ("ebic", 0.5), ("ebic", 1.0), ("ebic", 1.6)]
REFUSAL = [("never",), ("dup", 0.9), ("dup", 0.95), ("dup", 0.98), ("swap", 1.0), ("swap", 3.0), ("swap", 6.0), ("maxt", 4.0)]
EFFECTS = ["joint", "marginal"]

if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(OUT, "ld_mismatch_probe_results.jsonl")
    done = set()
    if os.path.exists(out):
        for line in open(out):
            done.add(json.loads(line)["name"])
    t0 = time.time()
    with open(out, "a") as fh:
        for ld, model, refusal, effects in itertools.product(LD, MODEL, REFUSAL, EFFECTS):
            name = "%s|%s|%s|%s" % (ld, model, refusal, effects)
            if name in done:
                continue
            m = ev.evaluate(make_strategy(ld, model, refusal, effects))
            rec = {"name": name, "ld": ld, "model": model, "refusal": refusal, "effects": effects,
                   "dev": m["combined_score"], "held": m["heldout_mechanism_score"],
                   "dev_fdr": m["development_false_discovery_rate"], "dev_refusal": m["development_correct_refusal_rate"]}
            fh.write(json.dumps(rec) + "\n"); fh.flush()
    print("done %.0fs" % (time.time() - t0))
