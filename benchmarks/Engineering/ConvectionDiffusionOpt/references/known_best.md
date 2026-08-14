# Known best — ConvectionDiffusionOpt

## Anchor

`verification/reference_thermal.py` identifies the transport coefficients and designs the heater
layout, run through the task's own evaluator. It uses only what a candidate receives — the grid,
the parameter bounds, the design specification, the experiment callback and the budget — and never
reads the hidden world.

Reproduce with:

```bash
python scripts/measure_reference.py --task Engineering/ConvectionDiffusionOpt \
    --reference verification/reference_thermal.py --entry design_thermal_policy
```

| | every recorded model proposal | reference |
|---|---:|---:|
| `combined_score` | 0.0000 | **0.7636** |
| `mechanism_score` | 0.0 | **0.9724** |
| `heldout_mechanism_score` | — | 0.8624 |
| `development_supported_claim_coverage` | 0.0 | 1.0 |
| `development_false_discovery_rate` | 0.0 | 0.0 |
| `development_correct_refusal_rate` | 1.0 | 1.0 |
| `development_validation_gap` | — | −0.0089 |

## What the reference does

1. **Solve** — the printed homogeneous equation, discretised as the task prints it: conservative
   diffusion, upwind convection, Dirichlet zero boundary. Verified against the evaluator's own
   solver, to which it is bit-identical on a shared parameter set.
2. **Calibrate** — two experiments, ten of twelve budget units, a single heater at opposite
   corners with twenty-four sensors each. One heater position leaves the velocity poorly
   constrained: the plume it makes samples the flow in one direction only.
3. **Fit** — least squares over the five coefficients, bounded to the published ranges, weighted
   by the noise the callback declares.
4. **Refuse** — reduced chi-square above 4.0. A heterogeneous apparatus cannot be fitted down to
   the sensor noise by any member of the homogeneous family. An apparatus with no heat response
   is caught separately, by its sensors never leaving zero.
5. **Design** — the field is linear in the source strengths, so for any placement the strengths
   are solved exactly by least squares against the target and then clipped to the power limits.
   Only the four positions are searched over.

## The bug worth recording

The reference abstained on every world while its solver was **bit-identical** to the evaluator's:
maximum absolute difference 0.0 on a shared parameter set. The mismatch was in reading the
sensors, not in solving the field. The apparatus samples bilinearly; the reference sampled the
nearest node.

That is close enough to look right and nowhere near close enough to fit. The declared sensor noise
is 6.5e-4 against field values around 0.27, so a one per cent sampling error is a four-sigma
residual, every world exceeded the misspecification threshold, and the reference read as a
correctly cautious retrieval when it was in fact a broken one. A refusal that comes from the
instrument model rather than from the science is indistinguishable from the real thing in the
score, which is why the solver was checked against the evaluator directly rather than inferred
from the score.
