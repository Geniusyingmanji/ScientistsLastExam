# QuantumErrorDecoder — known best values

All values are reproducible by re-running the oracle; none is quoted from a paper.

Measured 2026-08-08 on the benchmark host (Linux, Python 3.8, Stim 1.13.0, PyMatching 2.4.0,
NumPy 1.24.4) on the seeded shot sets declared in `verification/evaluator.py`.

## Anchors

| Regime | shots | detectors | trivial LER | MWPM LER (anchor = 1.0) | anchor failures |
|---|---:|---:|---:|---:|---:|
| `d3_p0.005` | 6000 | 24 | 0.10700 | 0.01750 | 105 |
| `d5_p0.005` | 6000 | 120 | 0.23050 | 0.01333 | 80 |
| `d5_p0.010` | 6000 | 120 | 0.34633 | 0.07867 | 472 |
| `d7_p0.005` | 6000 | 336 | 0.33983 | 0.00667 | 40 |
| `sealed_d5_p0.007` | 4000 | 120 | 0.29375 | 0.03800 | 152 |
| `sealed_d7_p0.008` | 4000 | 336 | 0.43400 | 0.04975 | 199 |

`d` is the code distance (with `d` rounds) and `p` is the uniform circuit-level noise strength.
The anchor is recomputed at evaluation time by PyMatching on the same decomposed detector error
model, so it cannot drift from the scored shot set.

## Calibration ladder

| Decoder | combined_score | robustness_score | wall |
|---|---:|---:|---:|
| Shipped baseline — never predict a flip | **0.0000** | 0.0000 | 0.7 s |
| Truth-blind reference A — numpy/scipy greedy matching | **0.2395** | 0.3380 | 10.4 s |
| Truth-blind reference B — numpy/scipy assignment-reduction matching | **0.3832** | 0.2286 | 4 s |
| GPT-5.6, budget one, best of five draws | **0.7391** | — | — |
| PyMatching 2 minimum-weight perfect matching | **1.0000** (by definition) | 1.0000 | — |
| Published sub-matching decoders | **> 1.0** | — | — |

Both references ship under `verification/` as calibration witnesses; neither is the baseline.

Both references are written under the same numpy/scipy-only constraint imposed on candidates,
and together they confirm the task is solvable within those constraints while leaving the MWPM
anchor out of reach. Reference A scores 0 on `d3_p0.005`: at distance 3 the trivial decoder is
already strong, so a sloppy matcher introduces more logical errors than it removes. Reference B
handles that regime well (0.7778) but loses ground at distance 7, where defect counts grow.

## Difficulty levels

`DIFFICULTY` in `verification/evaluator.py` selects the regime set. Level 1 is the shipped
configuration and reproduces the anchors above exactly; the table below is a measured ladder, and
a level with no entry raises rather than being extrapolated.

| Level | development regimes | shots | anchor failures |
|---:|---|---:|---|
| 1 | `(3,0.005) (5,0.005) (5,0.010) (7,0.005)` | 6000 | 105 / 80 / 472 / 40 |
| 2 | `(5,0.008) (7,0.008) (7,0.012) (9,0.008)` | 2400 | 109 / 137 / 397 / 126 |
| 3 | `(7,0.010) (9,0.010) (9,0.012) (11,0.010)` | 1200 | 114 / 155 / 258 / 187 |

Shot counts hold the decoding workload fixed, not the shot count. Work is shots times the summed
detector count, and detectors grow as `d^2` — 24, 120, 336, 720 and 1320 for `d` = 3, 5, 7, 9, 11
— so keeping the shot count high at a larger distance silently multiplies the load. Holding 4000
shots at level 2 would have made it 1.68x the level-1 workload and level 3 2.58x, converting the
task into the throughput test that forced level 1 down from 20000 shots. The counts above put all
three levels within 3% of each other, and the sealed side within 2%.

Level 2 measured against its own open-loop control, `greedy_rewrite`, eight paired seeds:

| budget | 3 | 5 | 8 | 10 | 12 |
|---|---:|---:|---:|---:|---:|
| gap | +0.0441 | +0.0086 | +0.0849 | +0.0902 | +0.0789 |
| paired wins | 7/1 | 5/3 | 6/2 | 7/1 | 6/2 |
| sign-test p | 0.070 | 0.727 | 0.289 | 0.070 | 0.289 |

Positive at every budget, largest near 10, and significant at none of them — the evidence is the
sign of the whole curve, not any single point. An earlier four-seed read gave +0.1162 at budget 8;
four more seeds pulled it to +0.0849, which is the usual direction for a small-n effect.

A caveat that belongs with those numbers: the feedback arm passed only 37 of 96 submissions here
against 79 of 96 for the open-loop arm, losing 35 to timeouts and 14 to worker exits. The same
asymmetry is present at level 1 — the open-loop arm passes 9 or 10 of 10 while the feedback arm
falls to 2 of 10 — so it is a property of this task under this searcher rather than of the
difficulty level: given feedback, the searcher writes more ambitious decoders and more of them
fail to finish. It does mean the gap mixes decoding quality with surviving the time limit.

All search measurements on this ladder use `greedy_rewrite` with searcher `gpt-5.5` at
`reasoning_effort: low`. The calibration ladder above was measured with GPT-5.6, so the two are
not comparable; run manifests now record the model condition in readable form so this cannot be
ambiguous again.

Sealed regimes move with the level and always sit at noise strengths absent from that level's
development set: level 2 uses `(7,0.009) (9,0.009)` at 1700 shots (141 and 157 anchor failures),
level 3 `(9,0.011) (11,0.011)` at 900 shots (147 and 177).

Difficulty is raised mainly through the noise strength, not the code distance. Below threshold a
larger code drives the logical error rate down exponentially, so distance alone makes the anchor
stop failing often enough to measure: a first attempt that scaled distance at fixed noise left
the level-3 `d=9` regime with 9 anchor failures, the same statistical failure that had already
disqualified a `d=9` sealed regime. Each level therefore pushes `p` toward the circuit-level
threshold near 1% while the code grows, which keeps the anchor measurable and simultaneously
weakens the graph approximation that matching depends on.

## Sizing: statistics against the timeout

Shot counts are pinned between two constraints.

*Statistics.* The score is a ratio of logarithms, so it is only as stable as the anchor's
failure count. The counts above (40–472 failures) hold score noise near or below 4%. A larger
sealed distance was tried and rejected: at `d=9, p=0.004` the anchor fails on about 0.2% of
shots, so any affordable shot count leaves single-digit failure counts and measures nothing.

*Compute.* The candidate's own decoding dominates the wall clock, and the whole evaluation must
fit the harness default 300 s timeout. This is not hypothetical — it was the first thing that
went wrong in practice. At an earlier 20000-shot sizing, GPT-5.6 produced a competent decoder
(shortest paths plus exact small-syndrome T-joins) that **scored nothing because it could not
finish**, which measures decoder throughput rather than decoding quality. At the current sizing
the reference finishes in 10.4 s, leaving roughly a 28× margin for a slower candidate.

## Is the anchor reachable inside the candidate constraints?

A fairness question about this task's own scoring: candidates may use only the standard library,
NumPy and SciPy, while the anchor is a specialist C++ matching library. If 1.0 were unreachable
under those constraints, the normalization would be misleading.

Two independent numpy/scipy references were written to probe this. A greedy nearest-defect
matcher reaches 0.2395. Reducing each shot's minimum-weight T-join to a balanced assignment
problem and solving it with `scipy.optimize.linear_sum_assignment` reaches 0.3832, including
0.7778 on `d3_p0.005`. Both degrade with code distance, where defect counts grow and the
assignment reduction stops being an exact perfect matching.

The gap to 1.0 is therefore an implementation-quality gap, not an impossibility: PyMatching
implements sparse blossom, and a correct general-graph minimum-weight perfect matching is
implementable in pure Python — substantially harder than either reference, and comfortably
inside the timeout headroom, but real work. Supporting evidence that the anchor is approachable:
a single GPT-5.6 budget-one draw already reaches **0.7391**, above both references.

## Cross-version note

Stim's seeded sampling stream is not stable across versions: the same seed yields slightly
different shots, moving both the trivial rate and the anchor by roughly 1–2% of score. Because
the score is a ratio computed from the *same* run, a candidate's score stays self-consistent
within one toolchain and the drift does not bias comparisons; it does mean
`verification/requirements.txt` pins the versions, and any upgrade must re-record this file.

## Why the score is uncapped

Minimum-weight perfect matching is the community reference, not the optimum. It decomposes the
circuit-level error model into a graph and therefore discards X/Z correlations that circuit-level
depolarizing noise actually produces. Decoders reported to beat matching on surface-code memory
include correlated/hierarchical matching, belief propagation with ordered-statistics
post-processing, tensor-network decoders, and learned decoders — Bausch et al.,
DOI `10.1038/s41586-024-08148-8`, report a recurrent-transformer decoder below both matching
and correlated matching on Google's distance-3 and distance-5 experimental data.

Reaching 1.0 is reproduction of a well-documented baseline. Only scores above 1.0 represent work
at the frontier, and any such result must be re-confirmed on a fresh unseeded shot set before it
is described as a decoding improvement.

## Reproduce

```bash
python -m sle eval --allow-uncertified --task QuantumErrorCorrection/QuantumErrorDecoder
```
