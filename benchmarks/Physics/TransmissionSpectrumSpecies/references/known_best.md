# TransmissionSpectrumSpecies — measured values

All numbers are reproducible from `verification/`.

## Why this shape

The K2-18 b dimethyl sulfide dispute is the reason the task has a refusal axis at all. The reported
detection was followed by reanalyses concluding the features **are not uniquely identifiable**,
with ethylene and chloroethane at least as favoured, DMS and DMDS mutually degenerate in the
mid-infrared, and the community's own summary that more work is needed on false positives. The task
reproduces that shape: a third of its systems contain something that the observation cannot name.

## World calibration

Regimes are calibrated against the budget, not chosen by eye. The measure is the best achievable
signal-to-noise on the species signal if the entire 30-transit budget goes to the best band:

| regime | signal-to-noise range | systems | correct answer |
|---|---|---|---|
| `clear` | 23.46 – 54.33 | 12 | report the set |
| `confusable` | 21.69 – 50.10 | 12 | abstain |
| `muted` | 0.02 – 0.13 | 12 | abstain |
| `sparse` | 0.47 – 0.90 | 12 | abstain |

The first attempt failed this check and was rebuilt. Cloud opacity 9 and noise 9e-4 gave the muted
and faint regimes signal-to-noise between 6 and 25 once the budget accumulated — identifiable, not
unanswerable — so the opacity went to 500 and the faint noise to 6.5e-2. "Unidentifiable" now means
the whole budget on the best band still does not reach unit signal-to-noise.

## The confusable pair

| quantity | first attempt | shipped |
|---|---|---|
| template correlation after band averaging | 0.9912 | **0.9997** |
| fit covariance correlation | −0.9792 | **−0.9992** |
| design matrix condition number | 93 | 461 |
| individual amplitude uncertainty, relative to their sum | 4.9× | **24.5×** |

At 4.9× and signal-to-noise 30 the individual amplitudes were recoverable, which would have made
the refusal regime a matter of noise rather than of identifiability. At 24.5× they are not: the
sum is measured at high significance and neither member is, which is exactly the published
situation.

## Baseline, reference, and the degenerate strategies

| submission | combined | recovery | FDR | refusal | attempted | valid |
|---|---|---|---|---|---|---|
| baseline (never abstains) | **0.000000** | 0.250 | 0.716 | 0.000 | 1.000 | 1 |
| reference | **0.382716** | 0.667 | 0.205 | 0.722 | 0.458 | 1 |
| blanket abstention | 0.000000 | 0.000 | 0.000 | 1.000 | 0.000 | 1 |
| claim every species | 0.000000 | 0.000 | 0.706 | 0.000 | 1.000 | 1 |
| claim no species | 0.000000 | 0.000 | 0.000 | 0.000 | 1.000 | 1 |
| guess without observing | 0.000000 | 0.083 | 0.562 | 0.000 | 1.000 | 1 |

Both degenerate strategies score exactly zero, for opposite reasons, and `discovery_coverage` — 0.000
against 1.000 — is what tells them apart in the report. The baseline is the analysis the field's own
critiques are about: it fits, it reports what fits, and it has no notion that a spectrum can fail to
decide.

The reference abstains on all 24 muted and faint systems but on only 3 of 12 confusable ones. That
gap is the headroom: recognising *no signal* is easy, and recognising *a signal that cannot be
attributed* is the part the literature is arguing about.

## The determinism bug

The noise realisation was seeded from `hash()` of the system id. Python randomises string hashing
per process, so the same reference scored **0.4231** in one interpreter and **0.2092** in the next —
the score depended on which process the oracle ran in. It is now seeded from a `zlib.crc32` digest
combined with a per-system seed fixed at construction, and three runs under randomised
`PYTHONHASHSEED` agree exactly at 0.382716.

This is the kind of defect that would have survived every structural check and quietly made every
measurement on this task meaningless.

## Robustness

Fifteen degenerate and adversarial submissions score 0.000000 without raising: blanket abstention,
never abstaining, claiming every species, claiming none, guessing without observing, `None`, `{}`,
a non-boolean abstain flag, a NaN confidence, an out-of-range confidence, an unknown species name, a
non-boolean species value, a raising callable, an allocation over the budget, more than 64
observation calls, and a negative transit count.

The malformed ones report `valid = 0`; the well-formed-but-useless ones report `valid = 1`. Keeping
those apart is the whole reason the report has a `valid` field.
