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

"""Reference behaviour on extra worlds of every kind, outside the graded seeds, and the same
worlds under the selection-line variants of the ladder (the false-discovery cost of a sharper
region-wide line, and the masking-aware local test)."""

import math, os
import numpy as np
ablation = _load(os.path.join(os.path.dirname(os.path.abspath(__file__)), "ablation.py"), "ld_ablation")
N = int(os.environ.get("FM_N", "25"))
worlds = []
for kind, signals in (("single", 1), ("masked", 2), ("multi", 3), ("unresolved", 1), ("unresolved", 3)):
    for k in range(N):
        spec = {"kind": kind, "signals": signals, "seed": 77000000 + 1000 * ev.WORLD_KINDS.index(kind) + 100 * signals + k, "budget": ev.ROW_BUDGET}
        worlds.append(ev._world(spec))
a = np.array([(w["attempt"], w["draw"], w["gap"]) for w in worlds], dtype=float)
print("%d worlds built: attempts mean %.1f max %d, draws mean %.1f max %d, gap min %.1f" % (len(worlds), a[:, 0].mean(), int(a[:, 0].max()), a[:, 1].mean(), int(a[:, 1].max()), a[:, 2].min()))
VARIANTS = [
    ("reference (extended BIC 18.1)", ref.fine_map),
    ("Bonferroni line for sixty variants at 0.05 (11.2)", ablation.variant(BIC_PENALTY=11.16)),
    ("plain BIC (9.9)", ablation.variant(BIC_PENALTY=math.log(ev.N_GWAS))),
    ("extended BIC halved (9.0)", ablation.variant(BIC_PENALTY=0.5 * (math.log(ev.N_GWAS) + 2 * math.log(ev.N_SNP)))),
    ("reference then the masking-aware local test", ablation.neighbourhood()),
]
for name, fn in VARIANTS:
    print("== %s" % name)
    per = {}
    for w in worlds:
        c = ev._Campaign(w).oracle(); p = ev._public_problem(w)
        out = fn(p, c); ca, ef, conf, ab = ev._validate_submission(out); m = ev._metrics(w, ca, ef, ab)
        per.setdefault((w["kind"], w["signals"]), []).append((m["mechanism_score"], m["false_discovery"], m["correct_refusal"], m["set_f1"]))
    allrows = []
    for key, rows in per.items():
        r = np.array(rows, dtype=float); allrows.append(r)
        print("   %-10s signals %d n %d mech mean %.3f min %.3f f1 %.3f | false discoveries %d | refusal %.2f" % (key[0], key[1], len(r), r[:, 0].mean(), r[:, 0].min(), r[:, 3].mean(), int(r[:, 1].sum()), r[:, 2].mean()))
    r = np.vstack(allrows)
    print("   all %d worlds: mech %.3f, false discoveries %d" % (len(r), r[:, 0].mean(), int(r[:, 1].sum())))
