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

## Three regimes

| regime | what moved | why the answer is what it is |
|---|---|---|
| `attributable` | one source, isotopically distinct | ethane (co-emitted by fossil, not microbial) or radiocarbon (fossil is ¹⁴C-dead) pins it |
| `sink_confounded` | the sink only | no purchasable observable constrains OH; abstain |
| `microbial_overlap` | two microbial sources whose δ¹³C ranges overlap | ethane and radiocarbon both say "not fossil" and neither says which; abstain |

The two refusal reasons are again different: one is an unmeasured dimension, the other is an
unresolvable one.

## Remaining

The observable menu and its budget (burden trend, δ¹³C trend, ethane ratio, radiocarbon, a bottom-up
inventory, an OH proxy that is uninformative in the confounded world), the evaluator on the standard
discovery triple, baseline, reference, the adversarial sweep, and packaging.

Working code in `.research/methane_wip/`.
