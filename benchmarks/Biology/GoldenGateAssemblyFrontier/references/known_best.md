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
beam searches after four coordinate-refinement passes. Score is uncapped remaining-gap log progress
toward log fidelity `-0.001` (~99.9% predicted F); that witness lands near combined score `0.54`,
not at one.

## 4. Headroom and ablation

A width-128, eight-refinement-pass search is not uniformly better than the width-32 witness
(partial-set fidelity is not a monotone admissible bound). The executable headroom program takes,
per instance, the better of the two; it strictly improves development combined score above the
witness. Wider search is not uniformly better because a wide beam can prune a lower-scoring
partial set that later avoids crosstalk. This makes held-out reporting load-bearing.

## 5. Failure and shortcut probes

Exclusive tests pin rejection of empty output, one-fragment output, wrong overlap orientation,
target mutation, out-of-range fragment length, duplicate reverse-complement class and selection of
an enzyme whose recognition site occurs internally. They also prove that adding an unused table
row cannot change the submitted pool's fidelity.

## 6. Interpretation limit

These are predictions under one measured ligation-frequency assay and four enzyme conditions. No
assembly was physically built for the synthetic targets. Promotion requires independent synthetic-
biology review, clean sandbox replay and frozen frontier-model calibration.

## 7. Model draws and construction errors

No frozen frontier-model calibration has been run; builder model identity was not recorded.
Lineage is incomplete_legacy and this task is excluded from RECORDED_LINEAGE.
The former evaluator recomputed its reference search in each fresh evaluation process, even
for invalid submissions. Anchors are now constants guarded by explicit full recomputation.
The former Task.md omitted the development-mean definition; that omission is repaired.

## 8. Maintainer shortcut measurements

Source: PR #18 comment by Geniusyingmanji, 2026-09-08, head f3e553d.
Greedy: infeasible, 0.000000. Beam width 2: 0.078686 development.
Beam width 8 without refinement: 0.429900 development / 0.130161 heldout.
Reference: 0.536922 / 0.501698. Refinement adds about 0.11 development and 0.37 heldout.
Superseded scale: a wider search previously measured 1.014924 / 0.660575; those values
are not measurements on the current scale. These are algorithm measurements,
not model draws or proof of difficulty. The score-one target is an engineering target, not a
published experimental record.


## 9. Current scientific admission hold

The [maintainer review of 2026-09-09](https://github.com/Geniusyingmanji/ScientistsLastExam/pull/18#issuecomment-5594779111)
reports exhaustive ceilings 0.685658 development / 0.512899 heldout for the 24-class panel.
A public-only ten-start local search scores 0.675263 in 8.6 seconds in the sandbox;
60 starts reach both ceilings in 75.5 seconds in-process. These are attributed maintainer
measurements, not independent model calibration. They supersede any implication that the
current score-one target is reachable or that substantial long-horizon headroom is established.
The maintainer explicitly reserved the choice among expanding the panel, clipping to an
attainable anchor, and introducing a position-dependent objective. This repair changes only
search-visible feasibility and neighbor descriptions; that scientific decision remains open.

## September 12 current-head replay

The standalone `references/beam_probe.py` uses only the public problem, beam width 64
and two coordinate-refinement passes. Full Linux sandbox scores are **0.573364500287
development / 0.501698019821 heldout**, versus reference **0.536921991354 /
0.501698019821**. These are the current reconstruction's measurements, not a verbatim
reproduction of an unavailable historical candidate. The strong declared shortcut guard
fails; enumeration, score-one attainability and useful search headroom remain unresolved.
No scoring anchor or objective was changed without the maintainer's scientific decision.

`instances_beating_reference` now counts valid rows whose actual log fidelity exceeds
the reference log fidelity. Previously it incorrectly counted scores above one, although
one denotes a separate engineering target. A real search regression covers a candidate
beating the reference while scoring below one. Heldout diagnostics remain search-hidden.

Reproduce the probe with `uv run python -m sle eval --task GoldenGateAssemblyFrontier
--allow-uncertified --candidate benchmarks/Biology/GoldenGateAssemblyFrontier/references/beam_probe.py
--timeout 60` (one shell line).

## Full-panel redesign audit: expansion alone rejected

A September 12 builder experiment tested the proposed panel expansion before changing the
frozen oracle. The four original 256-by-256 workbooks passed their existing SHA-256,
dimension and orientation checks. There are **120 non-palindromic reverse-complement
classes**, not 256 distinct such classes: 16 of the 256 four-mers are self-complementary,
and the remaining 240 orientations form 120 pairs. The existing 24-class extraction
keeps every fifth class.

Using all 120 classes, the same five targets, fragment counts and length constraints,
and the existing public-input-only beam search at width 8 with four refinement passes:

| instance | log predicted fidelity | reaches mathematical F=1 bound |
|---|---:|---|
| dev_a | 0.0 | yes |
| dev_b | -0.001548587920235 | no |
| dev_c | 0.0 | yes |
| heldout_a | -0.010777227853401 | no |
| heldout_b | -0.015522928327063 | no |

Each returned full fragment assembly was independently passed through the existing
artifact validator against the expanded public problem. The first builder timing was
1.25–2.07 seconds per width-8 search. These are in-process diagnostic timings, not
sandbox timings or fixed performance thresholds. Since every factor in the fidelity
product is at most one, the two exact zero log fidelities prove global optimality for
those two expanded instances. No global optimum is claimed for the other three.
Measured zero crosstalk counts permit predicted F=1; they do not establish perfect
physical assembly or absence of unobserved ligation events.

Reproduce with the original source workbooks (the extraction script documents their
names and URLs):

```bash
uv run python benchmarks/Biology/GoldenGateAssemblyFrontier/references/audit_full_panel.py \
  --xlsx-dir /path/to/workbooks --output /tmp/full-panel-audit.json
```

The output includes source and implementation hashes, complete assembly witnesses,
validation results, raw objective values and timings. This is a host-side redesign
experiment, **not a new frozen task, sandbox qualification, or model draw**. It does
not use the old normalized scores or claim that the old 24-class ceilings apply to
the expanded panel.

**Decision: reject panel expansion alone as a repair.** It increases nominal subset
count while making two development instances exactly saturate with a small existing
search. Keep this PR Draft and the frozen task unchanged. Reopening scientific
admission requires a separately justified redesign: obtain independently supported
measurements or manufacturing constraints that create meaningful design tradeoffs,
then demonstrate strong-search headroom and matched-budget feedback benefit on both
splits before committing a new oracle. Do not append an arbitrary position penalty,
choose larger fragment counts merely to defeat this probe, weaken the reference, or
rescale these saturated predictions. If no such scientific basis is available, retire
this task submission while retaining its source-replay and assembly-validation work.
