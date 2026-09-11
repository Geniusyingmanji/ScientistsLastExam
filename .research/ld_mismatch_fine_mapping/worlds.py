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
"""Construction statistics of every graded world: the mismatch, the single-world trap proxy, the
masked partner's marginal rank and sign, the weakest multi signal's rank, and the near-duplicate's
correlation in the cohort and in the panel."""
import numpy as np
for split, specs in (("development", ev.DEVELOPMENT_WORLDS), ("heldout", ev.HELDOUT_WORLDS)):
    for spec in specs:
        w = ev._world(spec); R, Rr, z = w["R"], w["R_ref"], w["z"]
        order = np.argsort(-np.abs(z)); rank = lambda j: int(np.where(order == j)[0][0])
        line = "%-11s %-10s seed %d mismatch %.3f (max |dr| %.2f) |" % (split, w["kind"], spec["seed"], w["mismatch"], np.abs(Rr - R).max())
        if w["kind"] == "single":
            j = w["causal"][0]
            traps = [p for p in range(ev.N_SNP) if p != j and R[j, p] ** 2 >= ev.TRAP_R2 and Rr[j, p] ** 2 <= ev.TRAP_REF_R2 and abs(z[p]) >= ev.GENOME_WIDE_Z]
            p = max(traps, key=lambda p: abs(z[p]))
            line += " causal z %.1f; trap proxy %d: cohort r2 %.2f, panel r2 %.2f, z %.1f" % (z[j], p, R[j, p] ** 2, Rr[j, p] ** 2, z[p])
        elif w["kind"] == "masked":
            i, j = sorted(w["causal"], key=lambda v: -abs(w["truth_beta"][v]))
            l, q = sorted(w["causal"], key=lambda v: -abs(z[v]))
            cond = (z[q] - R[l, q] * z[l]) ** 2 / (1 - R[l, q] ** 2)
            line += " lead z %.1f rank %d; partner z %.1f rank %d, sign %s, effect ratio %.2f, r %.2f (panel %.2f), conditional chi2 %.1f" % (
                z[i], rank(i), z[j], rank(j), "wrong" if z[j] * w["truth_beta"][j] < 0 else "right",
                w["truth_beta"][j] / w["truth_beta"][i], R[i, j], Rr[i, j], cond)
        elif w["kind"] == "multi":
            ranks = sorted(rank(j) for j in w["causal"])
            line += " causal z %s ranks %s" % (["%.1f" % z[j] for j in w["causal"]], ranks)
        else:
            i, j = w["duplicate"]; c = i if i in w["unresolved_causal"] else j
            line += " %d signals, causal %s z %s; pair %d z %.1f rank %d, duplicate z %.1f rank %d; r cohort %.3f panel %.3f; z2 difference %.2f; gap to other swaps %.1f" % (
                w["signals"], w["unresolved_causal"], ["%.1f" % z[v] for v in w["unresolved_causal"]], c, z[c], rank(c), z[i + j - c], rank(i + j - c),
                R[i, j], Rr[i, j], abs(z[i] ** 2 - z[j] ** 2), w["gap"])
        line += "; resolvability gap %.1f" % w["gap"]
        print(line)
