# QuantumErrorDecoder — known best values

All values are reproducible by re-running the oracle; none is quoted from a paper.

## Anchors per development regime

Measured on the seeded shot sets declared in `verification/evaluator.py`, under the two
toolchains this task has been run on:

| Regime | shots | trivial LER | MWPM LER (anchor = 1.0) | trivial LER | MWPM LER |
|---|---:|---:|---:|---:|---:|
| | | *stim 1.16.0 / macOS* | | *stim 1.13.0 / Linux py3.8* | |
| `d3_p0.005` | 20000 | 0.10335 | 0.01790 | 0.10345 | 0.01730 |
| `d5_p0.005` | 20000 | 0.22925 | 0.01435 | 0.22945 | 0.01465 |
| `d5_p0.010` | 20000 | 0.35815 | 0.08565 | 0.35875 | 0.08385 |
| `d7_p0.005` | 20000 | 0.34235 | 0.00905 | 0.34200 | 0.00950 |

**Stim's seeded sampling stream is not stable across versions.** The same seed yields slightly
different shots, which moves both the trivial rate and the MWPM anchor. Because the score is a
ratio of logarithms computed from the *same* run, a candidate's score is self-consistent within
any one toolchain, but cross-version comparisons carry roughly 1-2% of score noise. Both the
solver and the anchor move together, so this does not bias the comparison; it does mean
`verification/requirements.txt` pins the versions and any upgrade must re-record this table.

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
