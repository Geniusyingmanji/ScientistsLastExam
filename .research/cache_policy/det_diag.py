"""Distribution of the reference's determinism statistics over re-drawn seeds, on the package's
own evaluator: det1 worst tail, and det2's pooled z and worst tail after 24, 32, 40 and 48 traces."""
import json
import math
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from pkg_eval import TASK, ev, load  # noqa: E402

R = load(TASK / "verification/reference_lstar_family.py", "crp_reference_diag")
original = {s["name"]: s["seed"] for s in ev.DEVELOPMENT_WORLDS + ev.HELDOUT_WORLDS}
for shift in range(int(sys.argv[1]), int(sys.argv[2])):
    for spec in ev.DEVELOPMENT_WORLDS + ev.HELDOUT_WORLDS:
        spec["seed"] = original[spec["name"]] + 7919 * shift
        ev._WORLDS.clear()
    for spec in ev.DEVELOPMENT_WORLDS + ev.HELDOUT_WORLDS:
        world = ev._world(spec)
        world["budget"] = 10 ** 9
        bench = ev._Bench(world)
        problem = ev._public_problem(world)
        rng = random.Random(R.SEED)
        box = R._Box(problem, bench.oracle(), rng)
        q = box.q
        worst1 = 0.0
        for _ in range(6):
            for c in R._counts(box, R._random_trace(box.W, 40, rng, box.fresh), 10):
                worst1 = max(worst1, -math.log10(max(R._tail(10, q, min(c, 10 - c)), 1e-300)))
        minority, total, worst2, out = 0, 0, 0.0, {}
        for k in range(48):
            trace = (R._burst_trace if k % 2 else R._cyclic_trace)(box.W, rng, box.fresh)
            for c in R._counts(box, trace, 48):
                m = min(c, 48 - c)
                minority += m
                total += 48
                worst2 = max(worst2, -math.log10(max(R._tail(48, q, m), 1e-300)))
            if k + 1 in (24, 32, 40, 48):
                z = (minority - total * q) / math.sqrt(total * q * (1 - q))
                out[k + 1] = (round(z, 2), round(worst2, 2), box.spent)
        print(json.dumps({"shift": shift, "world": spec["name"], "kind": spec["kind"], "det1": round(worst1, 2),
                          "det2": out}), flush=True)
