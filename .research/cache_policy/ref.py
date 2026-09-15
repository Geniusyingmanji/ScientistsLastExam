"""Prototype reference for CacheReplacementPolicyID: determinism test, age-table family fit,
L* (Rivest-Schapire) fallback, targeted verification. Truth-blind: uses only Box."""
import itertools
import math
import random

import engine as E
import learn as L


def stress_trace(W, rng, fresh):
    """A burst of misses, then re-accesses of what the burst brought in and of older blocks."""
    base = list(range(W))
    t = []
    for _ in range(rng.randint(0, 3)):
        t.append(rng.choice(base))
    burst = [next(fresh) for _ in range(rng.randint(1, 2 * W))]
    t += burst
    tail = burst[-W:] + base
    rng.shuffle(tail)
    t += tail[: rng.randint(2, W + 2)]
    return t


def perm_trace(W, rng, fresh):
    """Hits that reorder the resident blocks, a short burst, then re-accesses."""
    base = list(range(W))
    t = [rng.choice(base) for _ in range(rng.randint(W, 2 * W))]
    burst = [next(fresh) for _ in range(rng.randint(1, W))]
    tail = base + burst
    rng.shuffle(tail)
    return t + burst + tail[: rng.randint(2, W + 2)]


def mixed_traces(W, rng, fresh, n):
    out = []
    for k in range(n):
        if k % 3 == 1:
            out.append(stress_trace(W, rng, fresh))
        elif k % 3 == 2:
            out.append(perm_trace(W, rng, fresh))
        else:
            rate = rng.choice([0.2, 0.35, 0.6])
            pool = list(range(W)); t = []
            for _ in range(24):
                b = next(fresh) if rng.random() < rate else rng.choice(pool[-(W + 2):])
                t.append(b); pool.append(b)
            out.append(t)
    return out


def observe(box, traces, reps):
    data = []
    for t in traces:
        counts = [0] * len(t)
        for _ in range(reps):
            for j, h in enumerate(box.run(t)):
                counts[j] += h
        data.append((t, [c * 2 > reps for c in counts]))
    return data


def simulate(policy, trace):
    m = policy.reset(); ways = list(range(policy.W)); out = []
    for b in trace:
        if b in ways:
            m = policy.hit(m, ways.index(b)); out.append(True)
        else:
            v, m = policy.miss(m); ways[v] = b; out.append(False)
    return out


def family(W):
    for A in (2, 4):
        for table in itertools.product(range(A), repeat=A):
            for ins in range(A):
                for age_all in (True, False):
                    yield E.AgeTable(W, A, table, ins, age_all=age_all)


def mismatches(policy, data, cap):
    bad = 0
    for t, obs in data:
        pred = simulate(policy, t)
        bad += sum(p != o for p, o in zip(pred, obs))
        if bad > cap:
            return bad
    return bad


def check(box, machine, rng, n, reps, confirm=6):
    """Targeted verification: mixed traces, majority of `reps`, disagreements confirmed."""
    for t in mixed_traces(box.W, rng, box.fresh, n):
        pred = L.predict(machine, t, box.W)
        counts = [0] * len(t)
        for _ in range(reps):
            for j, h in enumerate(box.run(t)):
                counts[j] += h
        for j in range(len(t)):
            if (counts[j] * 2 > reps) != pred[j]:
                c, k = counts[j], reps
                for _ in range(confirm):
                    c += box.run(t[: j + 1])[j]; k += 1
                if (c * 2 > k) != pred[j]:
                    return t[: j + 1]
    return None


def fit_family(box, rng, n_traces=24, reps=3):
    data = observe(box, mixed_traces(box.W, rng, box.fresh, n_traces), reps)
    total = sum(len(t) for t, _ in data)
    cap = max(3, int(0.01 * total))
    scored = []
    for p in family(box.W):
        b = mismatches(p, data, cap)
        if b <= cap:
            scored.append((b, p))
    if not scored:
        return None
    best = min(b for b, _ in scored)
    close = [p for b, p in scored if b <= best + 2]
    machines = []
    for p in close:
        m = E.machine(p)
        if all(E.equivalent(m, o) is not None for o in machines):
            machines.append(m)
    # several inequivalent survivors: settle each pair with the victim query their difference names
    while len(machines) > 1:
        a, b = machines[0], machines[1]
        word = E.equivalent(a, b)
        v = box.victim(tuple(word[:-1]))
        keep = []
        for m in machines:
            if L.predict_victim(m, word) == v:
                keep.append(m)
        if not keep:
            return None
        if len(keep) == len(machines):
            break
        machines = keep
    return machines[0] if len(machines) == 1 else None


def burst_trace(W, rng, fresh):
    """Resident hits, a burst of misses, then every burst block and resident block re-accessed:
    where insertion or eviction is random, which of them survive varies from run to run."""
    base = list(range(W))
    t = [rng.choice(base) for _ in range(rng.randint(0, W))]
    burst = [next(fresh) for _ in range(rng.randint(W // 2, 2 * W))]
    tail = burst + base
    rng.shuffle(tail)
    return t + burst + tail


def cyclic_trace(W, rng, fresh):
    """A loop over more blocks than there are ways, a few times: every miss is a chance for a
    random choice to show, and the next pass re-reads what it chose."""
    blocks = list(range(W)) + [next(fresh) for _ in range(rng.randint(1, W // 2 + 1))]
    rng.shuffle(blocks)
    return blocks * rng.randint(2, 4)


def determinism2(box, rng, n=24, reps=48):
    """Pooled minority test: for a deterministic policy each position's minority count over `reps`
    runs is at most Binomial(reps, q); randomness adds to it. Returns the pooled z and the
    smallest per-position log10 tail probability."""
    q = box.q
    minority, total, worst = 0, 0, 0.0
    for k in range(n):
        t = (burst_trace if k % 2 else cyclic_trace)(box.W, rng, box.fresh)
        counts = [0] * len(t)
        for _ in range(reps):
            for j, h in enumerate(box.run(t)):
                counts[j] += h
        for c in counts:
            m = min(c, reps - c)
            minority += m; total += reps
            p = sum(math.comb(reps, j) * q ** j * (1 - q) ** (reps - j) for j in range(m, reps + 1))
            worst = max(worst, -math.log10(max(p, 1e-300)))
    z = (minority - total * q) / math.sqrt(total * q * (1 - q))
    return z, worst


def reference(box, rng, max_states=512, lead=math.log(1e4), det_threshold=6.0, rounds=40,
              claim_cap=32, checks=64, use_permfit=False):
    box.lead = lead
    try:
        if L.determinism(box, rng) > det_threshold:
            return {"verdict": "no_policy", "why": "nondeterministic"}
        z, worst = determinism2(box, rng)
        box.det = (round(z, 2), round(worst, 2))
        if z > 4.0 or worst > 6.0:
            return {"verdict": "no_policy", "why": "nondeterministic2 z=%.1f w=%.1f" % (z, worst)}
        m = fit_family(box, rng)
        if m is not None and check(box, m, rng, 16, 5) is None:
            return {"verdict": "policy", "machine": m, "why": "family"}
        if use_permfit:
            import permfit as PF
            m = PF.permfit(box)
            if m is not None and check(box, m, rng, checks, 5) is None:
                return {"verdict": "policy", "machine": m, "why": "permfit"}
        ls = L.LStar(box, max_states)
        for _ in range(rounds):
            hyp = ls.hypothesis()
            if hyp[0] > claim_cap:
                return {"verdict": "no_policy", "why": "too_big_%d" % hyp[0]}
            t = check(box, hyp, rng, checks, 5)
            if t is None:
                return {"verdict": "policy", "machine": hyp, "why": "lstar"}
            ce = L.counterexample(box, hyp, t)
            if ce is not None:
                ls.add_counterexample(ce, hyp)
    except L.Budget:
        return {"verdict": "no_policy", "why": "budget"}
    return {"verdict": "no_policy", "why": "rounds"}


WORLDS = {
    "fifo4": E.FIFO(4), "plru4": E.PLRU(4), "lru4": E.LRU(4), "nru4": E.AgeTable(4, 2, [0, 0], 0),
    "switch4": E.Switch(4, 4), "plru8": E.PLRU(8), "nru8": E.AgeTable(8, 2, [0, 0], 0),
    "srrip_hp4": E.AgeTable(4, 4, [0, 0, 0, 0], 2), "age4_x": E.AgeTable(4, 4, [1, 0, 3, 1], 3),
    "bip4": E.BIP(4, 1 / 16), "srrip_rtie4": E.AgeTable(4, 4, [0, 0, 0, 0], 2, tie="random"),
    "perm4_a": E.random_permutation_policy(4, 101), "perm4_b": E.random_permutation_policy(4, 202),
    "perm5_a": E.random_permutation_policy(5, 303), "agemiss4": E.AgeOnMiss(4, 4, [0, 0, 1, 1], 1),
    "bip4_64": E.BIP(4, 1 / 64), "plru4_fb64": E.PLRUFallback(4, 1 / 64),
    "plru4_fb32": E.PLRUFallback(4, 1 / 32), "plru4_fb16": E.PLRUFallback(4, 1 / 16),
}

if __name__ == "__main__":
    import sys
    q = float(sys.argv[1]); budget = int(sys.argv[2]); seed = int(sys.argv[3]) if len(sys.argv) > 3 else 7
    only = sys.argv[4].split(",") if len(sys.argv) > 4 else list(WORLDS)
    for name in only:
        p = WORLDS[name]
        rng = random.Random(seed)
        box = L.Box(E.Cache(p, q, 10 ** 9, seed=seed * 31 + 1), p.W, q, budget, rng)
        res = reference(box, rng)
        ok = None
        if res["verdict"] == "policy" and not p.randomized:
            ok = E.equivalent(res["machine"], E.machine(p)) is None
        print(name, res["verdict"], res["why"], getattr(box, "det", ""), res["machine"][0] if "machine" in res else "-",
              "correct" if ok else ("WRONG" if ok is False else ""), "spent", box.spent, flush=True)
