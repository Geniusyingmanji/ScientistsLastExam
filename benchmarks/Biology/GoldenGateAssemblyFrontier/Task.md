# GoldenGateAssemblyFrontier — segment a construct using measured ligation fidelity

## Scientific question

Can a deterministic design policy split a synthetic noncoding DNA construct into a fixed number
of manufacturable Golden Gate fragments, choose a compatible Type IIS enzyme, and assign the
actual four-base junctions so that the complete one-pot assembly has high predicted fidelity under
measured ligation crosstalk?

The product is an assembly design, not a free-standing codeword set. Every submitted overhang must
be the four-base overlap of two adjacent submitted fragments, and those fragments must reconstruct
the complete target exactly. A high score predicts performance under the frozen Pryor et al.
ligation-count model; it is not experimental validation of a DNA assembly.

## What to implement

```python
def design_assembly(problem):
    ...
    return {
        "enzyme": "BsaI-HFv2",
        "fragments": ["ACGT...", "TGCA...", ...],
        "overhangs": ["AATG", "CGCT", ...],
    }
```

The mapping must contain exactly those three fields. `fragments` must contain exactly
`fragment_count` nonempty A/C/G/T strings. `overhangs` has one entry for every adjacent fragment
pair, so its length is exactly `fragment_count - 1`; empty and one-fragment submissions are not a
way to avoid the ligation objective.

For each junction `i`:

```text
fragments[i][-4:] == overhangs[i] == fragments[i + 1][:4]
```

The evaluator reconstructs the product by taking the first fragment and appending bases 5 onward
from every later fragment. That string must equal `target_sequence` byte for byte. Fragment length
includes the four-base overlap and must lie inside `fragment_length_bounds`. Junction reverse-
complement classes must be unique and belong to the published measured panel.

The selected enzyme must name one supplied condition. Its recognition sequence and reverse
complement must be absent from the reconstructed product; otherwise the product contains an
internal Type IIS site and is invalid. Different targets deliberately rule out different enzyme
families, so choosing the matrix is part of the design rather than a decorative label.

## Every public problem key

| key | meaning |
|---|---|
| `target_sequence` | complete noncoding A/C/G/T construct to reproduce exactly |
| `fragment_count` | fixed required number of fragments, currently 14--17 |
| `fragment_length_bounds` | inclusive oligo length bounds, including each four-base overlap |
| `overhang_length` | fixed value 4 |
| `canonical_overhangs` | 24 measured reverse-complement classes available in this frozen cell |
| `conditions` | four enzyme conditions, each with its recognition site, sparse integer ligation counts, and PLOS supplement id |
| `fidelity_definition` | machine-readable statement of the published fidelity calculation |
| `artifact_contract` | exact reconstruction and overlap contract |

`ligation_counts` uses keys `ROW>COLUMN`. Missing sparse entries are measured zeros, not missing
data. Rows are 5-prime overhangs and columns are possible ligation partners. The correct partner
of row `s` is `reverse_complement(s)`.

## Measured fidelity oracle

For selected overhangs `{O_1, ..., O_n}`, Pryor et al. define assembly fidelity as
`F = product_i p(O_i)`. For one `O_i`, the numerator of `p` is the observed count for
`O_i -> rc(O_i)` plus the reverse direction. Its denominator sums ligations from both `O_i` and
`rc(O_i)` to every selected overhang and every selected reverse complement. Only overhangs that
actually occur between submitted fragments enter this pool; unused table rows earn no credit.

The exact integer cells are a deterministic sparse extraction from PLOS ONE Tables S1--S4 for
BsaI-HFv2, BsmBI-v2, Esp3I and BbsI-HF. Each original workbook is 256 by 256. The extraction keeps
24 fixed non-palindromic reverse-complement classes and both orientations needed by the formula.
Original URLs, SHA-256 digests, table identifiers, orientation and CC BY attribution are stored in
`data/pryor_ligation_counts_v1.json`.

## Evaluation and continuing improvement

Three development targets and two held-out targets vary construct length, required fragment count,
legal enzyme families and ligation matrix. Each target is generated from a frozen seed and contains
an intentional internal site for one or two enzyme families. Split labels and profile seeds are not
passed to the candidate; the complete target and measured design inputs are.

For each target, the baseline evenly spaces fragments and takes the nearest legal unused junction.
The reference performs two deterministic public-data beam searches followed by coordinate
refinement. If `L = log(F)`, the uncapped instance score is

```text
max(0, (L_candidate - L_baseline) / (L_reference - L_baseline)).
```

Thus the shipped baseline is exactly 0, the truth-blind reference is exactly 1, and a design with
higher measured fidelity can score above 1. `combined_score` averages the three development
targets; `robustness_score` reports the two held-out targets. Feasibility, predicted fidelity,
chosen condition and the number of instances beating the reference remain separate. Invalid
submissions score zero for that target and never receive a small-pool reward.
`development_complete`, `development_valid_count`, `development_invalid_count` and
`development_feasibility_rate` describe the public panel. The parallel `heldout_complete`,
`heldout_valid_count`, `heldout_invalid_count` and `heldout_feasibility_rate` fields are computed
from held-out calls regardless of development validity; failure on one split cannot erase or
upgrade the other split's execution record.

The reference is not claimed optimal. A wider deterministic search scores `1.014924` on the
development mean because it improves one target, while falling to `0.660575` on the two held-out
targets. This is executable headroom and an explicit warning against selecting only on development,
not evidence that the task is frontier-model hard.

## Rules and scope

- Edit only `solution.py`; preserve `design_assembly(problem)`.
- Deterministic CPU Python using the standard library, NumPy or SciPy; no network or processes.
- Do not read `verification/` or `frontier_eval/`.
- Return the complete fragments, not cut coordinates or a list of desirable overhangs.
- Results are predictions from one published in-vitro ligation-count model. Experimental claims
  require physical assembly, transformation, sequence confirmation and independent replication.

Reference: Pryor JM et al., *PLOS ONE* 15, e0238592 (2020),
DOI `10.1371/journal.pone.0238592`, CC BY 4.0.

## Relationship to nearby tasks

`OrthogonalDNACodewords` packs abstract oligonucleotide words under sequence-distance and
hybridization constraints. This task must choose boundaries in a supplied construct, return the
actual overlapping DNA fragments, avoid internal restriction sites, reconstruct the target exactly,
and optimize the measured pairwise ligation matrix for only the junctions used. `RNAInverseDesign`
and `RNAEnsembleDesign` optimize folding of one RNA sequence; neither performs multi-fragment DNA
assembly or uses measured ligation crosstalk.
