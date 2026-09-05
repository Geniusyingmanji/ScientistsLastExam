# Reference and admission record — MetagenomicMixtureID

## 1. Reference method

`verification/reference_solver.py` is standalone and uses only the public database
and charged sequencer. Three runs (10, 10, 5 depth units) are pooled; a genome is
called present when its unique-marker depth clears a Poisson background by six
standard deviations; abundances normalize the unique masses; refusal fires when the
conserved-marker count exceeds the library expectation by four standard errors — the
signature of reads no unique marker can absorb. It deliberately lacks
expectation-maximization refinement, marker-bias correction and per-run variance
weighting.

## 2. Baseline and normalization

The shipped `solution.py` names three fixed genomes with uniform abundances and
scores exactly `0.000000` after normalization. A truth-informed mixture claim scores
one. Measured on 2026-09-05 the reference reaches `0.9961` development and `0.9952`
robustness with zero false discoveries and full refusal.

## 3. Capability comparisons and ablations

| variant | development | FDR | refusal |
|---|---:|---:|---:|
| full reference | 0.9961 | 0.00 | 1.00 |
| single depth-1 run | 0.9825 | — | — |
| novelty test disabled | 0.5961 | 1.00 | 0.00 |

Presence is cheap; the novelty test carries the refusal axis entirely. Local
debugging numbers, not frozen benchmark evidence.

## 4. Shortcut probes

Fixed-genome claims score zero; a shallow single run already clears presence
thresholds (0.983), so the discriminating axes are abundance precision and the
novelty margin. Passing these probes does not prove the absence of shortcuts.

## 5. Frontier-model calibration

Not run. This task remains `candidate`. A clean Linux model draw, frozen before
exposure, must show that the first proposal does not reach the reference on the
abundance and refusal axes together.

## 6. Construction errors and revisions

Two construction errors were caught locally on 2026-09-05. (i) The read-allocation
probabilities renormalized a full-strength unique block, shrinking the conserved
excess of novel organisms to two sigma — undetectable by the honest test. (ii) The
first baseline ranked the observed markers and scored 0.35; it now ships the
copy-paste fixed claim. Both are pinned in `tests/test_metagenomic_mixture_id.py`.

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
