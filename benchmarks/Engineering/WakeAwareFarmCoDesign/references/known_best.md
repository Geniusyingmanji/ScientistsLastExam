# Reference and admission record — WakeAwareFarmCoDesign

## 1. Reference method

`verification/reference.py` is standalone and uses only the public problem mapping.
It screens twelve deterministic feasible layout jitters, performs one bounded
`120/60/30 m` layout/yaw alternation (at most two coordinate passes per scale),
and finishes with a second direction-wise yaw sweep. Direction count is read from
the problem; the old hard-coded twelve-direction constant was removed.

The score-one envelope recomputes 600 layout draws and additional multiscale
alternations. It explicitly contains the runnable reference's exact seed, yaw grid,
layout scales and pass limits, so a different greedy path cannot accidentally make
the witness stronger than its anchor. Component normalization also includes regular
and staggered layout controls with optimized yaw. The envelope is a reproducible
search record, not a published optimum.

## 2. Baseline and normalization

The September 12 revision reports layout-only GWh gain and incremental yaw-control
GWh gain separately, then uses their geometric mean. This directly repairs the
maintainer's finding that 85% of the old decision variables (yaw) contributed only
0.003391 while a zero-yaw spreading heuristic obtained 0.509220.

Clean local in-process measurement on macOS / Python 3.12:

| entry | development | heldout | robustness |
|---|---:|---:|---:|
| regular zero-yaw baseline | 0.000000 | 0.000000 | 0.000000 |
| runnable joint reference | **0.782836** | **0.782388** | 0.499350 / 0.708390 |

The reference evaluation, including all six freshly computed anchors, took 25.92 s.
Scores are rounded to six decimals before reporting to remove pairwise-summation
noise. The wrapper timeout is 600 s; Linux sandbox timing remains pending.

## 3. Capability comparisons and ablations

The complete reference's development means are `layout_score=0.714964` and
`yaw_control_score=0.864917`. Every individual instance has positive yaw GWh gain
(4.53–7.51 GWh on development and 4.98–7.10 GWh held out).

| ablation | layout axis | yaw axis | combined |
|---|---|---|---:|
| regular layout, zero yaw | baseline | absent | 0.000000 |
| improved/reference layout, zero yaw | positive | absent | 0.000000 |
| regular layout, coordinate-refined yaw | absent | positive | 0.000000 |
| complete alternating reference | 0.714964 mean | 0.864917 mean | 0.782836 |

The ablations are properties of the scoring graph, pinned by tests. They show that
both advertised capabilities are active; they do not establish that the joint
optimization problem resists a new low-dimensional family.

## 4. Shortcut probes

The September 8 maintainer probes against the obsolete one-axis score remain part
of the record:

| historical family | old development score |
|---|---:|
| larger-budget copy of the same hill climb | 1.169086 |
| repulsion/spreading layout, zero yaw | 0.509220 |
| yaw only on the baseline grid | 0.003391 |

Those results invalidated the old claim that the remaining gap was necessarily
joint search. Under the revised score, every zero-yaw family has combined score
zero while its layout axis remains visible, and every unchanged-baseline layout has
layout score zero while its yaw axis remains visible. This fixes the semantic bug;
it is not presented as a universal shortcut bound. A new probe that optimizes both
axes and a frozen first-proposal model draw remain admission blockers.

## 5. Frontier-model calibration

Not run. The task remains `candidate`. Local reference/shortcut measurements do
not substitute for `batch_evolve.py --run-role calibration`, server-held wind roses,
or the rule that a first proposal must remain below the competent reference.

## 6. Construction errors and revisions

- 2026-09-08 review: scaling the old algorithm reached 1.169086; a simple zero-yaw
  spreading family reached 0.509220; yaw-only value was 0.003391. The old reference,
  headroom and “genuine joint search” claims were withdrawn.
- 2026-09-12 repair: removed the unsupported `0.20*load` proxy, inactive 3.6 MW cap
  and artificial 0.18 velocity floor. The yaw displacement now uses the public
  momentum-style `0.5*Ct*cos(gamma)^2*sin(gamma)*dx` term, and the approximately
  `cos^1.9` own-power loss is retained. Both are still reduced-model choices pending
  FLORIS reproduction.
- The score now requires positive layout and yaw increments. The reference alternates
  both capabilities, and the anchor includes its exact path plus component controls.
- `CompositeLaminateStacking` was withdrawn from PR #21 after a full pair-exchange +
  ILS reference scored 0.993447 even after rescaling loads so both advertised failure
  modes were active. Basic neighborhood search saturated that task within budget.

## 7. Robustness and reproducibility

The widened-expansion (`k=0.074`) and `+7 deg` direction-shift evaluation remains
separate from development scoring. The current reference reports 0.499350 on the
development robustness tier and 0.708390 held out. One development instance has a
negative shifted relative score; this is retained rather than clipped or averaged
into `combined_score`.

Reproduce the local reference measurement with:

```sh
python - <<'PY'
import importlib.util
from pathlib import Path
root = Path("benchmarks/Engineering/WakeAwareFarmCoDesign")
def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
evaluator = load(root/"verification/evaluator.py", "wake_evaluator")
reference = load(root/"verification/reference.py", "wake_reference")
print(evaluator.evaluate(reference.design_wind_farm))
PY
```

The evaluator and standalone reference still require clean Linux sandbox replay,
pinned FLORIS comparison, independent wind-energy review and deterministic repeat
confirmation on the final committed tree.
