# InterventionalSCM — recover hidden causal mechanisms by experimentation

## Scientific background

Observational association does not generally identify causal direction. Controlled
interventions can break Markov-equivalent explanations and reveal how perturbations propagate
through a system. This task models a small autonomous laboratory: each hidden world is a
linear, acyclic structural causal model (SCM), but its graph, topological order, coefficients,
and noise scales are unknown.

The variables obey

```text
X_j = sum_i B[i,j] X_i + epsilon_j,
```

where `B[i,j] != 0` means `X_i -> X_j`. One hidden world is a null system with no causal
edges. A good scientist must therefore be able to report that no supported mechanism exists,
not always invent a graph.

## Your task

Edit `solution.py` and implement:

```python
def discover_mechanism(n_variables, observe, intervene, budget_units):
    """Return a dict containing:
      adjacency:   (n_variables, n_variables) directed 0/1 array
      coefficients:(n_variables, n_variables) coefficient array
      confidence:  optional scalar in [0,1]
      abstain:     optional bool; True means return the null mechanism

    observe(n_samples) -> observational samples with shape (n_samples, n_variables)
    intervene(variable, value, n_samples) -> samples from do(X_variable=value)
    """
```

Each callback consumes experimental budget in blocks of 32 samples. Observation batches are
limited to 256 samples, intervention batches to 128 samples, and intervention values to
`[-3,3]`. Exceeding `budget_units` invalidates that hidden-world result even if your code catches
the callback error.

## Evaluation

The primary `combined_score` measures recovery of the directed graph and its structural
coefficients across procedurally generated hidden worlds. The evaluator separately records:

- `mechanism_score`: directed-edge and coefficient recovery;
- `intervention_prediction_score`: predictions under sealed interventions never exposed to
  the search program;
- experimental calls and budget units used; and
- correct null-world abstention.

These quantities are deliberately not collapsed into a single “science score.” The benchmark
optimization target is mechanism recovery; sealed intervention prediction is an independent
validity diagnostic.

## Rules

- Only edit `solution.py`; keep the `discover_mechanism` signature.
- Deterministic CPU code using the Python standard library, NumPy, and SciPy only.
- No network or process creation. Do not read `verification/` or `frontier_eval/`.
- Do not assume that variable index is a causal/topological order.

