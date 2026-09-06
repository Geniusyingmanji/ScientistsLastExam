# ProteinDistanceGeometry: scoring evidence — 2026-09-06

## Scientific endpoints

Zero is the straight-line baseline. One is zero loss on all public distance,
bond, angle, excluded-volume and chirality constraints. Quality is
`q=1/(1+loss/0.2)` and score is `(q-q_baseline)/(1-q_baseline)`, clipped to [0,1].
The loss scale 0.2 resolves residual violations near a good conformation; it does
not depend on the candidate or reference loss. A feasible zero-loss procedural
witness exists and is tested independently of the reference. The reference
remains MDS plus 45 least-squares evaluations; `references/headroom_probe.py`
uses 120 evaluations with otherwise identical public inputs.

## Reproduction and measurements

The legal `solution.py` baseline scores **0.000000**, valid=1. The input-only
comparison reference is `references/reference.py`.
Reproduce using:

```sh
python -m sle eval --allow-uncertified --task StructuralBiology/ProteinDistanceGeometry \
  --candidate benchmarks/Biology/ProteinDistanceGeometry/references/reference.py --timeout 300
```

Baseline and reference were validated through the Linux candidate sandbox on
implementation commit `3b62c02`; baseline score was exactly zero and both were valid.

| Solver | Development normalized score | heldout_score | Valid |
| --- | ---: | ---: | ---: |
| Original reference | 0.68917271 | 0.67805589 | 1 |
| Public-input headroom probe | 0.85186119 | 0.82711863 | 1 |

The discovery held-out column is raw scientific quality, not the normalized
development scale. Optimization held-out scores use the same normalization as
development. All reference algorithms are unchanged by this calibration.
Pre-calibration score measurements do not describe this revision.

## Designed runtime budget

The maintainer observed **96 seconds** for one full reference evaluation. The
task wrapper explicitly declares **EVAL_TIMEOUT_S=300**, matching its metadata,
task card and the normal `sle eval --timeout 300` command. This is the total
candidate wall-clock deadline across all four worlds; repository worker CPU
limits also apply. The outer subprocess allowance adds 120 seconds for trusted
work and cleanup. On this Linux x86_64 host, direct reference evaluation took
23.95 seconds; the formal sandbox reference took 32.63 seconds, and the
120-evaluation probe took 67.15 seconds. The default task-local wrapper also
returned valid=1 and score 0.68917271. Hardware and BLAS
settings affect runtime; these measurements are not a portable speed guarantee.
The evaluator no longer runs a second reference optimization to construct the
anchor, avoiding unnecessary overhead.

## Limits and provenance

These original procedural worlds are repository-visible; held-out means excluded
from search feedback, not server-secret. No external datasets or code are
redistributed. Model simplifications and nearest-task overlap are in `Task.md`.
Precision/headroom measurements do not establish expert difficulty: strong
classical comparisons, frontier draws, long-horizon search and external domain
review remain pending. The task stays **candidate**.

Scientific sources: doi:10.1023/A:1008380219900.
