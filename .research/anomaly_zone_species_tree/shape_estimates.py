"""The reference's own site-rate shape estimate and refusal statistic on every world, next to the
true shape: the numbers behind the shape table in references/known_best.md."""
import os as _os
TASK = _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "..", "benchmarks", "Biology", "AnomalyZoneSpeciesTree"))
import sys, time
sys.path.insert(0, TASK + "/verification")
import evaluator as ev
src = open(TASK + "/verification/reference_quartet_consensus.py").read()
old = "    if worst > REFUSAL_STATISTIC:\n"
assert src.count(old) == 1
src = src.replace(old, "    _REC.append((shape, worst))\n" + old)
ns = {"_REC": []}
exec(compile(src, "ref_stat", "exec"), ns)
fn = ns["infer_species_tree"]
t0 = time.time()
for split, specs in (("dev", ev.DEVELOPMENT_WORLDS), ("held", ev.HELDOUT_WORLDS)):
    for spec in specs:
        w = ev._world(spec); c = ev._Campaign(w)
        out = fn(ev._public_problem(w), c)
        shape, worst = ns["_REC"][-1]
        print("  %-4s %-11s %d  true shape %.3f  estimated %.3f  ratio %.2f  statistic %7.1f  verdict %s" % (
            split, spec["kind"], spec["seed"], w["shape"], shape, shape / w["shape"], worst, out["verdict"]), flush=True)
print("total %.0fs" % (time.time() - t0))
