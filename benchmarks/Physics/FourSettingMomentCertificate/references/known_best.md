# FourSettingMomentCertificate — measured values

Every SOS number here is produced by `verification/`. Classical and two-qubit anchors
are quoted from the papers cited in `references/anchors.json` and rechecked as noted.

## Reference — `verification/reference_certificate.py`

Truth-blind: it reads the public instance (functional, pool, budget) and returns
squares. It does not call an SDP solver.

Hand exact SOS: two CHSH 2×2 replacements using four frozen BB extras
`(B1 B2, B2 B1, B0 B3, B3 B0)`. Expanded bound **7/2**. Legal at every budget in this
task (`k ≥ 4`).

The reference is capability-complete for a small exact SOS and deliberately not at the
two-qubit floor 0.25. On the logarithmic scale it scores about 0.46. Score one is hung
at bound 3.0, which the 36-point pairing grid does not prove. Headroom below 3.5 is
which extra moments to spend the rest of the Hamming-weight budget on.

## Baseline — `solution.py`

| | k=4 | k=8 | k=12 | mean |
|---|---:|---:|---:|---:|
| triangle bound | 4 | 4 | 4 | |
| triangle score | 0 | 0 | 0 | **0** |
| catalog SOS | 3.5 | 3.5 | 3.5 | |
| catalog log-score | 0.461 | 0.461 | 0.461 | **0.461** |

The baseline is the triangle inequality written as squares over the NPA-1 basis. It
uses no extra moments.

## Difficulty ladder

| ablation | bound | combined_score | what was removed |
|---|---:|---:|---|
| triangle, no extras | 4.00 | 0.000 | all extra-moment SOS |
| one CHSH block (two BB extras) | 3.75 | **0.222** | the second block |
| two CHSH blocks (catalog) | 3.50 | 0.461 | — |
| below two-qubit 0.25 | — | 0 (reported) | not rewarded |

Dropping either CHSH block of the catalog raises the bound by 0.25 and drops the
log-score from 0.461 to 0.222. The extras are doing the work.

## Shortcut probe

A 36-point grid over the three perfect matchings of four A settings, the three of
four B settings, zip vs cross pairing, and two sign patterns. Two of 36 geometries
are valid and both score **0.461** (bound 3.5); they are the catalog pairing and its
sign-matched twin. The other 34 fail the operator identity (score 0).

The grid reaches the reference and does not reach the score-one bound 3.0. Beating
3.5 requires a different SOS, not another pairing from this grid. Recalling I3322
NPA numbers is worth nothing: the functional is different.

## Model draws

Not run. No frontier calibration on a clean tree. A searcher that enumerates the
36-point CHSH-block grid would hit 0.461, not 1.0. The untouched part of the scale
is below 3.5, toward the wave-1 target 3.0.

## Construction errors

The gated design was an I3322 NPA-4 dual occupying the same identity as
`BellBoundCertificate`. It was replaced by `I_4422^{13}` and a frozen Hamming-weight
pool. A free word budget was refused because that is the sibling task. Floats were
refused rather than rounded; accepting them would have turned the oracle into an SDP
call. A bound below 0.25 is reported and zeroed, not rewarded.

## Robustness

Twelve malformed submissions — empty mapping, `None`, empty basis, empty squares,
negative weight, unreduced `A0 A0`, duplicate words, five extras on a k=4 budget,
zero denominator, a boolean posing as a weight, mismatched vector length, and a
raising callable — all score 0, and none raises out of the evaluator. A length-2
AB correlator outside the same-party pool is rejected.
