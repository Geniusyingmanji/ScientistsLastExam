# MethaneSourceAttribution — measured values

All numbers are reproducible from `verification/`.

## The model is validated by closure, not fitted

| quantity | model | observed |
|---|---|---|
| emission-weighted source signature | −53.37 ‰ | — |
| effective total-sink fractionation | 6.2 ‰ | 6–7 ‰ (literature) |
| atmospheric δ¹³C | −47.17 ‰ | −47.2 ‰ |
| burden | 5278 Tg | ~5300 Tg |
| drift over 20 years | 0 Tg, +0.023 ‰ | — |

The atmospheric value is not an input. It falls out of the emission mix and the sink fractionation,
and that it lands on the observed number is the check.

The first version used the OH-only fractionation of 3.9 ‰ and drifted three per mil over twenty
years. The constant was wrong and the drift found it; the model was not adjusted to hide it.

## The confounding is complete, not approximate

Fit a **pure source change with the sink held fixed** to each regime's trajectory and report the
misfit in units of observational noise (5 Tg on the burden, 0.02 ‰ on δ¹³C):

| regime | reduced misfit of a pure-source explanation |
|---|---|
| `tracer_identifiable` | 0.00 |
| `inventory_identifiable` | 0.00 |
| `microbial_overlap` | 0.00 |
| `sink_confounded` | **0.00** |

A sink change of a few per cent is reproduced by a source change to within the noise. The two cheap
measurements say nothing against attributing it entirely to sources — which is the objection raised
against the microbial reading of the post-2007 rise. `sink_confounded` is therefore a **pure** sink
change with no source moving, so naming any source is unambiguously a false discovery.

## Regime calibration

| regime | ethane SNR | inventory SNR per changed source | δ¹³C change (‰) |
|---|---|---|---|
| `tracer_identifiable` | 0.7 – 8.8 | 0.3 – 12.2 | **+0.187 … +0.945** |
| `inventory_identifiable` | 0.2 – 2.0 | **2.0 – 6.9** | −0.669 … −0.107 |
| `sink_confounded` | 0.3 – 1.7 | — | **−0.083 … −0.044** |
| `microbial_overlap` | 0.2 – 1.9 | 0.1 – 3.0 | −0.349 … −0.179 |

The δ¹³C **sign** is the clean cut: only `tracer_identifiable` raises it, because fossil (−44 ‰) and
biomass burning (−25 ‰) are the only sources heavier than the −53.37 ‰ mean.

`microbial_overlap` occasionally shows one sector at 3σ. That does not make it answerable: **two**
sources moved, so a report naming the resolvable one is still wrong, and the other reads near zero.

## Baseline and reference

| submission | combined | mechanism | FDR | refusal | coverage |
|---|---|---|---|---|---|
| baseline | **0.000000** | 0.562 | 0.656 | 0.000 | 1.000 |
| reference | **0.754464** | 0.812 | 0.071 | 1.000 | 0.438 |

Per regime, what the baseline did:

| regime | recovered | what it named |
|---|---|---|
| `tracer_identifiable` | 8/8 | biomass burning ×6, fossil ×2 |
| `inventory_identifiable` | 1/8 | ruminants ×7 |
| `microbial_overlap` | 0/8 | ruminants ×8 |
| `sink_confounded` | 0/8 | **waste ×5, wetlands ×3** |

The baseline is genuinely competent where isotopes suffice — 8 of 8 — and scores zero. The last row
is the trap firing: a sink-only rise looks like a modest increase in a source slightly lighter than
the mean, and waste is that source. It attributes a sink change to sources in every one of those
cases, with confidence.

The reference abstains on 16 of 16 unanswerable cases and still misses 3 of 16 answerable ones. The
headroom is in mechanism, not refusal.

## Corrections made during calibration

* **Tracers measured the wrong thing.** The ethane and radiocarbon readings first reported the
  change in a *ratio*, whose denominator moves whenever any source changes. They responded to
  microbial changes almost as strongly as to fossil ones and separated nothing. They now report the
  change in tracer **emission**, a clean linear functional of the emission changes.
* **The answerable regime drew a source no tracer can single out.** `wetlands` is microbial; ethane
  and radiocarbon both say only "not fossil". A third of the supposedly answerable cases were not.
* **Regime sizes were absolute.** A flat 10–18 Tg step is under one sigma for wetlands (nominal
  180 Tg) and over three for waste (75 Tg), so one member of the "unresolvable" pair was resolvable.
  Sizes are now scaled to each sector's own inventory uncertainty.

## Robustness

Seventeen degenerate and adversarial submissions score 0.000000 without raising: blanket
abstention, never abstaining, claiming every sector, claiming none, guessing without measuring,
alternating abstention, `None`, `{}`, a non-boolean abstain flag, a NaN confidence, an out-of-range
confidence, an unknown sector name, a non-boolean sector flag, a raising callable, overspending the
budget, flooding the call count, an unknown measurement name, and an inventory request without a
sector.

The malformed ones report `valid = 0`; the well-formed-but-useless ones report `valid = 1`.
