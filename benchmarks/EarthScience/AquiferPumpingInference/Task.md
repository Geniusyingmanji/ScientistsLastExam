# AquiferPumpingInference

## Scientific problem

A pumping test perturbs an aquifer and records hydraulic drawdown away from the well. In the
supported family, an infinite homogeneous confined aquifer follows the Theis radial-flow solution.
Choose observation radii and times, recover transmissivity and storativity, and predict drawdown at
sealed radius/time contexts. Refuse and name the failure when the record resolves leakage through
an aquitard, a constant-head recharge boundary, or delayed dual-porosity storage.

The difficulty is experimental as well as numerical. Early and late observations constrain
different parameter combinations, while opening a new observation radius is expensive and radial
diversity is needed to distinguish spatial leakage or an image-well boundary from a change in
transmissivity.

## Candidate interface

Implement:

```python
def infer_aquifer(problem, measure):
    ...
```

Both arguments to `measure(radius_m, time_s)` must be values supplied by `problem`. The first
observation at a distinct radius costs seven units: six setup units plus one measurement unit.
Each later observation at that radius costs one unit. Repeated measurements are permitted and
have independent deterministic noise. Catching an exception does not undo an invalid coordinate
or budget violation. The callback returns exactly:

- `measurement_id`: immutable current-world evidence identifier;
- `radius_m`, `time_s`: the requested coordinates;
- `drawdown_m`: nonnegative hydraulic-head drawdown;
- `drawdown_standard_error_m`: one-standard-error uncertainty;
- `cost_units`: cost of this observation;
- `spent_units`: cumulative cost in this world.

## Supported model

For pumping rate `Q`, transmissivity `T`, storativity `S`, radius `r`, and elapsed time `t`,

```text
u = r**2 S / (4 T t)
s(r,t) = Q E1(u) / (4 pi T),
```

where `E1` is the exponential integral. The same `T` and `S` govern every radius and time.

The three unsupported families are explicit reduced-order alternatives. Writing `s_T(r,t)` for
the confined Theis expression above, the evaluator uses

```text
leaky aquifer:      s(r,t) = s_T(r,t) exp(-r/L)
recharge boundary: s(r,t) = max(0, s_T(r,t) - s_T(sqrt(r**2 + (2d)**2), t))
dual porosity:      s(r,t) = w s_T(r,t; T,S) + (1-w) s_T(r,t/tau; T,rho S)
```

Here `L` is a leakage length, `d` a recharge-boundary distance, `rho` a storage ratio, `tau` a
delay factor, and `w` the fast-domain weight. These formulas define this benchmark's reduced-order
laboratory; they are motivated by, but are not the full Hantush-Jacob or Moench field solutions.

Every candidate-visible `problem` key is listed here:

- `schema_version`: interface version;
- `pumping_rate_m3_s`: constant pumping rate `Q`;
- `observation_radii_m`: allowed radius values;
- `observation_times_s`: allowed elapsed-time values;
- `measurement_budget_units`: maximum total callback cost;
- `minimum_evidence_measurements`: evidence count required for a scientific diagnosis;
- `parameter_bounds`: mapping from both reported parameter names to inclusive `[lower, upper]` lists;
- `prediction_contexts`: ordered mappings containing `radius_m` and `time_s`;
- `diagnosis_values`: allowed diagnosis strings;
- `supported_model`: name of the supported confined-aquifer family;
- `measurement_model`: callback cost and noise description;
- `abstain_when`: refusal rule.

## Return value

Return exactly these keys:

- `diagnosis`: `confined`, `leaky_aquifer`, `recharge_boundary`, `dual_porosity`, or `undetermined`;
- `transmissivity_m2_s` and `storativity`: finite values within their public bounds;
- `predicted_drawdown_m`: one finite nonnegative value per prediction context, in supplied order;
- `confidence`: finite number in `[0,1]`;
- `abstain`: boolean, false exactly for `confined`;
- `evidence_measurement_ids`: distinct identifiers returned in this world.

A named scientific diagnosis requires at least `minimum_evidence_measurements`; `undetermined`
requires at least one. Do not assume hidden seeds, fixed parameters, world order, or diagnosis.

## Scoring

For supported worlds, continuous quality combines parameter recovery, sealed prediction, and a
correct confined-family diagnosis. The split `combined_score` is the mean supported-world quality
multiplied by the exact named-refusal rate over unsupported worlds. Therefore blanket abstention,
never refusing, and a fixed unsupported label all score exactly zero. Confidence calibration
changes supported-world quality only slightly.

Mechanism accuracy, false-discovery rate, correct-refusal rate, supported discovery coverage,
attempted discovery, parameter recovery, prediction, validity, and held-out transfer are reported
separately. Each rate publishes its numerator and denominator. Mechanism accuracy uses all worlds;
an invalid submission, wrong family, or undetermined answer is incorrect.

The truth-blind reference, ablations, and a 128-strategy shortcut probe are quantified in
`references/known_best.md` and pin the capability ladder without exposing evaluator worlds.
It scores `0.622081/0.793352` development/held out. A one-radius half-budget version scores
`0.000000/0.192774`; fixed storativity scores `0.351835/0.431246`; never refusing scores zero;
and a confined fit followed by three residual thresholds reaches `0.481859/0.525816`.

## Relationship to nearby tasks

`Geophysics/GravityInversion` reconstructs static subsurface density bodies by choosing surface
gravity stations; it has no pumping intervention, transient diffusion equation, hydraulic
parameters, or aquifer-boundary diagnosis. `ClimateScience/EnergyBalanceModel` infers a global
two-layer climate response from chosen forcing experiments, not radial groundwater flow.
`AtmosphericScience/RadiativeTransferFit` also performs active parameter inversion with refusal,
but selects thermal channels to retrieve atmospheric profiles rather than pumping-test radii and
porous-medium transport parameters. `EarthScience/GroundwaterRemediationDesign` (open proposal)
optimizes a remediation design rather than inferring an aquifer model from transient observations.
`WaterDistribution/DistributionNetworkTopology` (if merged) reconstructs a pressurized pipe graph;
it does not estimate porous-medium storage or reject aquifer conceptual models. No Frontier-Eng
task uses pumping-test interpretation or Theis-model inadequacy.

## Rules and references

Only edit `solution.py`. Use deterministic CPU-only Python, NumPy, SciPy, and the standard library.
Do not read `verification/` or `frontier_eval/`, use the network, or create processes.
`sle.contract_lint` may be imported for free shape checks.

The supported equation follows Theis (1935), DOI `10.1029/TR016i002p00519`. The reduced-order
leakage, boundary, and dual-porosity alternatives are motivated respectively by Hantush and Jacob
(1955), DOI `10.1029/TR036i001p00095`; Ferris et al. (1962), USGS Water-Supply Paper 1536-E,
DOI `10.3133/wsp1536E`; and Moench (1984), DOI `10.1029/WR020i007p00831`. They are benchmark
surrogates, not claims to reproduce those papers' complete solutions or field prescriptions.
