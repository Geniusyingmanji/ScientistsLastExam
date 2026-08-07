# QuantumErrorDecoder — known best values

Measured 2026-08-07 with Stim 1.16.0, PyMatching 2, NumPy 1.26.4 on the seeded shot sets
declared in `verification/evaluator.py`. All values are reproducible by re-running the oracle;
none is quoted from a paper.

## Anchors per development regime

| Regime | shots | trivial LER | MWPM LER (anchor = score 1.0) |
|---|---:|---:|---:|
| `d3_p0.005` | 20000 | 0.10335 | 0.01790 |
| `d5_p0.005` | 20000 | 0.22925 | 0.01435 |
| `d5_p0.010` | 20000 | 0.35815 | 0.08565 |
| `d7_p0.005` | 20000 | 0.34235 | 0.00905 |

`d` is the code distance (with `d` rounds) and `p` is the uniform circuit-level noise strength.
The anchor is recomputed at evaluation time by PyMatching on the same decomposed detector error
model, so it cannot drift from the scored shot set.

## Calibration ladder

| Decoder | combined_score | robustness_score |
|---|---:|---:|
| Shipped baseline — never predict a flip | **0.0000** | 0.0000 |
| Truth-blind reference — numpy/scipy greedy matching over the error graph | **0.2652** | 0.3657 |
| PyMatching 2 minimum-weight perfect matching | **1.0000** (by definition) | 1.0000 |
| Published sub-matching decoders | **> 1.0** | — |

The truth-blind reference is a deliberately simple greedy matching decoder written under the
same numpy/scipy-only constraint imposed on candidates. It confirms the task is solvable within
those constraints while leaving the MWPM anchor well out of reach. It scores 0 on `d3_p0.005`
because at distance 3 the trivial decoder is already strong and a sloppy matching decoder
introduces more logical errors than it removes.

## Why the score is uncapped

Minimum-weight perfect matching is the community reference, not the optimum. It decomposes the
circuit-level error model into a graph and therefore discards X/Z correlations that circuit-level
depolarizing noise actually produces. Decoders reported to beat matching on surface-code memory
include correlated/hierarchical matching, belief propagation with ordered-statistics
post-processing, tensor-network decoders, and learned decoders — Bausch et al.,
DOI `10.1038/s41586-024-08148-8`, report a recurrent-transformer decoder below both matching
and correlated matching on Google's distance-3 and distance-5 experimental data.

Reaching 1.0 is therefore reproduction of a well-documented 20-year-old baseline. Only scores
above 1.0 represent work at the frontier, and any such result must be re-confirmed on a fresh
unseeded shot set before it is described as a decoding improvement.

## Reproduce

```bash
python -m frontier_science eval --allow-uncertified --task QuantumErrorCorrection/QuantumErrorDecoder
```

Full evaluation including the two sealed regimes takes about 55 s on one CPU core.
