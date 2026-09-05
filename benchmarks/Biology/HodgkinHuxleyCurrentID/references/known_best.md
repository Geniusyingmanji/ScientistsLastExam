# Reference and admission record — HodgkinHuxleyCurrentID

## 1. Reference method

`verification/reference_solver.py` is standalone: the public gating equations are
restated in closed form (at clamped voltage each gating variable relaxes
exponentially from its holding steady state), four fixed steps (-40, -20, 0, 30 mV
for 20 ms) are fitted by bounded least squares over the eight parameters from five
starts including the classic squid-axon values, and refusal fires when the best
weighted residual per degree of freedom exceeds six — extra currents leave
structural misfit no three-current row absorbs. It deliberately lacks adaptive
protocol design, trace reweighting and gating-clamp decomposition.

## 2. Baseline and normalization

The shipped `solution.py` charges one protocol and guesses mid-range parameters:
`0.000000`. Submitting the true parameter row scores one (sealed prediction exact).
Measured on 2026-09-05 the reference reaches `0.7176` development and `0.5940`
robustness with zero false discoveries and full refusal.

## 3. Capability comparisons and ablations

| variant | development | refusal |
|---|---:|---:|
| full reference | 0.7176 | 1.00 |
| single classic start | ≈0.55 | 1.00 |
| no misfit gate | ≈0.55 | 0.00 |

Multistart rescues local minima; the misfit gate carries the refusal axis. Local
debugging numbers, not frozen benchmark evidence.

## 4. Shortcut probes

Mid-range guesses score zero; the parameter axis (0.565) resists lazy fits because
conductances, reversals and shifts trade off. No low-dimensional family reaches the
reference.

## 5. Frontier-model calibration

Not run. This task remains `candidate`. A clean Linux model draw, frozen before
exposure, must show that the first proposal does not reach the reference on the
parameter and refusal axes together.

## 6. Construction errors and revisions

Five construction errors were caught locally on 2026-09-05. (i) The public alpha
forms divide zero by zero at shifted 25 mV; a stable series form replaced them. (ii)
The first closed-form gating started relaxation from the step steady state, making
every trace constant. (iii) A math.exp call on an array crashed A-type worlds. (iv)
The rectifying extra current was four percent of peak — below the misfit gate — and
was strengthened to a quadratic leak the family cannot absorb. (v) The reference
imported the hidden evaluator; it now restates the public equations. All pinned in
`tests/test_hodgkin_huxley_current_id.py`.

## 7. Robustness and reproducibility

Development and held-out parameters use fresh seeds; closed-form gating is exact, so
determinism holds to machine arithmetic. Formal Linux sandbox replay, global
evidence refresh and independent replication are pending.

## Reproduce

```bash
python scripts/measure_reference.py \
  --task Electrophysiology/HodgkinHuxleyCurrentID \
  --reference verification/reference_solver.py \
  --entry recover_channel_parameters
```
