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
| Truth-blind reference — numpy/scipy greedy matching over the error graph | **0.2395** | 0.3380 | 10.4 s |
| PyMatching 2 minimum-weight perfect matching | **1.0000** (by definition) | 1.0000 | — |
| Published sub-matching decoders | **> 1.0** | — | — |

The reference is a deliberately simple greedy matching decoder written under the same
numpy/scipy-only constraint imposed on candidates. It confirms the task is solvable within
those constraints while leaving the MWPM anchor well out of reach. It scores 0 on `d3_p0.005`
because at distance 3 the trivial decoder is already strong and a sloppy matching decoder
introduces more logical errors than it removes.

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
python -m frontier_science eval --allow-uncertified --task QuantumErrorCorrection/QuantumErrorDecoder
```
