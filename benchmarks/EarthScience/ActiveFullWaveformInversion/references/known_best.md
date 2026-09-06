# Reference and admission record — ActiveFullWaveformInversion

## 1. Reference method

`verification/reference_solver.py` is standalone and uses only public inputs and charged interfaces. Bounded two-stage smoothed/full-waveform least squares over a 3x5 velocity correction grid.
It is a method witness, not independent high-fidelity verification. The reference now optimizes signed spatial velocity corrections instead of drawing a fixed negative lens. A finer grid, source design and more complete inversion remain open.

## 2. Baseline and normalization

The shipped `solution.py` is the baseline. Tests check valid near-zero development scores.
Optimization references define one through recomputed objective differences; discovery scores
retain their fixed supported-world ceilings and refusal normalization. Changed oracle versions
must not be compared as if their score differences were model improvements.

## 3. Capability comparisons and ablations

Run `python scripts/diagnose_pr9_earth.py --output tmp/hardening/diagnostics.json --sweeps`.
On the current dirty macOS tree, the signed multishot reference scores `0.356670` development
(`mechanism_score=0.571113`) and `0.189769` robustness. Replaying the historical public method on
the current oracle scores `0.249539` development (`mechanism_score=0.499693`) and `0.209638`
robustness. This is a method comparison, not an isolated causal ablation: both the reference and
oracle changed during hardening. A clean Linux per-capability ladder remains unmeasured.

## 4. Shortcut probes

No low-dimensional velocity-family sweep has been run for this task. The only current probe is the
historical smooth-lens method above, which remains well below the new reference but is not a broad
shortcut search. A constant lens, source-only inversion and travel-time-only fit still need an
explicit grid before admission. The numbers above are local diagnostics, not frozen benchmark
evidence.

## 5. Frontier-model calibration

Not run. This task remains `candidate`. A clean Linux model draw, frozen before exposure, must
show that the first proposal does not reach the competent reference. No calibration or external
review is implied by these local code changes. Server-held worlds and independent model review
remain required.

## 6. Construction errors and revisions

2026-09-05 hardening: The reference now optimizes signed spatial velocity corrections instead of drawing a fixed negative lens. A finer grid, source design and more complete inversion remain open.
Standalone references no longer import the hidden evaluator. The task card records the review
lineage, licensing uncertainty and public-world contamination risk. Earlier measurements below
belong to the pre-hardening version and are retained only as history.

## 7. Robustness and reproducibility

Development and heldout metrics remain separate. The new tests cover anchor feasibility,
equivalent-parameter scoring, mass conservation, time refinement, forecast-unit invariance,
instrument error poisoning and malformed submissions as applicable. Formal Linux sandbox
replay, global evidence refresh and independent scientific replication are still pending.
See the task card citations for background; the explicitly declared reduced model is not
certified by those publications.

## Historical pre-hardening record (obsolete scores)

# Known best — ActiveFullWaveformInversion

## Scoring anchor

`verification/reference_solver.py` is the shipped truth-blind multishot smooth-lens witness. The
evaluator recomputes its score from the same public acquisition interface available to a
candidate; it does not read the hidden velocity field.

Measured on 2026-09-05, the shipped baseline scores `0.000000` and the reference scores
`0.249539` on development worlds with `0.209638` robustness. This is a reproducibility anchor,
not a claim of optimality or real-Earth validity. The task still requires model calibration,
server-held worlds, higher-fidelity replication and independent seismology review.

## Difficulty ladder measurement

The same frozen truth-blind witness was evaluated at all three levels on 2026-09-05:

| level | combined | held-out robustness |
|---:|---:|---:|
| 1 | 0.249539 | 0.209638 |
| 2 | 0.101852 | 0.276268 |
| 3 | 0.078013 | 0.000000 |

The primary development score decreases monotonically. The small held-out set is not ordered at
level 2, so these are initial ladder measurements rather than a claim of fully calibrated spacing.

## Reproduce

```bash
python scripts/measure_reference.py \
  --task WavePropagation/ActiveFullWaveformInversion \
  --reference verification/reference_solver.py \
  --entry invert_velocity_model
```
