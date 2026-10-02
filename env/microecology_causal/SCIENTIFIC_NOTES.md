# Trusted scientific notes — do not expose to candidate agents

## Purpose and genuinely different structures

This experimental world keeps the original batch apparatus but varies causal
structure, not merely rates. It is independent of `env/microecology/`; no original
kernel, world or evaluated result is changed or imported. Public descriptions,
legal controls, costs, output channels, noise and scales are identical across
the three private structures. The anonymous peak permutation is fixed within
an instance and independently sampled from the structural choice.

All structures share the same carbon-transfer backbone and yield fractions.
Let S be nutrient, A/B/C living biomasses, X/Y/Z extracellular carbon pools and W
an unobserved inert pool. One unit of A uptake transfers S into 0.40 A + 0.35 X
and 0.25 Z. One unit of B uptake transfers X into 0.45 B + 0.55 Y. One unit of C
uptake transfers its substrate into 0.50 C + 0.50 W. Death transfers living
biomass to W; X and Y decay to W. No process creates or destroys carbon.

| Private stratum | C substrate | Inhibitor of A uptake | Inhibitor of C uptake |
|---|---|---|---|
| `inhibitory_feedback` | Z | Z | Y |
| `feedback_cut` | Z | Z | None |
| `direct_toxin_detox` | Y | Y | None |

In the first structure, B's secreted Y suppresses the organism that clears A's
inhibitory product Z. This closes an interspecies feedback path. The second
removes specifically **Y's inhibition of C**, disconnecting B's feedback onto
A/C. It is not a claim that the entire network is acyclic: A's product inhibition
and the A–C production/clearance relationship remain. Calling it simply an
"open chain" would be misleading.

The third has a different consumer resource and a different direct inhibitory
edge: B secretes the product that suppresses A, while C consumes that same
product. Its C-uptake flux is subtracted from **Y only**; old Z consumption is
absent. Z is then a noninhibitory coproduct. This changes both material routing
and the causal role of C. The alternatives represent indirect inhibition,
disconnection of that interaction, and direct byproduct inhibition with
consumer detoxification. They are stylized ecological motifs, not assertions
about particular organisms or molecules.

## Kinetics and common nuisance variation

Uptake rates are Monod resource-limited fluxes proportional to the organism's
biomass. Inhibition multiplies uptake by `1/(1+(inhibitor/K)^2)`. Temperature
multiplies all biological/decay fluxes by `2**((temperature_c-30)/10)`; it does
not change yields, routing or interaction topology.

The nominal private values are: uptake coefficients A/B/C = 0.95/0.80/0.65 h⁻¹,
resource half-saturation concentrations S/X/consumer-substrate = 0.30/0.12/0.10,
inhibition scales for A/C = 0.32/0.18, death = 0.012 h⁻¹ and decay X/Y =
0.012/0.025 h⁻¹. Each value is independently multiplied by a uniform factor in
[0.88,1.12], from the same distribution in every stratum. Some sampled
inhibition parameters are inactive in structures without the corresponding
edge; those inactive parameters are not identifiable. Yields are common fixed
values. No parameter distribution encodes a separate class label.

Private stratum selection is a domain-separated SHA-256 draw from the seed.
`World.operator_strata` and `World(seed).operator_stratum()` are operator-only
hooks; they are never part of `describe()` or `run()`. Registration remains
explicitly experimental; the integration boundary is documented below.

## Carbon accounting, positivity and bounded work

Each uptake column sums to zero: −1+.40+.35+.25 = 0,
−1+.45+.55 = 0, and −1+.50+.50 = 0. Death and decay each transfer equal amounts
to W. Consequently the ODE preserves the sum of all eight pools. At every
nonnegative coordinate boundary its consumption flux vanishes and remaining
production is nonnegative. Zero-inoculum organisms therefore remain absent.
The nonnegative orthant is invariant. Initial carbon is at most 13 and feeds
add at most 12, so every pool and total carbon are bounded by 25 mmol C/L.

Simulation uses event-split LSODA with relative tolerance 1e−9, absolute
tolerance 1e−12 and maximum internal step 0.5 h. Dense output keeps the numerical
mesh independent of observation times. Solver trial states are extended below
zero by using zero in rate evaluation. An output below −1e−9 or a material
balance error above 1e−7 raises a generic failure. Only smaller roundoff-level
negative entries are set to zero, subtracting exactly that correction from the
largest positive pool to preserve total carbon. This numerical cleanup is
explicit; positivity of the physical ODE follows from the flux structure, not
from unrestricted clipping. Measurement clipping is a separate public operation.

Depletion exports the removed carbon; feed imports its exact dose. Events at a
measurement time run before that measurement, with equal-time actions in input
order. The private trajectory helper exposes full pools and imported/exported
ledgers for testing; public observations expose neither W nor ledger metadata.

Tests use an independently constructed carbon-transfer matrix and DOP853 solver,
not the production derivative. Additional checks cover starvation's analytic
exponential decay, temperature clock changes, individual inward boundaries,
exclusive consumer substrates, all legal events and endpoint ordering, full
material accounting, absent organisms, reproducible clipped noise, observation
grid independence and public-description equality across structures.

## Identifiability and actual development evidence

Only reserved development seeds 7, 46, 1439 and 8743 were used. They choose direct
detoxification, inhibitory feedback, feedback cut and direct detoxification,
respectively. The diagnostic experiments below are **operator evidence**, not
agent instructions, required discoveries, evaluator answer keys or public
mechanism menus.

A standard development culture starts A=B=C=0.05, S=5 at 30°C. Comparing it with
the same culture without B gives these C contrasts at 15 h:

| Development seed | Private stratum | C with B minus C without B |
|---|---|---:|
| 46 | inhibitory feedback | −0.4289 |
| 1439 | feedback cut | approximately zero (<1e−7) |
| 7 | direct toxin/detox | +0.3065 |
| 8743 | direct toxin/detox | +0.2253 |

These effects are measured downstream biomass, not directly assigned or removed
readouts. A complementary intervention uses C-absent A/B cultures and removes
90% of one anonymous fraction at 9 h. At 12 h, removing the actual A inhibitor
increases A by 0.235–0.241 for Y in the direct structure and by 0.333–0.368 for Z
in the other structures. Removing the other of Y/Z changes A by less than 1e−7.
The report records all three public peak depletions, with the private molecular
role annotation separated from the raw observable traces. C-positive cultures
then distinguish the direct effect from the C-mediated one.

Timing matters: in seed 46, adding B suppresses A and C strongly around 12–18 h,
but the C difference becomes positive by 72 h because biomass production and
subsequent death occur at different times. A late abundance contrast must not
be interpreted as a timeless positive or negative causal edge. The raw report
retains these sign changes rather than selecting only a favorable endpoint.

Eight grouped parameter corners per stratum (uptake, saturation/inhibition, and
loss factors independently set to 0.88 or 1.12) retained a C contrast at 15 h of
−0.476 to −0.189 for feedback, within 2e−10 of zero for the cut, and +0.125 to
+0.429 for direct detoxification. This is a 24-profile boundary check, **not** an
exhaustive enumeration of all 2¹¹ parameter corners. A maximum-work experiment
(32 observations, 72 h, 40°C, maximal inocula/nutrient and four maximal feeds)
took at most 0.028 s in that local check, with nonnegative states and carbon
residual below 7.5e−14. It is runtime evidence, not a hardware-independent bound.

### Explicit competing-explanation regimes

The feedback and cut structures are exactly observationally equivalent when
their nuisance parameters and peak mapping are matched, B starts absent, all
extracellular fractions initially equal zero, and only this apparatus's legal
feeds, depletions and temperature changes are used. B remains zero, hence Y has
no source and stays zero, so the removed Y→C inhibition factor is identically
one. Arbitrarily dense observations or replicates within that restricted regime
cannot distinguish those two structures. The equivalence is not claimed for
direct detoxification, for B-positive inocula, for mismatched nuisance values,
or for apparatus extensions such as adding Y or inoculating B later. In fact,
C absence also disables the differing edge for the first two structures, even
if Y is produced; this is another restricted equivalence, not a globally missing
edge claim. Experiments must activate the relevant pathway to test it.

The matched-parameter diagnostic with B absent includes selective depletion,
nutrient feed and a temperature shift; the recorded trajectories of feedback
versus cut agree exactly numerically. Separately, shared-parameter full cultures
observed only through 0.25 h show a maximum difference among any two structures
of just 0.0211 paired measurement standard deviations across channels. That is
finite-information ambiguity under the stated noise, not mathematical equality
of all three mechanisms. Longer observations and interventions can resolve it.

## Baseline, scope and handoff

The baseline uses only public records, initial controls, temperatures and event
histories, with nearest-experiment time interpolation. It knows neither the
equations nor the structure menu. In 64 disjoint development queries, mean
prediction-only scores with 0/4/12 noisy records were 0.488/9.544/15.763; mean
NRMSE was 0.6670/0.3464/0.2902. Its weakness does not establish intrinsic
difficulty. A stronger fitted dynamical comparator should precede substantial
claims about candidate performance. Scales and noise were kept at the original
batch apparatus's declared values, not adjusted to any model outcomes.

The evidence establishes distinguishable constructed causal motifs and genuine
restricted non-identifiability. It does not establish novel biology, unrestricted
mechanism discovery, identification of a unique equation, structural holdout
generalization or contamination resistance. Absent effects may mean that the
pathway was not activated. Hidden structure variation adds a testable challenge;
it is not by itself a validated scientific-discovery benchmark.

Run `python -m env.microecology_causal.calibrate --output <operator-path>.json`
to reproduce the raw clean/noisy diagnostic traces, matched-parameter alternatives,
boundary checks, noisy training records and disjoint development evaluation.

## Experimental registration

`env.registry` registers this as the eighth world and marks it in
`EXPERIMENTAL_ENVIRONMENTS`. `load_world('microecology_causal', seed)` returns the
World and its public-record baseline. The axis remains `times_h`; none of the
original microecology's scientific rules, scales or noise were edited.
All three existing task profiles support this world under `full_description`.
The world description is identical across private structures; adding the world
to the public task/claim catalogs supplies no structure menu or desired answer.
The candidate is never given this document, tests, source or calibration files.

For a new explicitly selected cohort, `--balanced-strata microecology_causal`
cycles the three labels in `World.operator_strata`; trusted operators can call
`World(seed).operator_stratum()` to verify the allocation. These labels are
written only as `operator_sampling_stratum` in the private frozen manifest.
All actually used scientific development seeds, `7, 46, 1439, 8743`, already belong
to the central exclusion set. Integration tests may instantiate other seeds to
exercise schema/freeze plumbing; their fixture outcomes are not scientific
development evidence or formal results.

Public claim policy `public-claim-eligibility-0.5` applies the original
microecology's minimum 1 h lag after preparation and each preceding event, plus
matched times in both arms. Claims about a directly removed fraction at the
event instant remain ineligible. The rule declares an eligibility resolution;
it cannot establish causality, semantic novelty or unique mechanism recovery.
The prospective runner approves the same zero-clipped Gaussian observation
contract as original microecology. For latent concentration x >= 0,
`E[max(x+N(0,sigma²),0)] - x` lies in `[0, sigma/sqrt(2*pi)]`, with its maximum
at x=0. The recorded bias bound is therefore valid for every class and channel.

The task catalog version is now `scientific-task-profiles-0.1.1`. Existing
oscillator/Ising apparatus-only presentation guards were re-audited for the
catalog/claim additions. Their six projected problem envelopes and system prompt
retain identical scientific content; only the two metadata version strings
change. Unknown description/task/score additions continue to fail closed.
These changes require a new source freeze. Completed core/expansion source
archives, results, scoring formulas and seven-world null calibration are not
modified. The standalone calibration command above reproduces the structural
diagnostics. Generic baseline calibration also accepts explicit selection with
`python -m env.calibration --environments microecology_causal --output <new-operator-path>.json`;
its initial-value reference uses public inocula and time-zero feeds only. The
seven-world `claim_calibration.NULL_ENVIRONMENTS` list is unchanged. Registration
does not extend or recompute the old null calibration.
