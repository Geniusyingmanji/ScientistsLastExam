# GateSynthesis — synthesize transferable quantum-control pulses

## Scientific background

Quantum optimal control chooses piecewise-constant fields that steer a known Hamiltonian to a
target unitary. At time slice `t`,

```text
H(t) = H_drift + sum_c amplitude[t,c] * H_control[c],
U(t+dt) = exp(-i H(t) dt) U(t).
```

The nominal objective is global-phase-invariant process fidelity

```text
F = |Tr(U_target^dagger U)|^2 / dimension^2.
```

In laboratory hardware, a pulse that is perfect for one calibrated Hamiltonian may fail under
detuning, amplitude miscalibration or finite control bandwidth. Nominal synthesis and robust
control are therefore evaluated separately.

## Your task

Implement a general one- and two-qubit pulse-design policy:

```python
def design_pulse(drift, controls, target, n_steps, dt, amplitude_limit):
    """Return a real array with shape (n_steps, len(controls)).

    drift:    (d,d) Hermitian drift Hamiltonian
    controls: (n_controls,d,d) Hermitian control Hamiltonians
    target:   (d,d) target unitary
    """
```

Every nominal Hamiltonian, target, time step and amplitude bound is supplied. The policy is
called on several one- and two-qubit gates; do not hard-code a CNOT pulse or fixed dimensions.

## Evaluation

`combined_score` is mean nominal development fidelity normalized above free evolution. The
trusted evaluator separately retains:

- `robustness_score`: worst-case detuning, +/-6% amplitude calibration and bandwidth-filtered
  implementation on development targets;
- `heldout_policy_score`: nominal performance on evaluator-only target/Hamiltonian regimes;
- `heldout_robustness_score`: their shifted-hardware performance; and
- pulse RMS, slew and per-variant fidelities.

Only nominal development score controls search. Robustness, held-out performance and all
per-instance values are sealed from proposal prompts and parent selection.

## Rules

- Only edit `solution.py`; keep the `design_pulse` signature.
- Return finite real amplitudes within `[-amplitude_limit, amplitude_limit]`; values are rejected,
  not clipped.
- Deterministic CPU code using the Python standard library, NumPy and SciPy only.
- No network or process creation. Do not read `verification/` or `frontier_eval/`.
