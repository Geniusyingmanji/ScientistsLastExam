# SpinSystemInference — known best values

All values are recomputed by the oracle at evaluation time; none is quoted from a paper.

Measured 2026-08-12 on the benchmark host (Linux, Python 3.8, nmrsim 0.6.0).

## Worlds at the shipped level

Five development worlds of three coupled spins, shifts spread over 260 Hz with at least 45 Hz
between neighbours, couplings drawn from 3 to 12 Hz with about a third of pairs left genuinely
uncoupled. Every third world makes two spins magnetically equivalent.

| World | peaks | determined |
|---|---:|---|
| `w0_n3` | 12 | yes |
| `w1_n3` | 12 | yes |
| `w2_n3_deg` | 8 | no — spins 0 and 1 equivalent |
| `w3_n3` | 12 | yes |
| `w4_n3` | 12 | yes |

The degenerate world is visibly different — 8 peaks instead of 12 — so a candidate can detect it
rather than having to guess. What it cannot do is recover the hidden 0–1 coupling, which has no
effect on the spectrum. That coupling is excluded from mechanism scoring instead of counted as a
miss, and the only correct answer for that world is to abstain.

## Calibration ladder

| Method | mechanism | false-discovery rate | correct refusal | wall |
|---|---:|---:|---:|---:|
| Shipped baseline — n strongest peaks, no couplings | **0.0417** | 0.00 | 0.00 | <1 s |
| Truth-blind reference — least-squares fit of the nmrsim forward model | **0.5833** | **0.25** | 0.00 | 137 s |

The reference is the point of this table, and not because of its mechanism score. It recovers a
respectable 0.58 of the structure **while claiming a coupling that does not exist in a quarter of
the pairs that have none, and while never recognising the world it cannot solve**. A single
combined number would have reported 0.58 and hidden both.

That is the case T7 argued for in this repository and CausaLab documents in the literature: the
objective score and the correctness of the discovery are different quantities. Here they are kept
apart by construction — `combined_score` carries mechanism alone, and the other two axes sit beside
it in the metrics.

## What a good answer has to do

Three things at once, and the axes are designed so that trading one for another is visible:

- recover shifts and couplings (mechanism)
- leave uncoupled pairs uncoupled (false discovery)
- abstain on the magnetically equivalent world and nowhere else (refusal)

Claiming every pair is coupled raises mechanism slightly and destroys the false-discovery rate.
Abstaining everywhere scores zero mechanism, because an abstention on a determined world counts as
zero for that world.

## Cost

The reference fitter takes 137 s across five worlds, dominated by forward simulations. A candidate
doing the same has roughly the same budget inside the 300 s harness timeout, so an approach that
simulates thousands of trial systems will not finish. nmrsim prints two debug lines to stdout on
every simulation; the evaluator and the reference both suppress it, and a candidate that does not
will produce megabytes of output — one calibration run generated 2.8 MB before this was fixed.

## Reproduce

```bash
python -m frontier_science eval --allow-uncertified --task Spectroscopy/SpinSystemInference
```
