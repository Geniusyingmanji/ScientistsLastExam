# SparseRecovery — compressed sensing signal recovery

## Scientific background

Compressed sensing recovers a sparse signal from far fewer measurements than the Nyquist
rate. Given `y = A x + noise` where `x` is k-sparse in R^n and A is m×n with m << n, the
goal is to recover `x`. This underpins MRI acceleration, radio astronomy, and spectrum sensing.

## Your task

```python
def recover_sparse(A, y, k):
    """Given measurement matrix A (m,n), observation y (m,), sparsity k,
    return estimated signal x_hat (n,)."""
```

## Scoring

Recovery SNR = 20 log10(||x_true|| / ||x_true - x_hat||), averaged over instances.
Normalized between least-squares baseline and oracle (known-support) ceiling.

## Rules

- Only edit `solution.py`. numpy/scipy only. CPU. Do not read `verification/`.
