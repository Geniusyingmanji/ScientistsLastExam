# TransmissionSpectrumSpecies — say which molecules are there, or say you cannot tell

## Scientific setting

When a planet crosses its star, some starlight passes through the planet's atmosphere on the way to
us, and molecules leave absorption features in it. Reading those features back into a list of
molecules is how every claimed atmospheric detection is made — and it is contested right now.

The JWST spectrum of K2-18 b produced a reported detection of dimethyl sulfide, a possible
biosignature. The reanalyses that followed concluded that the features **are not uniquely
identifiable**: ethylene and chloroethane are at least as favoured, DMS and DMDS are mutually
degenerate in the mid-infrared, and the community's own summary is that more work is needed to
identify potential false positives (A&A 700 (2025) A55; AJ 170 (2025); arXiv:2505.10539).

So the interesting question is not only *which molecules are present*. It is **when the data cannot
say**, and whether a searcher knows the difference.

## The world

In the isothermal, well-mixed limit the transit depth is

```
D(lambda) = depth + scale * ln( sum_i x_i sigma_i(lambda) + kappa_grey + kappa_ray (1/lambda)^4 )
```

so a species enters as the *logarithm* of its cross-section. Three consequences drive the task, and
each produces a different kind of unanswerable system:

* a **grey cloud deck** raises the floor inside the logarithm and mutes every feature at once;
* a **confusable pair** whose bands overlap is not separable at any allocation of the budget — here
  the two templates correlate at 0.9997, the fit correlates at −0.9992, and individual amplitudes
  carry 24.5 times the uncertainty of their sum;
* a **faint system** never reaches unit signal-to-noise even if the whole budget goes to its best
  band.

Only the third is noise. A searcher that abstains whenever the spectrum looks noisy gets that one
and misses the other two.

| regime | best achievable signal-to-noise | correct answer |
|---|---|---|
| `clear` | 23 – 54 | report the species set |
| `confusable` | 22 – 50 | abstain — something is there, the data cannot say which |
| `muted` | 0.02 – 0.13 | abstain |
| `sparse` | 0.47 – 0.90 | abstain |

Twenty-four of the thirty-six systems in the set are unanswerable. That is the point.

## The budget

You get `budget_transits` transits and twelve wavelength bands, and you choose how to spend them.
`observe(allocation)` takes one non-negative integer transit count per band and returns the binned
depth and its uncertainty for each; a band given zero transits returns `None`. The budget is
cumulative across calls and cannot be exceeded.

## What is scored

**Three axes, reported separately and never averaged**, because they fail in opposite directions
and a single number hides which one moved:

| axis | meaning | denominator published |
|---|---|---|
| `mechanism_recovery` | on identifiable systems, is the species set exactly right? | yes |
| `false_discovery_rate` | of the species claimed present, how many are absent? | yes |
| `correct_refusal_rate` | on unidentifiable systems, does the searcher abstain? | yes |

A fourth counter, `attempted_rate`, records how often the searcher declined to abstain. Without it,
"abstained on everything" and "the science is too hard" look identical in the report, and they call
for opposite responses.

`combined_score` is the product of recovery, `(1 - false discovery rate)` and refusal, normalised so
that blanket abstention scores exactly zero. The product is deliberate: a method that never refuses
is not doing calibrated discovery, however well it identifies, and a method that always refuses
identifies nothing. Both degenerate strategies score zero and the report tells them apart.

**Naming either member of the confusable pair is a false discovery**, even when one of them is
genuinely present. The world does not determine which, so naming either is a claim the data cannot
support. The pair is named in the problem as `known_confusable_group` — it is not a secret, and
hiding it would only make the task about guessing which species overlap rather than about what to do
when two of them do.

## Contract

Implement `analyze(problem, observe)`, called once per system, returning

```python
{"abstain": bool, "species": {name: bool, ...}, "confidence": float}
```

`species` is read only when `abstain` is false; `confidence` must be a finite number in `[0, 1]`.
`problem` carries these keys, all public:

| key | meaning |
|---|---|
| `system_id` | which system this is |
| `band_edges_um` | the twelve band boundaries, in microns |
| `wavelength_um` | the underlying wavelength grid |
| `species_catalogue` | the candidate species, in order |
| `cross_sections` | one opacity template per species on that grid |
| `budget_transits` | how many transits you may spend in total |
| `known_confusable_group` | species the observation cannot separate |
| `graded_species` | the species recovery is graded on |

Submission shape is checked by `sle.contract_lint` before scoring. A report that raises, returns the
wrong shape, overspends the budget, or asks for a negative number of transits scores zero on that
system without disturbing the others.

## What this task does not measure

Cross-sections are synthesised as fixed sums of Gaussian bands, not taken from a line list. That is a
deliberate limit: the task measures whether a searcher can tell an identifiable system from an
unidentifiable one under a budget, not whether it knows real molecular opacities. A submission that
hard-codes real HITRAN data would gain nothing, because the catalogue it is scored against is the
one handed to it.

## Relation to the rest of this benchmark

`Physics/RadialVelocityPlanets` and `Physics/LookElsewhereAnomaly` concern finding *planets* and the
trials factor; this concerns what is *in* one. `Chemistry/CrowdedSpectrumAssignment` and
`Spectroscopy/NMRSpectrumFitting` are spectroscopy of samples in a laboratory, where the observer
chooses the conditions rather than the budget. No task in the Frontier-Eng catalogue (47 tasks in
the paper appendix, 95 entries in its `TASK_DETAILS`) concerns atmospheric retrieval or
biosignature attribution.
