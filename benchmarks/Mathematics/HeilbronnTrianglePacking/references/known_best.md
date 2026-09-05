# HeilbronnTrianglePacking — reference results and anchor confidence

Every score below is produced by running code in this directory.

## Reproducing

```
python3 frontier_eval/run_eval.py --candidate solution.py --metrics-out /tmp/baseline.json
python3 frontier_eval/run_eval.py --candidate verification/reference_construction.py --metrics-out /tmp/reference.json
```

## The anchors (maintained record table, independently re-fetched)

Erich's Packing Center (`https://erich-friedman.github.io/packing/heilbronn/`) maintains
the record table for the unit-square Heilbronn triangle problem for every `n` up to 16,
independently re-fetched and confirmed on 2026-09-06:

| n | min-area | status |
|---|---|---|
| 8 | (sqrt(13)-1)/36 = 0.07237642431844414 | proven optimal (L. Dehbi, Z. Zeng, 2022) |
| 10 | approx 0.04654 | best-known only, not proven optimal |
| 11 | 1/27 = 0.037037037037037035 | best-known only, not proven optimal |

`n=10` and `n=11` are genuinely open: a candidate that finds a valid point set with a
larger minimum triangle area at either size would be a real, new, checkable record. `n=8`
is proven optimal (an explicit certified configuration plus an exhaustive/certified proof
that no configuration does better) -- **no valid point set can score above 1.0 at n=8**,
disclosed here rather than hidden.

For scientific motivation (not a task anchor, since it concerns different regions):
"AlphaEvolve: A coding agent for scientific and algorithmic discovery," arXiv:2506.13131,
reports new 2026 records for Heilbronn variants in an equilateral triangle (11 points,
area >= 0.0365) and general convex regions (13 points >= 0.0309, 14 points >= 0.0278) --
but explicitly did not improve on the classic unit-square records this task uses.

## Baseline — `solution.py`

Places the `n` points at the vertices of a regular `n`-gon inscribed in the unit square's
largest inscribed circle (motivated by Goldberg's conjecture, which holds only for `n=6`).

| n | min-area | score |
|---|---|---|
| 8 | 0.05177669529663685 | 0.0000 |
| 10 | 0.02806424853622407 | 0.0000 |
| 11 | 0.02145620494458457 | 0.0000 |

## Reference — `verification/reference_construction.py`

Randomized coordinate hill-climbing: 25 restarts from random point sets, each running
15,000 single-point perturbation steps with an annealed step size, keeping only moves that
strictly increase the minimum triangle area.

| n | min-area | score |
|---|---|---|
| 8 | 0.05880463869361249 | 0.3412 |
| 10 | 0.03602903364872838 | 0.4311 |
| 11 | 0.03101732325860153 | 0.6136 |

`combined_score = 0.4620`. Measured directly by running
`verification/reference_construction.py` through the oracle above (runtime approx 18s for
all three sizes together). Plain hill-climbing improves substantially on the regular-
polygon baseline but falls well short of every published record here, most at `n=11` --
exactly the gap the certified-optimal and global-optimization methods behind the cited
records were built to close, and the gap a stronger search policy here would need to
close too.

## What this task is not

This task scores the exact, finite, self-contained geometric object (a finite point set
and the minimum area among all `C(n,3)` triangles it forms, computed by the direct
shoelace/cross-product formula). It does not ask for, and does not check, the certified
global-optimization or computer-assisted-proof methods used to *prove* the `n=8` and `n=9`
records optimal -- that machinery is separate, already-published mathematics this task
does not re-derive or re-check.
