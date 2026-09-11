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

**2026-09-08 correction:** the oracle and reference now consistently use absolute
membrane voltages, converting to the original rate coordinate with `u = V + 65 - s`
at the holding and step potentials. Independent equilibrium values at -65 mV are
pinned in `tests/test_pr9_chem_bio_contracts.py`. This follows the absolute-potential
convention in the [NEURON Book, Chapter 9](https://www.neuron.yale.edu/ftp/ted/book/revisions/chap9indexedref.pdf).
Oracle-direct debugging after correction gives baseline 0, reference development
0.640364, heldout 0.828679, development FDR zero and refusal one. These are local
debugging observations, not clean Linux calibration or independent certification.
The public budget is now four units, exactly the tier used by the reference.

The shipped `solution.py` charges one protocol and guesses mid-range parameters:
`0.000000`. Submitting the true parameter row scores one (sealed prediction exact).

## 3. Capability comparisons and ablations

Measured on the 2026-09-12 hardened head:

| variant | development | robustness | refusal |
|---|---:|---:|---:|
| full four-step reference | 0.640364 | 0.828679 | 1.00 |
| first two steps only | 0.066144 | 0.157297 | 0.00 |
| first step only | 0.000000 | 0.000000 | 0.00 |
| no misfit refusal | 0.240364 | 0.162013 | 0.00 |

The complete budget and misfit gate are both load-bearing. Local debugging numbers,
not frozen benchmark evidence.

## 4. Shortcut probes

Mid-range guesses score zero. A reviewer-reported sweep of 325 low-dimensional
strategies on the voltage-corrected worlds topped out at `0.053671/0.000000`, far below
the four-step reference. Reducing the public budget from eight to four can only remove
strategies from that family; it cannot improve their score.

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
`tests/test_pr9_chem_bio_contracts.py`.

The 2026-09-08 review found that the original alpha/beta equations were expressed
relative to rest, while holding and reversal potentials were absolute. The missing
65 mV conversion changed both physical currents and reference difficulty; old
measurements cannot be reused. The A-type transient also previously started from
the depolarized inactivation equilibrium and used a slow 220 ms decay, suppressing
the very transient it was intended to model. It now starts from holding-state
availability and relaxes over 20 ms, with a regression test for the resulting
transient. These are explicitly synthetic A-type-like currents; renewed
experimental-design and model-mismatch sensitivity measurements remain necessary.
The 2026-09-12 review additionally found that the reference could silently double its
own four-step acquisition while candidates were offered eight steps. The public budget
is now four, so the normalization reference is the best measured method at its own tier.

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
