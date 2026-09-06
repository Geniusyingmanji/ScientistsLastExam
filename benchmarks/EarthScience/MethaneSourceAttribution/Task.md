# MethaneSourceAttribution — say which sources moved, or say the record cannot tell

## Scientific setting

Atmospheric methane resumed growing in 2007 and its δ¹³C has trended lighter ever since. **What
drove it is not settled.** The isotopic evidence has been read as a largely microbial source; that
reading has been challenged on the grounds of spatial variability in source signatures and open
questions in the sinks, and the field's own summary is that source signatures remain poorly
constrained.

Both objections are this task, modelled rather than described.

## The world

A budget for the methane burden and its carbon isotope ratio:

```
d[CH4]/dt  = sum_i E_i - k [OH] [CH4]
d(d13C)/dt = ( sum_i E_i (delta_i - d13C) ) / [CH4]  -  k [OH] eps
```

The sink term is the first difficulty. OH removes the light isotopologue faster, so it **raises**
δ¹³C — which means a weaker sink and a lighter source both push the burden up and δ¹³C down.
Measured here: a pure source change reproduces a sink-only trajectory to a reduced misfit of
**0.00** against 5 Tg on the burden and 0.02 ‰ on δ¹³C. The burden and isotope records alone say
nothing against attributing a sink change entirely to sources.

Overlapping signatures are the second. Wetlands (−61 ‰), ruminants (−65 ‰) and waste (−55 ‰) are
all microbial and their ranges overlap; fossil is −44 ‰ and biomass burning −25 ‰.

The budget closes against observation, and that is the model's validation rather than a fit: the
nominal 580 Tg/yr inventory carries an emission-weighted signature of −53.37 ‰, the observed
atmospheric value is −47.2 ‰, and the 6.2 ‰ difference is the effective total-sink fractionation,
inside the 6–7 ‰ the literature gives. Integrated twenty years the model drifts 0 Tg and +0.023 ‰.

## What you can buy, and what it settles

| measurement | cost | what it settles |
|---|---|---|
| `burden` | 1 | how much extra methane |
| `d13c` | 1 | how light it is on average — **the sink moves this too** |
| `ethane` | 3 | fossil against everything else, by co-emission |
| `radiocarbon` | 5 | fossil against everything else, by being ¹⁴C-dead |
| `inventory` | 3 | one named sector, bottom-up |
| `oh_proxy` | 6 | the sink — **uninformative in the confounded world** |

The budget is 12 and ethane plus radiocarbon plus the sink proxy costs 14, so the allocation is a
real choice. The sink proxy returning nothing is not an evasion: it is the state of the methyl
chloroform constraint now that its emissions have ceased and the constraint has decayed with them.

## Four regimes, two answerable

| regime | what moved | correct answer |
|---|---|---|
| `tracer_identifiable` | fossil or biomass burning | attribute — δ¹³C **rises**, and ethane separates the two |
| `inventory_identifiable` | one microbial source, 3.5–5σ of its own inventory | attribute — buy the right inventory |
| `sink_confounded` | the sink only, **no source moved** | abstain |
| `microbial_overlap` | two microbial sources, each 0.8–1.4σ | abstain |

The two refusal regimes fail differently: one has an **unmeasured** dimension, the other an
**unresolvable** one.

`sink_confounded` carries a trap. Its burden rises while δ¹³C falls only slightly, and the source
that explains that is one slightly lighter than the emission-weighted mean — which is waste. A
searcher that buys the isotopes and the tracers concludes *waste increased*, confidently and
wrongly; the baseline in this package does exactly that in 5 of 8 cases. The way out is to buy the
waste inventory, find no change, and treat the contradiction between the top-down inference and the
bottom-up number as the reason to abstain. That contradiction is the real methane-budget problem.

## What is scored

**Three axes, reported separately and never averaged**, each with its denominator:

| axis | meaning |
|---|---|
| `mechanism_score` | on answerable cases, is the set of changed sources exactly right? |
| `false_discovery_rate` | of the sources claimed, how many did not move? |
| `correct_refusal_rate` | on unanswerable cases, does the searcher abstain? |

plus `discovery_coverage`, how often it declined to abstain. `combined_score` is the product;
blanket abstention scores zero because it recovers nothing, and never abstaining scores zero because
its refusal rate is zero. Both land on zero and the report tells them apart.

## Contract

Implement `attribute(problem, measure)`, called once per case, returning

```python
{"abstain": bool, "changed_sources": {name: bool, ...}, "confidence": float}
```

`changed_sources` is read only when `abstain` is false; `confidence` must be finite in `[0, 1]`.
`measure(name)` — or `measure("inventory", sector)` — charges the cost above against the budget; at
most 32 calls. `problem` carries these keys, all public:

| key | meaning |
|---|---|
| `case_id` | which case this is |
| `source_catalogue` | the sectors, in order |
| `measurement_costs` | the table above |
| `observation_budget` | what you may spend |
| `window_years`, `change_year` | the record length and when the change began |
| `microbial_sources` | which sectors are microbial |
| `note` | that the sink can move and is not one of the sources |

Submission shape is checked by `sle.contract_lint` before scoring. A report that raises, overspends,
or names a sector outside the catalogue scores zero on that case without disturbing the others.

## What this task does not measure

The box model is global and annual; there is no transport, no latitude, no seasonality, and the
sectors are five where an inversion would use dozens. It measures whether a searcher can tell an
attributable change from an unattributable one under a budget, not whether it can run an inversion.

## Relation to the rest of this benchmark

`EarthScience/ForcedSignalAttribution` attributes a climate signal to forcings and is `evidence`;
this names *which sources* and is `substance`. `Exoplanets/TransmissionSpectrumSpecies` is the other
`substance` task with a refusal axis, and its unanswerable cases are unresolvable spectra rather
than an unmeasured sink. No task in the Frontier-Eng catalogue concerns atmospheric source
apportionment.
