# AquiferPumpingInference

## Scientific problem

A pumping test perturbs an aquifer and records hydraulic drawdown away from the well. In the
supported family, an infinite homogeneous confined aquifer follows the Theis radial-flow solution.
Choose observation radii and times, recover transmissivity and storativity, and predict drawdown at
sealed radius/time contexts. Refuse and name the failure when the record resolves leakage through
an aquitard, a constant-head recharge boundary, or delayed dual-porosity storage.

The difficulty is experimental as well as numerical. Early and late observations constrain
different parameter combinations, while multiple radii are needed to distinguish spatial leakage
or an image-well boundary from a change in transmissivity.

## Candidate interface

Implement:

```python
def infer_aquifer(problem, measure):
    ...
```

`measure(radius_m, time_s)` costs one unit. Both arguments must be values supplied by `problem`.
Repeated measurements are permitted and have independent deterministic noise. Catching an
exception does not undo an invalid coordinate or budget violation. The callback returns exactly:

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

Supported worlds receive continuous parameter-recovery and sealed-prediction scores plus a correct
confined-family diagnosis. Unsupported worlds receive science credit only for the correct named
refusal. The clipped development `combined_score` is zero for the valid blanket-undetermined
baseline. Confidence calibration changes the score only slightly.

Mechanism accuracy, false-discovery rate, correct-refusal rate, supported discovery coverage,
attempted discovery, parameter recovery, prediction, validity, and held-out transfer are reported
separately. Each rate publishes its numerator and denominator. Mechanism accuracy uses all worlds;
an invalid submission, wrong family, or undetermined answer is incorrect.

The truth-blind reference, ablations, and a 192-strategy shortcut probe are quantified in
`references/known_best.md` and pin the capability ladder without exposing evaluator worlds.
It scores `0.985962/0.983490` development/held out. One-radius repeated sampling scores
`0.852296/0.839991`; fixed storativity scores `0.699741/0.722078`; never refusing scores
`0.612462/0.609990`; and the summary-statistic shortcut sweep reaches only `0.361500/0.361500`.

## Relationship to nearby tasks

`Geophysics/GravityInversion` reconstructs static subsurface density bodies by choosing surface
gravity stations; it has no pumping intervention, transient diffusion equation, hydraulic
parameters, or aquifer-boundary diagnosis. `ClimateScience/EnergyBalanceModel` infers a global
two-layer climate response from chosen forcing experiments, not radial groundwater flow.
`WaterDistribution/DistributionNetworkTopology` (if merged) reconstructs a pressurized pipe graph;
it does not estimate porous-medium storage or reject aquifer conceptual models. No Frontier-Eng
task uses pumping-test interpretation or Theis-model inadequacy.

## Rules and references

Only edit `solution.py`. Use deterministic CPU-only Python, NumPy, SciPy, and the standard library.
Do not read `verification/` or `frontier_eval/`, use the network, or create processes.
`sle.contract_lint` may be imported for free shape checks.

The supported equation follows Theis (1935), DOI `10.1029/TR016i002p00519`. Leaky-aquifer and
boundary diagnostics are grounded in Hantush and Jacob (1955), DOI `10.1029/TR036i001p00095`, and
Ferris et al. (1962), USGS Water-Supply Paper 1536-E, DOI `10.3133/wsp1536E`. The oracle is an
explicit reduced-order benchmark, not a field-site interpretation prescription.
Delayed dual-porosity behavior is motivated by Moench (1984), DOI `10.1029/WR020i007p00831`.
