"""Baseline: least-squares (ignores sparsity)."""
import numpy as np

def recover_sparse(A, y, k):
    x, _, _, _ = np.linalg.lstsq(A, y, rcond=None)
    return x
