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

## Numerical reproducibility follow-up — 2026-09-07

The recorded score is scoped to a fixed numerical environment, not a promise of
bit-identical optimization across machines or BLAS configurations. On this
Linux x86_64 host, NumPy 1.26.4 / SciPy 1.11.4 with one BLAS thread produced
**0.6891727077822446** in two direct host runs, two direct container runs, and
two actual sandbox runs. All per-instance metrics matched within these runs.
NumPy 2.2.6 / SciPy 1.15.3 with one thread also reproduced the same result twice.
The sandbox explicitly sets OPENBLAS_NUM_THREADS, OMP_NUM_THREADS,
MKL_NUM_THREADS and NUMEXPR_NUM_THREADS to 1 for candidate execution.

With four BLAS threads, two direct runs instead produced development
**0.6891726704740557** and held-out **0.6984321575313412**, compared with
single-thread held-out **0.6780558879651339**. Small numerical changes can alter
the path of the finite-budget nonlinear least-squares reference, especially on
the larger held-out instances. The scoring oracle still evaluates the submitted
coordinates against fixed public constraints; it does not rerun the reference.

The maintainer reported **0.686377** in #37. That exact value has not been
reproduced here (including direct runs with 1, 2, 4, 8, 16 and 32 BLAS threads).
Its precise cause remains unconfirmed without the maintainer's platform,
NumPy/SciPy/BLAS configuration and per-instance metrics. It should not be
attributed to sandboxing itself: direct and sandbox runs agree in the matched
single-thread environment. Freeze numeric environment and thread settings
alongside evidence when exact score comparison is required.

The task regression now repeats both baseline and original reference in fresh
single-thread processes with distinct Python hash seeds and requires exact
agreement. No reference algorithm, scoring formula or calibration endpoint was
changed by this follow-up.

### Controlled initialization experiment

Further diagnosis kept the same public worlds, residual function, scoring
formula, one BLAS thread and 45-evaluation solver budget. Only the MDS
eigendecomposition implementation was substituted in a local probe. Eigenvector
signs were aligned to NumPy's result before optimization:

| Initialization | Development score |
| --- | ---: |
| Original `numpy.linalg.eigh` | 0.6891727077822446 |
| `scipy.linalg.eigh(..., driver="evd")` | 0.6891727077822446 |
| Sign-aligned SciPy `driver="ev"` | 0.6776219265518619 |
| Sign-aligned SciPy `driver="evr"` | 0.7761727694523910 |

After sign alignment, initial coordinates differ by at most 3.56e-14 Angstrom
and initial losses by less than 1e-13. A forward-difference Jacobian diagnostic
using sqrt(machine-epsilon) relative steps differs by up to 6.34e-8. Its six
smallest singular values are about 3e-9 to 2.1e-8, versus a largest value about
0.73–0.78. The objective is invariant under global translations and rotations;
these unconstrained directions make numerical derivatives and finite-budget
steps sensitive to roundoff. Piecewise restraint residuals add nonsmoothness.
This controlled experiment demonstrates how tiny initialization differences can
produce materially different final reference scores. It does not identify the
maintainer's exact environment or reproduce 0.686377. No production solver was
changed; these alternate drivers are diagnostic interventions only.

For exact cross-host diagnosis, record `platform.platform()`, NumPy/SciPy
versions, `numpy.show_config()`, `scipy.show_config()`, BLAS thread environment
variables and the complete per-instance metrics alongside the run.
