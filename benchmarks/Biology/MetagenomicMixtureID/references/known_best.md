# Reference and admission record — MetagenomicMixtureID

## 1. Reference method

`verification/reference_solver.py` is standalone and uses only the public database
and charged sequencer. Four runs (5, 5, 5, 5 depth units) are pooled; a genome is
called present when its unique-marker depth clears a Poisson background; abundance
per genome is the median over its markers, which absorbs the hidden lognormal
efficiency bias (sums would systematically overweight efficient markers); refusal
fires when the conserved-marker count exceeds the library expectation by three
standard errors — cross-mapping conserves the unique total, so no inflation
correction is needed. It deliberately lacks expectation-maximization refinement
and per-run variance weighting.

## 2. Baseline and normalization

The shipped `solution.py` names three fixed genomes with uniform abundances and
scores exactly `0.000000` after normalization. A truth-informed mixture claim
scores one. After the 2026-09-06 read-economy tightening (1200 reads per unit,
four-run budget, marker-efficiency jitter, cross-mapping, six-to-sixteen-percent
novel shares) the reference reaches `0.8969` development and `0.9594` robustness
with zero false discoveries and full refusal.

## 3. Capability comparisons and ablations

| variant | development | FDR | refusal |
|---|---:|---:|---:|
| full reference (4 x depth 5) | 0.8969 | 0.00 | 1.00 |
| single depth-5 run | 0.8877 | 0.00 | 1.00 |
| single depth-5 run, pre-hardening statistics | 0.9825 | — | — |

The hardening moved 1000-fold read mass out of the shallow probe's reach: presence
is still easy, abundance under hidden marker bias is not (a five-genome uneven
world scores 0.56 for the reference). Local debugging numbers, not frozen benchmark
evidence.

## 4. Shortcut probes

Fixed-genome claims score zero; a shallow single run already clears presence
thresholds (0.983), so the discriminating axes are abundance precision and the
novelty margin. Passing these probes does not prove the absence of shortcuts.

## 5. Frontier-model calibration

Not run. This task remains `candidate`. A clean Linux model draw, frozen before
exposure, must show that the first proposal does not reach the reference on the
abundance and refusal axes together.

## 6. Construction errors and revisions

Four construction errors were caught locally, the last two in the 2026-09-06
difficulty rework. (i) The read-allocation probabilities renormalized a
full-strength unique block, shrinking the conserved excess of novel organisms to
two sigma. (ii) The first baseline ranked the observed markers and scored 0.35.
(iii) A cross-mapping block accidentally doubled every unique count, making novel
worlds look library-heavy. (iv) A 1.05 inflation correction on the unique total
was applied although cross-mapping conserves the total — supported worlds were
refused as novel; a difficulty audit also found a single shallow run scoring 0.98
against the 0.996 reference, so the statistics were tightened to 1200 reads per
unit, 8-18 percent novel shares, hidden efficiency bias, cross-mapping and a
four-run budget. All pinned in `tests/test_round4_new_tasks.py`.

## 7. Robustness and reproducibility

Development and held-out mixtures use fresh seeds; repeated depth runs draw
independent multinomials by construction. Determinism was checked by comparing two
full evaluation dictionaries. Formal Linux sandbox replay, global evidence refresh
and independent replication are pending.

## Reproduce

```bash
python scripts/measure_reference.py \
  --task Metagenomics/MetagenomicMixtureID \
  --reference verification/reference_solver.py \
  --entry identify_mixture
```
