# Experimental three-strain batch ecology

This apparatus observes three unfamiliar strains, `A`, `B`, `C`, nutrient, and
three anonymous extracellular fractions, `peak-01`, `peak-02`, `peak-03`.
The labels are consistent within one material instance. Their names do not
specify functions or molecular identities. The public contract is
`World.describe()`; operator source, manifests, tests, calibration output and
`SCIENTIFIC_NOTES.md` are not candidate attachments.

Every experiment starts a fresh vessel with the same material properties. All
concentrations are mmol carbon/L, time is hours, and temperature is Celsius.
Initial extracellular fractions and the unobserved inert pool are zero. A strain
with no initial inoculum remains absent. Internal dynamics conserve carbon;
nutrient feed adds carbon, selective depletion removes carbon, and some carbon
may enter the unobserved inert pool. The seven measured pools alone need not sum
to total carbon.

| Input | Legal values |
|---|---|
| `initial` | Required object containing exactly `A`, `B`, `C` in [0,1] and `nutrient` in [0,10]. |
| `times_h` | Required list of 1–32 strictly increasing finite times in [0,72]. |
| `temperature_c` | Optional finite value in [20,40], default 30. |
| `events` | Optional list of 0–4 events, default empty; nondecreasing `time_h`, each between zero and the final observation. |

Each event contains `time_h` and exactly one action:

* `deplete: {"channel": "peak-01", "fraction": 0.8}` selectively removes that
  fraction of one of the three extracellular peaks; fraction is in [0,1].
* `feed: 1.0` adds nutrient in [0,3] mmol carbon/L with negligible volume change.
* `temperature_c: 35` changes temperature within [20,40] until another change.

Events occur before measurement at the same time; equal-time events execute in
the supplied order. No other pool is directly changed by depletion. Observation
does not alter the trajectory. All numerical inputs must be finite real numbers,
not booleans; unknown fields and oversized arrays are rejected.

```json
{
  "initial": {"A": 0.05, "B": 0.05, "C": 0.05, "nutrient": 5.0},
  "temperature_c": 30,
  "times_h": [0, 6, 12, 18, 24, 48, 72],
  "events": [{"time_h": 12, "deplete": {"channel": "peak-01", "fraction": 0.8}}]
}
```

Output has only `axis`, `channels`, and `values`, with one seven-column row per
requested time. Channel order is `A, B, C, nutrient, peak-01, peak-02, peak-03`.
Independent Gaussian measurement noise has standard deviations
`[0.002,0.002,0.002,0.004,0.004,0.004,0.004]`, then is clipped at zero. There is no
process noise. Clipping produces positive measurement bias near zero; noisy
concentration sums need not conserve carbon. Fixed scoring normalization scales
are `[1,1,1,5,1,1,1]`.

Each experiment costs
`8 + len(times_h) + 2*len(events) + ceil(times_h[-1]/12)` units. The maximum legal
experiment costs 54 units. No cells, clock or medium carry across calls. This
batch apparatus does not expose direct chemical additions, later inoculation,
supernatant transfers or molecular identity assays.

The baseline compares public initial conditions, temperature and event
histories with supplied records, then interpolates the closest observed
trajectory. With no records it holds initial concentrations, applying declared
nutrient additions. It uses no ecological equations, hidden mechanism menu,
instance parameters or private seed. It is a weak empirical reference; a poor
baseline result alone is not evidence of scientific difficulty or novelty.

This eighth registered world remains **experimental**, pending independent
mechanism-design review. It must be selected explicitly for a new frozen cohort;
it does not enter completed core/expansion cohorts or the existing seven-world
null calibration. All three public task profiles apply without revealing a
mechanism menu. `full_description` is the supported presentation;
`apparatus_only` has not been audited for this world.

Quantitative paired claims require matched observation times at least 1 hour
after initial preparation and every event at or before that readout, inclusive
at the boundary. Future events do not restart the lag. This is the pilot's public
claim-resolution rule, not a fitted time constant or a certificate of mechanistic
depth. Prospective observations use a per-channel mean-bias bound of
`noise_std/sqrt(2*pi)` for zero clipping, in addition to the stated noise scale.

It represents synthetic carbon-balanced systems, not calibrated organisms.
Researchers may choose their questions and perturbations; a quantitative effect
or predictive fit does not by itself identify a unique causal mechanism.

Operator integration and calibration are described in
[SCIENTIFIC_NOTES.md](SCIENTIFIC_NOTES.md). They are not candidate attachments.
