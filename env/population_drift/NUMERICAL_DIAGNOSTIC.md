# Separate precision diagnostic of two retained discrepancies

The original independent numerical review retains **two failed full-distribution
comparisons and an A-partial verdict**. A separately frozen diagnostic now
supports a narrower explanation: on those two saved cases, production results
agree closely with a higher-precision calculation, while the saved DOP853
reference distributions retain their discrepancies. No original result was
regraded, and no production simulation was rerun.

## Frozen comparison and results

The diagnostic deliberately selected the two earlier failures. It used the same
saved binary64 parameters, initial conditions, and all seven original sample
times. Independently written Decimal code enumerated replacement events and
evaluated uniformization at 50 and 80 decimal digits. Each positive-time result
started from the original initial distribution. The method shares the original
author reference's uniformization family; it is not a third unrelated algorithm.

Maximum absolute differences over the complete saved distribution arrays:

| Retained case | 50 vs 80 digits | Saved production vs 80 digits | Saved DOP853 vs 80 digits |
|---|---:|---:|---:|
| First failed comparison | 6.573827e-49 | 4.036392e-15 | 2.845201431e-9 |
| Second failed comparison | 1.339163e-48 | 1.047273e-14 | 3.319852071e-9 |

The two DOP853 differences both attain their maxima at time 5, count state 16.
Public expectation readouts remain much closer: the largest production–Decimal
difference is 1.565414e-14, and the largest DOP853–Decimal difference is
1.536125e-13. Agreement of a few linear projections can coexist with larger
errors in individual probabilities.

The new frozen checks produced **10 passes and 2 failures**. The failures are
the saved DOP853 distribution comparisons at the new 1e-10 diagnostic tolerance.
The original production–DOP853 failures at 2e-9 remain unchanged. Precision
stability is empirical evidence, not a rigorous bound on all rounding error.
The fixed truncation argument applies to the exact-arithmetic stochastic
operator; the reported numerical tail estimates are not outward-rounded
certificates.

## Execution and review scope

One run completed four reference trajectory wrappers, four generator
constructions and 24 positive-time propagations. A separate saved-array
arithmetic phase brings the ledger to **33 attempts and 66 events**, all closed.
There were zero World, production, candidate or model API calls. The process
receipt recorded 2.34 seconds wall time and approximately 2.18 seconds CPU.
Two earlier package revisions were withdrawn before any numerical execution to
repair supervisor resource handling; both remain archived.

A fresh reviewer reproduced all 12 reported comparison maxima, their maximizing
coordinates and tolerance decisions using saved-number arithmetic. Its 211
evidence checks passed; the original files and the frozen pre-run inputs stayed
byte-identical. These checks are separate from the two numerical failures.

This supports a precision limitation in these saved DOP853 outputs. It does not
identify integration versus interpolation as the cause, certify the legal
parameter domain, establish a unique mechanism, or measure GPT capability.
Review remains **same-family, provisional, pending external review**; no
canonical integrity audit was available. Hashes bind bytes, not scientific truth.

Operator-owned evidence is retained outside the public repository:

- Authorized revision-3 freeze SHA-256:
  `646793794e08dbee89f40aa57795016275b02fb9aa585f9a4ad3eda427cb4a8f`.
- Independent reference source SHA-256:
  `54d59939c47dce5639cd509dfdb70be0f80afeb5e641a98b2b0080a22a4eb787`.
- Independent saved-result audit SHA-256:
  `778ac4fc7e9749ab154f7e465fc9e36014138f75f1d15c63508d9c16f842bcf0`.

Raw instance identifiers, parameters, arrays and private paths are not included
in this public summary. The scientific contract remains in the [world
README](README.md); this diagnostic changes neither that contract nor scoring.
