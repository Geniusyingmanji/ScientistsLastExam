# GoldenGateAssemblyFrontier reference record

## 1. Frozen scientific object

The scored object is a complete ordered fragment assembly for each synthetic target. Junctions are
not free words: each is the four-base overlap physically present at one adjacent fragment boundary.
The product must reconstruct the target exactly and contain no recognition site for the selected
enzyme condition.

## 2. Data provenance

Pryor JM et al., *PLOS ONE* 15:e0238592 (2020), DOI
`10.1371/journal.pone.0238592`, CC BY 4.0. Original supplementary workbook SHA-256 values:

- S1 BsaI-HFv2: `320dd058f3ca6372768c7ddfe9cda2a2ea2a076c4f86dd08587d8f295aae1d15`
- S2 BsmBI-v2: `7c444e99e5e4d245461a892e8543a35c84987f93abcee7098de9d9d817237e94`
- S3 Esp3I: `1557e62cfa4f89cd021420b75e145dae2f453ecf26dcca340a8c29008736ea66`
- S4 BbsI-HF: `56143bb445e6d84bba646429402e0948793395269cc5d8ba0e80962c0cac6492`

Each workbook is 257 by 257 including labels, hence a 256 by 256 count matrix. Row labels equal the
reverse complements of the lexicographically ordered column labels. The sparse 24-class extraction
has SHA-256 `f6cf8c7ff9cf73a85e56085092c0cc725b01dbf7f3c77ce9a840c312b4486f50`.
`references/extract_pryor_ligation_counts.py` rebuilds it from prefetched source files and optionally
checks all cells against the fixed OMEGA `160be2f` CSV mirror. The committed replay receipt records
a successful builder replay and explicitly leaves independent source replay pending.

## 3. Measured anchors

| instance | baseline F | reference F | reference enzyme |
|---|---:|---:|---|
| dev_a | 0.357734140583 | 0.981847600177 | BsmBI-v2 |
| dev_b | 0.408787569678 | 0.912298512850 | BbsI-HF |
| dev_c | 0.634301231956 | 0.993554931378 | Esp3I |
| heldout_a | 0.391224288743 | 0.975436592666 | Esp3I |
| heldout_b | 0.538027379186 | 0.970806376807 | BsaI-HFv2 |

The baseline is the public even-spacing construction in `solution.py`. The reference uses only the
public target, enzyme descriptions and count matrices. It takes the better of width-8 and width-32
beam searches after four coordinate-refinement passes.

## 4. Headroom and ablation

A width-128, eight-refinement-pass red team reaches development scores `0.982670`, `1.065777`, and
`0.996324`, for mean `1.014924`. It therefore provides executable score-above-one headroom, but its
held-out scores are `0.986089` and `0.335061`. Wider search is not uniformly better because partial
set fidelity is not a monotone admissible bound; a wide beam can prune a lower-scoring partial set
that later avoids crosstalk. This makes held-out reporting load-bearing.

## 5. Failure and shortcut probes

Exclusive tests pin rejection of empty output, one-fragment output, wrong overlap orientation,
target mutation, out-of-range fragment length, duplicate reverse-complement class and selection of
an enzyme whose recognition site occurs internally. They also prove that adding an unused table
row cannot change the submitted pool's fidelity.

## 6. Interpretation limit

These are predictions under one measured ligation-frequency assay and four enzyme conditions. No
assembly was physically built for the synthetic targets. Promotion requires independent synthetic-
biology review, clean sandbox replay and frozen frontier-model calibration.
