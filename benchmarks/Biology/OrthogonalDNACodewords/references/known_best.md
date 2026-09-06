# Reference and admission record — OrthogonalDNACodewords

## 1. Reference method

`verification/reference_solver.py` is a seeded random-pool greedy constructor: each
restart draws a 40,000-word pool with the family's GC content and homopolymer cap,
shuffles it deterministically, and greedily accepts compatible words in vectorized
blocks; the best restart is kept. With `restarts=240, seed=0` it reaches 28 words
(dna16) and 27 (dna12). The frozen witness (32/29) additionally requires the
removal-repair search described in section 3, which the shipped reference
deliberately omits. The witness is a search witness, not a claimed
optimum; published DNA-word-design constructions under comparable constraints may
exceed it, and beating the witness scores above one by design.

## 2. Baseline and normalization

The shipped `solution.py` returns the first compatible pair per family — the trivial
two-word library anyone can write down — and scores exactly `0.000000`. The witness
sizes anchor one; the span is (witness − 2) per family.

## 3. Capability comparisons and ablations

| variant | dna16 | dna12 | score |
|---|---:|---:|---:|
| frozen witness (greedy + repair) | 32 | 29 | 1.000 |
| shipped reference (greedy only, 240 restarts) | 28 | 27 | 0.896 |
| 5 restarts, different seed | 23 | 25 | 0.776 |

The removal-repair phase carries the last step to the witness; greedy alone
plateaus at 28. These are local debugging numbers, not frozen benchmark evidence.

## 4. Shortcut probes

The artifact is the object itself, so low-dimensional parameterized families do not
apply. Probes ran on construction shortcuts: a different-seed five-restart greedy
reaches 0.864 (below the witness), and any constraint violation scores zero regardless
of size. All remaining untested construction methods are admission risks; passing
these probes does not prove the absence of shortcuts.

## 5. Frontier-model calibration

Not run. This task remains `candidate`. A clean Linux model draw, frozen before
exposure, must show that the first proposal does not reach the frozen witness.
Independent review of the constraint family against the DNA-word-design literature
remains required.

## 6. Construction errors and revisions

Three construction errors were caught locally on 2026-09-05 before any model saw the
task. (i) The verifier's Hamming matrix counted the diagonal, so every library —
including the witness — failed its own check. (ii) The first baseline imported a helper
from `verification/`, violating black-box safety; the baseline is now self-contained.
(iii) The constructor never checked a word against its own reverse complement, so
self-dimerizing words entered the witness; the self-dimer check now runs even against
an empty library. All three are pinned in `tests/test_orthogonal_dna_codewords.py`.

## 7. Robustness and reproducibility

Both families verify with the same exact counting code the witness must pass;
determinism was checked by comparing two full evaluation dictionaries. Formal Linux
sandbox replay, global evidence refresh and independent replication are pending. See
the task card citations for background; the frozen witness is not certified as optimal
by those publications.

## Reproduce

```bash
python scripts/measure_reference.py \
  --task SyntheticBiology/OrthogonalDNACodewords \
  --reference verification/reference_solver.py \
  --entry build_codeword_library
```
