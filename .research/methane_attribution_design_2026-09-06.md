# MethaneSourceAttribution — design and validations (2026-09-06)

Target cell: **EarthScience × substance**, which is empty. `substance` is also the thinnest cell in
the inventory at four tasks, and three of those are in one discipline.

## Why this problem

Atmospheric methane resumed growing in 2007 and its δ¹³C has trended lighter since. What drove it is
**not settled**. Isotopic evidence has been read as a largely microbial source; that reading has
been challenged on the grounds of spatial variability in source signatures and open questions in the
sinks. The field's own summary is that source signatures remain poorly constrained
([ESSD preprint 2025-668](https://essd.copernicus.org/preprints/essd-2025-668/), NOAA δ¹³C-CH₄
constraint work).

Both objections are the task, modelled rather than described.

## The model, and the closure that validates it

A two-box budget for the burden and δ¹³C:

```
d[CH4]/dt  = sum_i E_i - k [OH] [CH4]
d(d13C)/dt = ( sum_i E_i (delta_i - d13C) ) / [CH4] - k [OH] eps
```

The sink term is the whole difficulty: OH removes the light isotopologue faster, so it *raises*
δ¹³C. A weaker sink and a lighter source both push the burden up and δ¹³C down.

**The budget closes, and that is the validation.** The nominal emissions (580 Tg/yr across five
sectors) carry an emission-weighted signature of −53.37 ‰; the observed atmospheric value is
−47.2 ‰; the difference, 6.2 ‰, is the effective total-sink fractionation and sits inside the 6–7 ‰
the literature gives. Integrated for twenty years the model drifts **0 Tg** in burden and
**+0.023 ‰** in δ¹³C, and reproduces a burden of 5278 Tg against an observed ~5300.

The first attempt used the OH-only fractionation of 3.9 ‰ and drifted three per mil over twenty
years. The model was not tuned to hide that; the constant was wrong and the drift found it.

## The confounding is complete, not approximate

The decisive measurement. Fit a **pure source change with the sink held fixed** to each world's
trajectory, and report the misfit in units of observational noise (5 Tg on the burden, 0.02 ‰ on
δ¹³C):

| regime | reduced misfit of a pure-source explanation |
|---|---|
| `attributable` | 0.00 |
| `microbial_overlap` | 0.00 |
| `sink_confounded` | **0.00** |

A sink change of a few per cent is reproduced by a source change to within the noise. The burden and
δ¹³C records alone say *nothing* against attributing it entirely to sources — which is precisely the
objection raised against the microbial reading of the post-2007 rise.

`sink_confounded` was therefore made a **pure** sink change with no source moving at all, so that
naming any source is unambiguously a false discovery, and a searcher can only avoid it by noticing
it has no constraint on the sink rather than by looking at its residuals.

## Four regimes, two answerable, and the budget cannot buy everything

| measurement | cost | what it settles |
|---|---|---|
| `burden` | 1 | how much extra methane |
| `d13c` | 1 | how light it is on average — moved by the sink too |
| `ethane` | 3 | fossil against everything else, by co-emission |
| `radiocarbon` | 5 | fossil against everything else, by being ¹⁴C-dead |
| `inventory` | 3 | one named sector, bottom-up |
| `oh_proxy` | 6 | the sink — uninformative in the confounded world |

Budget 12. Ethane plus radiocarbon plus the sink proxy is 14, so the allocation is a real choice.

| regime | what moved | correct answer |
|---|---|---|
| `tracer_identifiable` | fossil or biomass burning | attribute — a tracer sees it |
| `inventory_identifiable` | one microbial source, 3.5–5σ of its own inventory | attribute — buy the right inventory |
| `sink_confounded` | the sink only, no source | abstain |
| `microbial_overlap` | two microbial sources, each 0.8–1.4σ | abstain |

Measured across 32–40 development cases:

| regime | ethane SNR | inventory SNR per changed source | δ¹³C change (‰) |
|---|---|---|---|
| `tracer_identifiable` | 0.7 – 8.8 | 0.3 – 12.2 | **+0.187 … +0.945** |
| `inventory_identifiable` | 0.2 – 2.0 | **2.0 – 6.9** | −0.669 … −0.107 |
| `sink_confounded` | 0.3 – 1.7 | — | **−0.083 … −0.044** |
| `microbial_overlap` | 0.2 – 1.9 | 0.1 – 3.0 | −0.349 … −0.179 |

The δ¹³C **sign** is the clean cut: `tracer_identifiable` is the only regime where it rises, because
fossil (−44 ‰) and biomass burning (−25 ‰) are both heavier than the −53.4 ‰ emission-weighted mean.

## The confounded world has a richer trap than it was designed with

`sink_confounded` shows the burden rising with δ¹³C falling only slightly. A source explanation of
that needs a source a little lighter than the mean — which is waste, at −55 ‰. So a searcher that
buys the isotopes and the tracers concludes *waste increased*, confidently and wrongly.

The way out is to buy the waste inventory, which shows no change, and to treat the contradiction
between the top-down inference and the bottom-up number as the signal to abstain. That is the actual
methane-budget problem, and it appeared from the construction rather than being placed in it.

## Three regimes

| regime | what moved | why the answer is what it is |
|---|---|---|
| `attributable` | one source, isotopically distinct | ethane (co-emitted by fossil, not microbial) or radiocarbon (fossil is ¹⁴C-dead) pins it |
| `sink_confounded` | the sink only | no purchasable observable constrains OH; abstain |
| `microbial_overlap` | two microbial sources whose δ¹³C ranges overlap | ethane and radiocarbon both say "not fossil" and neither says which; abstain |

The two refusal reasons are again different: one is an unmeasured dimension, the other is an
unresolvable one.

## Corrections made during calibration

* The tracers first reported the change in the mean ethane-to-methane *ratio*, which moves whenever
  any source changes because the denominator does. It responded to microbial changes almost as
  strongly as to fossil ones and separated nothing. They now report the change in tracer
  **emission**, which is a clean linear functional of the emission changes.
* The answerable regime first drew `wetlands`, which is microbial: ethane and radiocarbon both say
  only "not fossil", so a third of the supposedly answerable cases were not.
* Regime sizes were set in absolute Tg and are now scaled to each sector's own inventory
  uncertainty. A flat 10–18 Tg is under one sigma for wetlands and over three for waste, so one
  member of the "unresolvable" pair was resolvable.

## Remaining

The evaluator on the standard discovery triple, baseline, reference, the adversarial sweep, and
packaging.

Working code in `.research/methane_wip/`.
