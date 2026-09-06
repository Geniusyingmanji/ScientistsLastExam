# OrthogonalDNACodewords — build a larger orthogonal DNA word library

## Scientific setting

DNA computing, barcoding and storage all need sets of oligomers that do not
cross-hybridize: fixed GC content, enough pairwise Hamming distance, no long
Watson-Crick-complementary runs when one word slides along the reverse complement of
another (including a word against itself), and capped homopolymer runs. The maximum
library size under such constraints is a classical open combinatorial design problem
(Marathe, Condon & Corn 2001); verification is pure counting, independent of how the
library was built, so the record is open and beating the witness is the point.

## Your task

```python
def build_codeword_library(problem):
    """Return a mapping with exactly one key per family name, each a list of words."""
```

`problem` is a mapping with the keys

```text
families            list of family dicts: family, length, gc_count, min_hamming,
                    max_crossdimer, max_homopolymer, max_library (512)
alphabet            A C G T
scoring             per family score = (size - 2) / (witness - 2), averaged; larger
                    libraries score above one
verification_note   the constraint statement below
```

Two families ship: `dna16` (length 16, GC exactly 8, Hamming ≥ 8, cross-dimer ≤ 6,
homopolymer ≤ 3) and `dna12` (length 12, GC exactly 6, Hamming ≥ 7, cross-dimer ≤ 5,
homopolymer ≤ 3). A library is valid when every word meets its family constraints and
every pair of words (a word with itself included) meets the Hamming and cross-dimer
caps. The cross-dimer count of a pair is the maximum number of Watson-Crick
complementary matches over every shifted alignment of one word against the reverse
complement of the other; zero-overlap alignments do not count. Libraries above 512
words are not verified.

## Evaluation

- `combined_score` is the mean over families of (size − 2)/(witness − 2), where the
  trivial two-word library anchors zero and the frozen truth-blind witness search
  anchors one: dna16 witness 28, dna12 witness 27 (reproduced by the runnable
  reference in `verification/` with restarts=240, seed 0).
- A library that violates any constraint scores zero and invalidates the submission.
- The record is open: any larger valid library scores above one.

This is a combinatorial design benchmark; the constraint family mirrors published DNA
word design, and the frozen witness is not a claimed optimum.

## Oracle and difficulty

Verification is exact integer counting over encoded words (Hamming matrices, all 31
shifted reverse-complement alignments, run lengths). The evaluator holds no hidden
worlds: everything about scoring is public, and the difficulty is entirely in the
search.

## Rules

- Only edit `solution.py`; keep the complete function signature.
- Deterministic Python/NumPy/SciPy/stdlib code only; no network or process creation.
- Do not read `verification/` or `frontier_eval/`.

References: Marathe, Condon & Corn (2001), J. Comput. Biol., doi:`10.1089/10665270152530818`;
Gowri, Sheng & Yin (2024), Nat. Comput. Sci., doi:`10.1038/s43588-024-00646-z`;
King (2003), Electron. J. Combin., url:`https://www.combinatorics.org/ojs/index.php/eljc/article/view/v10i1r33`.

## 关系与区别 / Relationship to nearby tasks

NonlinearCodeRecords and CapSetFrontier build record combinatorial objects verified by
counting; this task is the same shape in the molecular regime, where the verifier
itself encodes Watson-Crick complementarity over all shifted alignments and the
trivial-pair floor anchors zero. No other task in the registry touches DNA word design
or hybridization constraints.

## Admission and reference scope

This package remains **candidate**. The runnable reference is a seeded random-pool
greedy constructor (restarts=240 reproduces the frozen witness; the shipped default of
40 restarts reaches the same sizes on these seeds). Local shortcut diagnostics are
recorded in `references/known_best.md`; they do not replace clean Linux sandbox
replay, independent review of the constraint family against the DNA-word-design
literature, or a frozen frontier-model calibration draw.

## Frontier-Eng overlap comparison (2026-09-06)

无. Nearest catalog entries: HighReliableSimulation; LDPCErrorFloor. Construct a maximal DNA word library satisfying exact GC, homopolymer, Hamming and shifted cross-dimer constraints. FE estimates error probabilities of fixed communication codes; it does not construct biochemical codewords.

See `.research/pr9_frontier_eng_overlap_2026-09-06.md` for the pinned 47-task paper and complete available repository catalog. The requested 95-entry source could not be reconciled with the available 78 rows (84 expanded tasks); source reconciliation and maintainer acceptance remain pending.
