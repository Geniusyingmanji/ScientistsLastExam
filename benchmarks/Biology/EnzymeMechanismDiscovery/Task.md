# EnzymeMechanismDiscovery — protocol-only episode pilot

**Status: candidate, protocol_only, frontier_eligible=false.** This pilot
provides a runnable discovery episode. Its fixed-design construction controls
remain near ceiling even under substantially smaller experiment budgets, so it
is not an admitted replacement for the retired EnzymeKineticsLaw. Do not report
it as a hard discovery task or include it in frontier benchmark aggregates.

A substrate becomes an intermediate and then a product. Product feedback,
substrate inhibition and loss of active enzyme can coexist. Select assays,
sample times, measured species and perturbations under a shared budget; then
commit an effective mechanism and kinetic parameters. Independent, previously
unseen mixed-load/pulse trajectories test that committed model.

## Scientific target

The target is a composition of effective kinetic modules, **not a uniquely
identified microscopic binding mechanism**. All pilot worlds use this public
family. The intermediate starts at zero. With concentrations in mM and time in
minutes, the equations between pulses are:

```text
v1 = kcat * E * S / (km * (1 + P/ki) + S + S*S/ks)
v2 = k2 * X
dS/dt = -v1
dX/dt = v1 - v2
dP/dt = v2
dE/dt = -kd * E
```

Here `E` is relative active-enzyme concentration, not an observable species.
The `P/ki` term is absent without `product_feedback`; `S*S/ks` is absent without
`substrate_inhibition`; `kd=0` without `enzyme_decay`. Consequently three modules
can form eight compositions. `kcat` has units mM per minute per relative enzyme
activity; `km`, `ki`, `ks` are mM; `k2`, `kd` are inverse minutes.

At a pulse, the selected substrate, product or enzyme level increases by the
specified amount. An enzyme pulse introduces **fresh active enzyme**. Samples
at the pulse time are taken immediately after the pulse. Substrate plus
intermediate plus product is conserved except for substrate/product additions.
The public `model.py` implements numerical prediction without any hidden data.

Initial substrate disappearance cannot reveal `k2` or enzyme decay. At zero
initial product it also cannot reveal product feedback. These are exact
observational confounds, not extra noise. Time series and perturbations can
resolve them. This limited model family avoids demanding a microscopic answer
that the allowed observations cannot identify.

The substrate-inhibition and feedback terms are established effective kinetic
forms; their composition and the synthetic ranges below are a benchmark model,
not an experimentally established enzyme. Relevant primary work includes
[Andrews (1968)](https://doi.org/10.1002/bit.260100602),
[progress-curve analysis including product inhibition](https://pubmed.ncbi.nlm.nih.gov/3120622/),
and [enzyme-inactivation diagnostics](https://www.sciencedirect.com/science/article/abs/pii/S0301462206002651).

## Episode interface

The candidate receives a JSON `problem` and calls `experiment(tool, arguments)`.
It must return a JSON claim. A trusted runner, rather than the candidate,
allocates the world seed and calls confirmation and private evaluation.

Every public problem key is defined below:

| Key | Meaning |
|---|---|
| `task_id` | `SystemsBiology/EnzymeMechanismDiscovery` |
| `contract_version` | `episode-pilot-v1`; different scientific contracts must not share scores |
| `budget_units` | 216 charged experiment units |
| `units` | `time`, `concentration`, `enzyme` units as defined above |
| `target` | Effective module recovery and new-trajectory prediction |
| `modules` | `product_feedback`, `substrate_inhibition`, `enzyme_decay` |
| `parameters` | `kcat`, `km`, `k2`, `ki`, `ks`, `kd` |
| `active_parameter_ranges` | Inclusive permitted ranges, also the generator's active ranges |
| `initial_bounds` | Substrate `[0.1,6]`, product `[0,4]`, enzyme `[0.2,2]` |
| `time_bounds` | Sample times `[0.02,8]` minutes |
| `max_samples` | At most 12 samples in a time course |
| `channels` | Substrate, intermediate and product |
| `pulse_bounds` | Time `[0.1,6]`, amount `[0.1,3]`; pulse must precede the last sample |
| `pulse_species` | Substrate, product or enzyme |
| `noise` | Independent additive Gaussian readings, known standard deviations below |
| `tools` | Argument keys, costs, and response fields for each tool |
| `claim_schema` | Exact claim keys, allowed decisions and parameter rules |
| `confirmation` | Three new pulse trajectories, independent noise, all three channels, prediction tolerance 0.06 mM |
| `identifiability` | All pilot worlds lie in the declared family; no supported calibrated-refusal claim |

The active parameter ranges are `kcat:[0.7,1.8]`, `km:[0.35,1.0]`,
`k2:[0.3,1.2]`, `ki:[0.5,1.6]`, `ks:[1.8,5.0]`, `kd:[0.08,0.2]`.
The gap between absent and present modules is public. The task does not ask you
to reliably identify an arbitrarily weak effect in finite noisy data.

### `initial_rate`

```json
{"initial":{"substrate":1.2,"product":0.0,"enzyme":1.0}}
```

Costs **3** units. Returns `evidence_id`, `tool`, a copy of `arguments`, `rate`
and `sigma`. The rate is substrate disappearance at time zero, with independent
Gaussian standard deviation 0.008 mM/min. It is **not** the initial product
appearance rate, which is zero because the intermediate initially vanishes.

### `time_course`

```json
{
  "initial":{"substrate":2.4,"product":0.7,"enzyme":0.8},
  "times":[0.1,0.8,1.9,3.0,4.7,8.0],
  "channels":["substrate","product"],
  "pulse":{"time":3.0,"species":"enzyme","amount":1.2}
}
```

Costs **`4 + len(times)*len(channels) + (4 if pulse else 0)`** units. Set `pulse`
to `null` for no pulse. Times must be strictly increasing; channels must be
unique. Every exact key shown is required and unknown keys are rejected.

Returns `evidence_id`, `tool`, a copy of `arguments`, `observations`, and `sigma`.
`observations` is one dictionary per sample time, containing the requested
channel names and noisy concentrations. Standard deviation is 0.006 mM per
reading, independent across readings and assays. Negative readings due to noise
are retained. Replicates cost another complete assay. Evidence IDs have the form
`assay-0001` and are local to the episode.

Invalid public inputs and unaffordable queries raise an error before any budget
or experimental state is consumed. Exploration closes after claim commitment.

## Claim contract

Return exactly `decision`, `mechanism`, `parameters`, and `evidence_ids`:

```json
{
  "decision":"discover",
  "mechanism":["product_feedback","enzyme_decay"],
  "parameters":{"kcat":1.2,"km":0.6,"k2":0.7,"ki":1.1,"ks":null,"kd":0.12},
  "evidence_ids":["assay-0001","assay-0002"]
}
```

`mechanism` is a list of unique public modules. Omitting a module explicitly
asserts its absence. All six parameter keys are required; an absent optional
module requires its parameter to be `null`. Numeric parameters must lie within
the public active ranges; booleans and nonfinite numbers are invalid.

`evidence_ids` contains distinct actual IDs observed in this episode. Empty
evidence is legal: a data-free guess is evaluated as a guess, without invented
experimental support. Citation counts receive no scientific reward and do not
prove that the candidate used the observations correctly.

Abstention is legal with `decision:"abstain"`, `mechanism:[]`, `parameters:{}`,
and optionally valid evidence IDs. All-abstain receives zero discovery credit.
There are no out-of-family worlds in this pilot; correct-refusal performance is
reported as **not applicable, denominator zero**, rather than a fabricated zero
or perfect score. Adding unsupported worlds requires a separately validated
scientific contract.

## Confirmation and private metrics

The trusted runner freezes the claim, then reveals three fresh trajectories
with mixed starting loads and enzyme/substrate/product pulses. Confirmation
design and observation random streams do not depend on exploration call count.
Repeated confirmation of the same frozen claim is idempotent; editing it or
substituting confirmation data is rejected. Model prediction is evaluated from
the precommitted parameters, so seeing confirmation cannot enable refitting.

The private verifier reports the following separately, with numerator and
denominator for each rate:

- `mechanism_recovery`: exact composition correct / one world.
- `module_accuracy`: correct presence/absence decisions / three modules;
  abstention contributes zero positive recovery credit.
- `false_discovery_rate`: wrong complete compositions / discovery claims.
- `module_false_discovery_rate`: false positive modules / claimed active modules.
  This differs from the complete-claim error above and misses false negatives.
- `refusal_rate`, `correct_refusal_rate`, `discovery_coverage`.
- `confirmation_pass_rate`: pulse trajectories with prediction RMSE at most
  0.06 mM / three trajectories for a discovery claim.

Zero denominators produce `value:null`. `confirmation_rmse_mM` compares the
frozen model to the latent mean concentration on new designs; observed noisy
confirmation readings are not treated as exact truth. `prediction_score` is
`exp(-(RMSE/0.06)^2)`. `combined_score` is exact mechanism recovery times this
continuous prediction score, zero for abstention. Error, refusal and coverage
are never averaged into it.

This is **same-family simulator confirmation**, not independent wet-lab
validation or discovery of a new law in nature. New composition families,
misspecified kinetics, nuisance calibration and external data remain future
work. Candidate code must never import `verification/` or receive the world seed.

## Reference, controls and admission

`verification/reference.py:solve(problem, experiment)` fits continuous module
coefficients, chooses perturbations by disagreement with alternative modules,
and refits the selected composition. It uses only the public problem, model and
charged callback. Other controls use the same inference with fixed dynamic
assays, only initial rates, no observations, or universal abstention.

Run the construction panel from repository root:

```sh
python -m benchmarks.Biology.EnzymeMechanismDiscovery.verification.audit_controls \
  --worlds 24 --output /tmp/enzyme-construction-controls.json
python -m pytest -q tests/test_enzyme_mechanism_discovery.py
```

The known family and current parameter separation may still make a general
nonlinear-fit program easy for frontier models. A fixed design can also be
scientifically sufficient. Neither a complex trajectory nor the reference's
adaptive label establishes difficulty. Keep this pilot outside the default
benchmark until repeated, frozen, fresh-world model calibration and independent
domain review support admission. Near-perfect frontier performance triggers
further redesign or retirement; changing score normalization is not hardening.

A matched-cost construction study tested caps of 60, 80 and 104 units. Actual
spends were 52, 72 and 104 units for both methods. At **all six settings** the
fixed and adaptive controls each recovered 24/24 mechanisms and passed 72/72
confirmation trajectories. Adaptive selection reduced parameter error slightly,
but these results do not establish useful difficulty. The unchanged 216-unit
pilot is retained exclusively for protocol/integration checks; budget reduction
alone is not an acceptable hardening claim. Full results and source hashes are
in `references/budget-study.json` and `references/known_best.md`.

## Relation to existing work

- `SystemsBiology/EnzymeKineticsLaw` fits one of six static initial-rate formulas.
  This pilot composes simultaneous modules, includes intermediate/active-enzyme
  dynamics, and requires a model that predicts fresh perturbations.
- `ChemicalKinetics/ReactionMechanismFitting` and `Catalysis/CatalystDeactivationLab`
  are close local neighbours. This pilot's new contribution is the standard
  episode/commit/confirmation protocol, not a claimed novel biochemical domain.
- [SciGym](https://arxiv.org/abs/2507.02083) motivates executable biochemical
  perturbation environments with structural and trajectory evaluation. This
  implementation is an original small effective model, not a BioModels export.
- [ScienceIDE](https://github.com/aitofound/ScienceIDE) motivates explicit
  scientific checks and environment boundaries. No ScienceIDE source or data is
  vendored here, and this pilot does not require its container stack.
