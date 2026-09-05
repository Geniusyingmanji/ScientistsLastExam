# ZarankiewiczMatrix — reference results and anchor confidence

Every score below is produced by running code in this directory.

## Reproducing

```
python3 frontier_eval/run_eval.py --candidate solution.py --metrics-out /tmp/baseline.json
python3 frontier_eval/run_eval.py --candidate verification/reference_construction.py --metrics-out /tmp/reference.json
```

## The anchors (primary source, direct fetch)

arXiv:2608.26603 ("Five improved lower bounds for Zarankiewicz numbers z(m,n;3,3)," A. Saurabh)
reports, verbatim from its results table:

| (m,n,3,3) | new lower bound | prior lower bound |
|---|---|---|
| (13,19,3,3) | >= 118 | 114 |
| (14,19,3,3) | >= 126 | 121 |
| (16,18,3,3) | >= 136 | 130 |

This task uses the **new** (most recent, as of this task's construction) lower bound as the
`score = 1.0` witness for each size. These are lower bounds without a matching upper-bound proof
(the companion paper arXiv:2605.01120, "New Bounds for Zarankiewicz Numbers via Reinforced LLM
Evolutionary Search," separately reports the first *exact* Zarankiewicz values ever determined --
`z(11,21,3,3)=116`, `z(11,22,3,3)=121`, `z(12,22,3,3)=132` -- at different (m,n) pairs than the
ones used here), so real headroom exists: a candidate that finds even one more valid 1-entry than
the numbers above at these exact sizes would be a genuine, new, checkable record.

## Baseline — `solution.py`

Fills exactly 2 full columns (every row gets a 1 in each of 2 fixed columns), leaving every other
column all-zero. Structurally impossible to contain a 3x3 all-ones block (only 2 columns are ever
populated), valid by construction with zero search.

| (m,n,3,3) | ones | score |
|---|---|---|
| (13,19,3,3) | 26 | 0.0000 |
| (14,19,3,3) | 28 | 0.0000 |
| (16,18,3,3) | 32 | 0.0000 |

## Reference — `verification/reference_construction.py`

Randomized greedy: visits cells in a random order, tentatively sets each to 1, and reverts only if
that creates a 3x3 all-ones block with two other rows (checked incrementally, not by rechecking
the whole matrix); 40 randomized restarts, keeping the densest valid matrix found.

| (m,n,3,3) | ones | score |
|---|---|---|
| (13,19,3,3) | 110 | 0.9130 |
| (14,19,3,3) | 116 | 0.8980 |
| (16,18,3,3) | 125 | 0.8942 |

`combined_score = 0.9017`. Measured directly by running `verification/reference_construction.py`
through the oracle above -- not asserted. A plain randomized greedy gets remarkably close to these
published records at this matrix size (this is a real, known feature of the K_{3,3}-free extremal
problem: dense near-optimal constructions are comparatively easy to find, and the last few edges
that separate a strong heuristic from the literature's SAT/evolutionary-search-backed record are
the genuinely hard part) -- exactly the gap the cited papers' heavier search methods were built to
close, and exactly the gap a stronger candidate policy here would need to close too.

## What this task is not

This task scores the exact, finite, self-contained combinatorial object (a 0/1 matrix and its
3x3-all-ones-submatrix-freeness). It does not ask for, and does not check, the general asymptotic
theory of the Zarankiewicz problem (the Kővári–Sós–Turán bound, or Füredi's refinements of it) --
that body of theory is a fixed, already-published mathematical context this task assumes, not
something a candidate re-derives or that this oracle re-checks.
