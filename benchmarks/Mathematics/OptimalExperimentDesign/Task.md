# OptimalExperimentDesign — allocate measurements for D-optimal information

## Scientific background

Experimental design chooses *where* to measure before collecting costly observations. For a
local linearization with sensitivity row `f(x)`, an allocation with information matrix

```text
M = (1/k) sum_t f(x_t) f(x_t)^T
```

is D-optimal when it maximizes `log det(M)`, equivalently minimizing the volume of the
parameter-confidence ellipsoid. Repeated experiment indices are allowed and represent replicate
measurements. This criterion is used in system identification, kinetics, spectroscopy and
sensor placement.

## Your task

Implement a general allocation policy:

```python
def select_designs(candidate_points, feature_matrix, n_measurements):
    """Return exactly n_measurements integer row indices.

    candidate_points: (n_candidates,) physical design coordinates
    feature_matrix:   (n_candidates, n_parameters) local sensitivities
    n_measurements:   total measurement/replicate budget
    """
```

The program is evaluated on procedurally constructed polynomial, oscillatory, exponential-decay
and saturation-model sensitivity matrices. Candidate-grid size, parameter count and budget vary
between calls. Do not assume one fixed family or hard-code indices.

## Evaluation

Each allocation is compared with a certified near-optimal fractional reference satisfying the
Kiefer–Wolfowitz sensitivity condition to relative tolerance `1e-4`. `combined_score` is normalized development
D-efficiency. Shifted families, larger parameterizations and changed physical scales are
evaluated separately as an evaluator-only `robustness_score`; they never enter proposal prompts
or parent selection.

The baseline spends all measurements on the first grid rows. It is legal but poorly
conditioned. A useful method should use the supplied sensitivity matrix, retain full rank, and
decide when replicates improve determinant rather than merely spreading points uniformly.
The evaluator may apply an invertible whitening transform to parameter columns for numerical
stability; D-optimal allocations and D-efficiency are invariant to this reparameterization.

## Rules

- Only edit `solution.py`; keep the `select_designs` signature.
- Return a one-dimensional array of finite integer indices in range. Repetitions are allowed.
- Deterministic CPU code using the Python standard library, NumPy and SciPy only.
- No network or process creation. Do not read `verification/` or `frontier_eval/`.
