# CirclePacking — known best values

Pack N non-overlapping unit circles inside the smallest possible square. For most N there is no
closed-form optimum; the listed values are the smallest known square sides from computational
search, and a tighter packing is a genuine result. The score is therefore uncapped.

## Anchors

| N | grid baseline side | best known side | source |
|---:|---:|---:|---|
| 7 | 6.0000 | 5.7320508076 | proven optimal, `4 + sqrt(3)`; Packomania csq7, r = 0.174457630187 |
| 10 | 8.0000 | 6.7474415232 | Packomania csq10, r = 0.148204322565 |
| 13 | 8.0000 | 7.4630478289 | proven optimal (Peikert 1991, per Friedman's survey); Packomania csq13, r = 0.133993513499 |

Each side is re-derived, not transcribed: Packomania states the radius `r` of N equal circles in
a **unit** square, and scaling those circles to radius 1 scales the square to side `1/r`. The
coordinate files are `http://www.packomania.com/csq/txt/csq{N}.txt`; the first data row's fourth
column is `r`.

## The N=13 anchor was wrong, and what it cost

This table used to list 7.6274 for N=13. That number is not in the source: `1/0.133993513499`
is 7.4630478289, and 7.6274 corresponds to no radius Packomania has ever listed for 13 circles.
Nothing in the repository could catch it, because a literal is not checkable by running anything
- which is why `tests/test_external_anchors_are_checkable.py` keeps the set of literal anchors
small and this file carries the re-derivation.

Against the wrong anchor, one model proposal reached a verified valid side of 7.4632466 and
scored 1.4406 - read at the time as a new world record from a single proposal, and the task was
reclassified as saturated on the strength of it. Against the real anchor the same packing scores
0.9995: an excellent result sitting just short of a proven optimum, which is what it always was.

Score per instance is the fraction of the baseline-to-record gap closed:

```text
progress = (baseline_side − achieved_side) / (baseline_side − best_known_side)
score    = max(0, progress)          # no upper clamp
```

Reaching the record scores exactly 1.0. Worked example at N=7, where the grid baseline is 6.0
and the record is 5.7320508076: a side of 5.8500 scores 0.5601, the record itself scores
1.0000, and 5.6500 scores 1.3063. At N=7 and N=13 the record is a proven optimum, so a score
above 1.0 there is a refutation of a proof and should be treated as a bug until shown otherwise;
at N=10 it would be a genuine new record.

## Why uncapped

Packomania is a live record table that has been improved repeatedly over decades. Clipping at
1.0 would make "matched the record" and "beat the record" indistinguishable, which is exactly
the distinction this benchmark exists to measure. N=7 is proven optimal and cannot be beaten;
N=10 and N=13 are conjectured and can.

## Sizing caveat

These instance sizes are small and settled. Measured on this repository: OpenEvolve reaches
0.9906 by its second oracle call and 0.9999 by the twentieth, and plain single-incumbent greedy
reaches 0.999989 by its sixth — the two searchers are indistinguishable because the task is easy
at these N, not because they are equally strong. Larger N, where the Packomania values are still
contested, is required before this task can discriminate between searchers.

## Reproduce

```bash
python -m sle eval --task Optimization/CirclePacking
```
