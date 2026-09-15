"""Headroom learner: Abel-Reineke style permutation-policy inference through victim queries.

Positions are defined by eviction rank under consecutive misses; that works whenever W misses in
a row evict every resident block once. Each hit vector is read off one hit and W victim queries."""
import random, sys
import engine as E, learn as L, ref as R


def permfit(box):
    W = box.W

    def ranks(prefix):
        seq, w = [], tuple(prefix)
        for _ in range(W):
            seq.append(box.victim(w)); w = w + ("M",)
        if sorted(seq) != list(range(W)):
            return None
        return {way: W - 1 - k for k, way in enumerate(seq)}      # way -> position

    pos0 = ranks(())
    if pos0 is None:
        return None
    at0 = {p: w for w, p in pos0.items()}
    hp = []
    for p in range(W):
        new = ranks((at0[p],))
        if new is None:
            return None
        perm = [None] * W
        for w, k in new.items():
            perm[k] = pos0[w]
        hp.append(perm)
    new = ranks(("M",))
    if new is None:
        return None
    v0 = at0[W - 1]
    mp = [None] * W
    for w, k in new.items():
        mp[k] = 0 if w == v0 else pos0[w] + 1
    policy = E.PermutationPolicy(W, hp, mp, start=[at0[k] for k in range(W)])
    return E.machine(policy, cap=2000)


if __name__ == "__main__":
    q = float(sys.argv[1])
    worlds = {"lru4": E.LRU(4), "plru4": E.PLRU(4), "plru8": E.PLRU(8), "perm5_a": R.WORLDS["perm5_a"],
              "perm4_a": R.WORLDS["perm4_a"], "fifo4": E.FIFO(4), "lip4": E.lip_like(4, 3, 5),
              "ins2_4": E.lip_like(4, 2, 6), "ins0_4": E.lip_like(4, 0, 7), "srrip_hp4": R.WORLDS["srrip_hp4"],
              "switch4": R.WORLDS["switch4"], "perm5_b": E.random_permutation_policy(5, 404),
              "perm6_a": E.random_permutation_policy(6, 505)}
    for name, p in worlds.items():
        rng = random.Random(3)
        box = L.Box(E.Cache(p, q, 10 ** 9, seed=5), p.W, q, 10 ** 9, rng)
        box.lead = 9.2
        try:
            m = permfit(box)
        except ValueError as e:
            m = None; print(name, "error", e)
        truth = E.machine(p, cap=10 ** 6)
        ok = None if m is None else (E.equivalent(m, truth) is None)
        print(name, "truth states", truth[0], "fit", None if m is None else m[0], "correct" if ok else ("WRONG" if ok is False else "none"), "spent", box.spent, flush=True)
