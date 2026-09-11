# Reference and admission record — MassFragmentationTree

## 1. Reference method

`verification/reference_solver.py` is standalone and uses only public inputs and the
charged instrument. Four energy scans (12/24/38/54) plus one precursor-window zoom
(2.6 Da wide); CHNO mass decomposition of every surviving peak; first-vs-last energy
contrast filtering of flat background; duplicate-peak merging at a third of the mass
tolerance; greedy loss-library attachment from heaviest fragment down; refusal when the
precursor ion never survives or two precursor ions with different isotope ratios share
the window. It is a method witness, not independent verification; it deliberately lacks
global tree optimization, additional zooms for isobaric resolution, and any use of
quantitative intensity models.

## 2. Baseline and normalization

The shipped `solution.py` charges one low-energy scan and claims the intact precursor as
the entire tree. Measured on 2026-09-05 the baseline scores exactly `0.000000`
development and `0.000000` robustness; the always-abstain construction makes full
abstention exactly zero by design. Submitting the exact hidden tree scores one.

## 3. Capability comparisons and ablations

Local oracle-direct ablations of the reference, measured 2026-09-05:

| variant | development | robustness | FDR | refusal |
|---|---:|---:|---:|---:|
| full reference | 0.5645 | 0.5248 | 0.00 | 1.00 |
| never refuse | 0.1645 | 0.0000 | 1.00 | 0.00 |
| two energies only (12, 54) | 0.5310 | 0.4462 | 0.00 | 1.00 |
| root-only edge attachment | 0.5061 | 0.5266 | 0.00 | 1.00 |
| blind zoom (empty window) | 0.3645 | 0.1915 | 0.50 | 0.50 |

Every capability contributes; the energies and intermediate-parent attachment matter
mainly through edge F1 (0.360 full vs 0.271 two-energy vs 0.243 root-only). These are
local debugging numbers, not frozen benchmark evidence.

## 4. Shortcut probes

- The review's three-scan strategy that submits all observed peaks and every
  loss-compatible peak pair is now invalid: several fragments receive multiple parents,
  so the output is not a fragmentation tree. A repaired single-parent version measured
  on 2026-09-12 reaches **0.389747/0.456859** development/robustness, versus the unchanged
  **0.564467/0.524831** reference. Its node F1 is 0.588 and edge F1 is 0.192. The hardened
  worlds include 8–12 flat background tracks deliberately placed at public-library loss
  gaps, so local mass compatibility no longer substitutes for energy-contrast filtering.
- Top-k peaks at one fixed energy, all attached to the precursor through the best
  library loss: best of 57 grid points (k in 4..40 step 2, energies 20/35/50) is
  **0.049** (k=8, E=50).
- Two-energy (E1 in 12..30, E2 in 40..60) root-attachment family: best of 16 points is
  **0.104** (24, 48).

The earlier probes also sit far below the reference; no tested low-dimensional family
exceeds it after hardening.
All remaining untested families are admission risks; passing these probes does not prove
the absence of shortcuts.

## 5. Frontier-model calibration

Not run. This task remains `candidate`. A clean Linux model draw, frozen before exposure,
must show that the first proposal does not reach the competent reference. Server-held
molecules and independent mass-spectrometry review remain required.

## 6. Construction errors and revisions

Three construction errors were caught locally on 2026-09-05 before any model saw the
task. (i) The zoom path passed the main tree explicitly and resurrected the precursor
ion in in-source worlds, making the refusal world undetectable — fixed by threading
`root_alive` explicitly and pinned by a test. (ii) The background filter compared
max-vs-min flatness and killed saturated fragments, inverting the energy ablation so that
fewer energies scored higher — replaced with first-vs-last contrast. (iii) Per-energy
mass noise split the same fragment into duplicate nodes at distinct rounded keys, which
hurt four-energy precision — fixed by merging observations within a third of the
tolerance. All three are pinned in `tests/test_mass_fragmentation_tree.py`.

A 2026-09-08 adversarial review found that repeating each true edge twenty times
produced edge F1 1.904762 and mechanism 1.452381. Canonical duplicate edges are now
rejected, while the matching routine independently counts each true edge at most
once. Outputs are bounded at 256 nodes and 4096 edges before matching. The normal
reference remains 0.564467 development; this retest is local debugging only.
The public query contract now correctly says that repeated calls draw fresh noise,
while replaying the same ordered calls is deterministic. Invalid outputs are no
longer reported as scientific discovery attempts.

A 2026-09-12 review then found that an unconstrained all-pairs graph over raw peaks
exceeded the reference. Validation now enforces heavier-to-lighter, loss-consistent edges
and at most one parent per fragment. The oracle also emits structured flat decoys whose
mass gaps match public losses; the intended multi-energy background filter removes them,
while the repaired low-dimensional tree shortcut remains below the reference on both
splits. These invariants are pinned in `tests/test_mass_fragmentation_tree.py`.

## 7. Robustness and reproducibility

Development and held-out metrics stay separate; the held-out set uses fresh molecules,
trees, backgrounds and failure regimes. Determinism was checked by comparing two full
evaluation dictionaries. Formal Linux sandbox replay, global evidence refresh and
independent replication are pending. See the task card citations for background; the
explicitly declared reduced-order cascade is not certified by those publications.

## Reproduce

```bash
python scripts/measure_reference.py \
  --task Spectroscopy/MassFragmentationTree \
  --reference verification/reference_solver.py \
  --entry recover_fragmentation_tree
```
