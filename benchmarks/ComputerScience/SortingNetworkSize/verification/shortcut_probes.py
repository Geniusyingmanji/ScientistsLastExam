"""Review-only generic construction probes; never read stored comparator data."""
from pathlib import Path
import importlib.util


def _baseline_module():
    path = Path(__file__).resolve().parents[1] / 'solution.py'
    spec = importlib.util.spec_from_file_location('sorting_generic_baseline', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


BASE = _baseline_module()


def batcher(n):
    return BASE._batcher(n)


def pruned_batcher(n):
    return BASE._prune(batcher(n), n)


def window_grid(n):
    width = 1 << (n - 1).bit_length()
    full = BASE._batcher(width)
    choices = [[(i - offset, j - offset) for i, j in full
                if offset <= i < j < offset + n]
               for offset in range(width - n + 1)]
    return min(choices, key=lambda net: (len(net), net))


def window_grid_pruned(n):
    return BASE.build_network(n)


def insertion(n):
    return [(j - 1, j) for i in range(1, n) for j in range(i, 0, -1)]
