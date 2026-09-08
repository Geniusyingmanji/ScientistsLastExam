"""Deterministic truth-blind search probe; not yet a qualifying reference.

Generate a generic baseline, prepend random comparator prefixes, and exactly
prune the resulting valid networks. Neutral/uphill moves allow structural changes.
No data files, known network tables, evaluator imports, or external processes.
The bounded iteration count makes the artifact deterministic across hosts.
"""
from functools import lru_cache

def _batcher(n: int):
    """Batcher odd-even mergesort on N = 2^ceil(log2 n) wires, sentinel gates removed.

    A sorting network on N >= n wires restricted to the real wires (padding with +inf
    sentinels makes every gate touching a sentinel a no-op) still sorts the first n
    wires, so deleting those gates yields a legal baseline network for any n.
    """
    size = 1
    while size < n:
        size <<= 1
    net = []

    def compare(i: int, j: int) -> None:
        if max(i, j) < n:
            net.append([min(i, j), max(i, j)])

    def merge(lo: int, length: int, r: int) -> None:
        m = r * 2
        if m < length:
            merge(lo, length, m)
            merge(lo + r, length, m)
            for i in range(lo + r, lo + length - r, m):
                compare(i, i + r)
        else:
            compare(lo, lo + r)

    def sort(lo: int, length: int) -> None:
        if length > 1:
            sort(lo, length // 2)
            sort(lo + length // 2, length // 2)
            merge(lo, length, 1)

    sort(0, size)
    return net


@lru_cache(maxsize=None)
def _inputs(n):
    wires = []
    total = 1 << n
    for wire in range(n):
        run = 1 << wire
        mask = ((1 << run) - 1) << run
        width = 2 * run
        while width < total:
            mask |= mask << width
            width *= 2
        wires.append(mask)
    return tuple(wires)


def _sorts(network, n):
    wires = list(_inputs(n))
    for i, j in network:
        a, b = wires[i], wires[j]
        wires[i], wires[j] = a & b, a | b
    return all(not (a & ~b) for a, b in zip(wires, wires[1:]))


def _prune(network, n):
    network = list(network)
    changed = True
    while changed:
        changed = False
        for pos in range(len(network) - 1, -1, -1):
            trial = network[:pos] + network[pos + 1:]
            if _sorts(trial, n):
                network = trial
                changed = True
    return network


@lru_cache(maxsize=None)
def _baseline(n):
    if not isinstance(n, int) or not 2 <= n <= 17:
        raise ValueError("supported channel counts are 2 through 17")
    width = 1 << (n - 1).bit_length()
    full = _batcher(width)
    choices = []
    for offset in range(width - n + 1):
        window = [(i - offset, j - offset) for i, j in full
                  if offset <= i < j < offset + n]
        choices.append(_prune(window, n))
    best = min(choices, key=lambda net: (len(net), net))
    return tuple(best)



SEARCH_TRIALS = 300


def search_network(n, trials=SEARCH_TRIALS, seed=0, max_extra=2):
    import random
    rng = random.Random(seed)
    best = list(_baseline(n))
    current = list(best)
    for step in range(trials):
        prefix = [tuple(sorted(rng.sample(range(n), 2)))
                  for _ in range(rng.randrange(1, 5))]
        # A sorting network accepts every possible output of the prefix.
        trial = _prune(prefix + current, n)
        if len(trial) <= len(best) + max_extra:
            current = trial
        if step % 100 == 99:
            current = list(best)
        if len(trial) < len(best):
            best = list(trial)
    return [list(pair) for pair in best]


def build_network(n):
    return search_network(n)
