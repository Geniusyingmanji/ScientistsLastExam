# ActiveNoiseSpectroscopy — a Lorentzian spectrum is not a noise mechanism

## Scientific question

A dephasing qubit is exposed either to one discrete fluctuator, to Gaussian noise with the same
power spectral density, or to an environment outside the one-fluctuator model. Design pulse
filters and allocate a finite number of shots to determine whether a **single non-Gaussian
fluctuator is supported**, estimate its physical parameters, and decline when it is not supported
or not distinguishable at this budget.

This is not a label-only classification. A claimed mechanism contains three continuous
parameters, and the evaluator propagates that mechanism through pulse sequences not used by the
measurement interface. A correct name with poor parameters therefore predicts the held-out
complex coherence poorly.

## Why a power spectrum is insufficient

The two in-family comparison processes are deliberately matched at second order. Both have

```text
C2(tau) = variance * exp(-switching_rate * |tau|)
S(omega) = 2 * variance * switching_rate / (switching_rate**2 + omega**2).
```

One process is Gaussian Ornstein--Uhlenbeck noise. The other is a stationary two-state Markov
fluctuator. Write `p` for its high-state probability and

```text
gap = sqrt(variance / (p * (1-p)))
b_low = -p * gap
b_high = (1-p) * gap
k_low_to_high = switching_rate * p
k_high_to_low = switching_rate * (1-p).
```

These choices give zero mean and exactly the covariance and Lorentzian PSD above. When `p != 0.5`,
the fluctuator has a nonzero third cumulant and creates an imaginary part of the qubit coherence.
When `p = 0.5`, that phase vanishes even though the process is still non-Gaussian: distinguishing
it from its Gaussian PSD match requires the even higher cumulants visible across more than one
filter. Thus a rule that merely looks for a phase is deliberately incomplete.

For a sequence of instantaneous pi pulses, the switching function `y(t)` starts at `+1` and flips
sign at every pulse. Its filter function is

```text
F(omega) = integral_0^T y(t) exp(i omega t) dt.
```

For Gaussian noise the coherence is real and

```text
W_G = exp[-1/2 integral_0^T integral_0^T y(t)y(s) C2(t-s) dt ds].
```

This is the time-domain form of the usual `S(omega) |F(omega)|^2` filter-function integral. For
the two-state process, all cumulants are retained by the exact tilted master equation

```text
d v / dt = [Q^T - i y(t) diag(b_low, b_high)] v,
W_RTN = [1, 1] v(T),       v(0) = [1-p, p].
```

The trusted oracle solves this two-dimensional propagation by a matrix exponential on each pulse
interval. It does not approximate the non-Gaussian process by a fitted label or by Gaussian noise.

## What you implement

```python
def discover_noise(problem, measure):
    ...
```

You choose controls from the complete public pulse panel and allocate shots. Return either

```python
{
    "abstain": False,
    "noise_model": "single_telegraph",
    "switching_rate_per_us": ...,
    "noise_variance_rad2_per_us2": ...,
    "high_state_probability": ...,
    "confidence": ...,
}
```

or

```python
{"abstain": True, "confidence": ...}
```

### `problem` — every public key

| key | meaning |
|---|---|
| `control_catalog` | the complete legal panel of eight Ramsey, echo, offset-echo and CPMG controls; each row gives `sequence_id`, `duration_us`, and all `pulse_times_us` |
| `shot_budget` | total X-plus and Y-plus Bernoulli shots; a query costs twice `shots_per_quadrature` |
| `min_shots_per_quadrature` | minimum legal allocation to each quadrature in one query |
| `max_shots_per_quadrature` | maximum legal allocation to each quadrature in one query |
| `parameter_bounds` | inclusive bounds for the three returned physical parameters |
| `switching_function` | the sign convention for `y(t)` |
| `measurement_model` | how complex coherence becomes X/Y binomial counts |
| `supported_model` | the single-fluctuator claim that may be returned |
| `abstain_when` | Gaussian, multi-fluctuator, or finite-budget ambiguous cases |

### `measure(sequence_id, shots_per_quadrature)`

`sequence_id` must name one row in the complete public control panel. A legal query returns

```python
{
    "sequence_id": ...,
    "shots_per_quadrature": n,
    "x_plus_counts": ...,
    "y_plus_counts": ...,
    "shot_cost": 2*n,
}
```

with

```text
P(X+) = (1 + Re W)/2
P(Y+) = (1 + Im W)/2.
```

The total shot budget is 24,000. Calls are a single auditable random stream per world, control and
quadrature: splitting one allocation into several calls neither repeats old shots nor creates an
uncharged redraw. Every protocol error and every overspend invalidates that world even if your
code catches the exception.

## Evaluation

- `combined_score = clip((sum of supported parameter-recovery scores - unsupported false-claim
  count) / supported-world count, 0, 1)`. Correct refusal only avoids a false-claim penalty; it
  never adds positive score, so declining every world is exactly zero. On supported worlds the
  parameter-recovery term scores all three parameters continuously.
- `heldout_prediction_score` recomputes the complex coherence of the submitted mechanism on three
  evaluator-only controls. It is reported separately from mechanism recovery.
- false-discovery rate, unsupported false-positive rate, correct refusal, unwarranted refusal, attempted discovery, confidence
  calibration, and shot use are separate diagnostics and are never averaged into the discovery
  score. Correctly saying “not a discovery” on a Gaussian null is a necessary true negative, not
  a new scientific discovery.
- Any non-abstaining `single_telegraph` claim on an unsupported world is a false discovery.
  Parameter error on a supported single-fluctuator world instead lowers continuous mechanism
  recovery; it is not relabelled as a structural false discovery. The evaluator publishes
  `false_claim_count`, total non-abstaining claim count, supported-world count, and
  unsupported-world count. FDR is false claims divided by all non-abstaining mechanism claims;
  unsupported false-positive rate is false claims divided by unsupported worlds.
- development and held-out sets each contain asymmetric and symmetric single fluctuators,
  PSD-matched Gaussian nulls, two-fluctuator model mismatch, and a weak single fluctuator that no
  legal full-budget control separates from its Gaussian match at the frozen KL gate.

The identifiability screen has two independent gates: family separation from the matched Gaussian,
and rank three of the local complex-coherence Jacobian for rate, variance, and occupancy. Because
the legal control panel is finite and complete, the evaluator computes the exact largest total KL
divergence available under the shot budget: Bernoulli KL adds across shots, so every shot pair is
assigned to the panel member with largest X-plus plus Y-plus KL. The first gate still does not by
itself prove that all three parameters are identifiable.

For supported construction worlds, the best free-rate/free-variance Gaussian fit over the whole
panel must also leave a minimum complex-response residual. This is a construction screen, not a
theorem that every Gaussian nuisance model is statistically separated. For an ambiguous world,
the evaluator needs only exhibit one same-rate/same-variance Gaussian alternative with sufficiently
small total KL; Pinsker's inequality then bounds the variation distance available to any adaptive
allocation over the complete panel.

## Relationships and differences

- `QuantumDynamics/HamiltonianLearning` infers a closed-system spin Hamiltonian from fixed
  magnetization traces. This task designs open-system pulse filters and distinguishes stochastic
  processes that share a PSD.
- `Physics/HiddenCouplingNetwork` reconstructs direct couplings from driven steady states. It has
  no shot allocation, filter function, higher cumulant, or held-out coherence artifact.
- `Gravitation/PTAHellingsDowns` chooses among spatial correlation kernels. This task fits a
  continuous dynamical noise mechanism and includes an exact Gaussian-versus-non-Gaussian
  second-order match.
- It does not overlap the engineering optimization tasks in Frontier-Eng: the artifact is a noise
  model inferred by quantum sensing, not a controller, device layout, or software system.

## Limits and status

This is a deterministic reduced-order candidate benchmark, not evidence about a real qubit. It
uses instantaneous pulses, classical pure dephasing, a single stationary fluctuator family, a
finite eight-control panel, and synthetic binomial measurements. It does not claim optimal
continuous-control discovery. Device-level claims require finite-pulse simulation, native-noise data, independent
experimental review, and prospective confirmation.

## Rules

- Only edit `solution.py`; keep `discover_noise(problem, measure)`.
- Deterministic CPU code using the Python standard library, NumPy, and SciPy only.
- Do not read `verification/` or `frontier_eval/`; do not use network or process creation.
- `sle.contract_lint` is importable and free to use for output-shape checks.

## Sources

- Sung et al., “Non-Gaussian noise spectroscopy with a superconducting qubit sensor,” *Nature
  Communications* 10, 3715 (2019), DOI `10.1038/s41467-019-11699-4`, arXiv `1903.01043`.
- Norris, Paz-Silva and Viola, “Qubit noise spectroscopy for non-Gaussian dephasing
  environments,” *Physical Review Letters* 116, 150503 (2016), DOI
  `10.1103/PhysRevLett.116.150503`.
