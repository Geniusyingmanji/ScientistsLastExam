# SLE computational science worlds

Each subenvironment lives in its own `env/<name>/` package. All experiments,
measurement noise, interventions and verification run in computation. No physical
laboratory or external simulator service is required.

| World | Observable system | Experimental controls | Main scientific scope |
|---|---|---|---|
| `microecology` | Three strains and anonymous extracellular fractions | Inocula, nutrient, temperature, fraction depletion and feed pulses | Mediated effects, delayed feedback, changing effect signs |
| `coupled_oscillators` | Positions and velocities of four masses | Initial kicks, cuts, mass/damping, clamps and forcing | Coupling structure, response, damping and transfer |
| `reaction_kinetics` | Four chemical concentration trajectories | Mixtures, temperature switches and additions | Reaction pathways, reversible transfer and temperature dependence |
| `heat_transport` | Three temperature probe trajectories | Heating, boundaries, flow, cooling and probe locations | Transport, loss and material heterogeneity |
| `gene_regulation` | Four bounded expression trajectories | Regulatory drives and timed pulses | Nonlinear feedback, thresholds, adaptation and memory |
| `ising_spin` | Six spin means and fifteen pair correlations | Temperature, fields, clamps and bond suppression | Collective equilibrium response, interactions and frustration |
| `hysteresis_material` | One response trajectory after a controlled history | Reset sign, preparation, field ramps, dwells and return loops | Distinguishing delayed response from persistent preparation memory |
| `microecology_causal` (experimental) | Three strains and anonymous extracellular fractions | Inocula, nutrient, temperature, fraction depletion and feed pulses | Competing causal accounts, intervention responses and restricted identifiability |
| `orbital_dynamics` (experimental) | Position and velocity of a body in a central field | Initial radius/velocity and timed impulses | Force-law ambiguity, dissipation and transfer beyond a circular trajectory |
| `pattern_formation` (experimental) | Sixteen probes on a periodic scalar field | Initial modes, ring length and uniform drive | Mode growth, forcing, symmetry and partial observability |
| `electrical_impedance` (experimental) | Quadrature voltage at a sealed linear one-port | Frequency, source resistance, parallel load and amplitude | Spectral response, resonance, relaxation and nonunique internal topology |
| `spin_echo` (experimental) | Mean classical magnetization x/y/z | Initial vector, waiting times, ideal rotation pulses and detuning | Reversible dispersion, transverse loss, finite-ensemble response and limited identification |
| `population_drift` (experimental) | Four expectation readouts of finite two-type population ensembles | Population size, preparation, reproductive bias and newborn-label controls | Drift, selection, mutation, current boundary occupancy and limited identification |
| `molecular_forces` (experimental) | Energy and Cartesian forces for three particles | Geometry and temperature | Pairwise versus collective dependence, geometric transfer |
| `climate_response` (experimental) | Surface temperature and energy imbalance | Annual forcing histories | Fast/slow response, hidden storage and feedback limits |
| `catalyst_aging` (experimental) | Instrument signal along a full ordered laboratory schedule | Coupon reuse, reaction conditions, blanks and standards | Irreversible aging versus instrument drift |
| `field_ecology` (experimental) | Detection fractions from replicated ecological panels | Habitat strata and repeated survey methods | Occupancy versus missed detection |
| `phase_equilibria` (experimental) | Diffraction intensity from prepared binary mixtures | Composition, preparation, finite hold, loading and scan angles | Mixture structure versus finite preparation history |

These five additions use the [new prospective research workflow](FRONTIER_RESEARCH.md):
one or two frozen predictive accounts, fresh observations and explicit uncertainty.
They are exploratory prototypes, with numerical checks but no strong-baseline
difficulty calibration. Their new GPT cohort is separate from historical scores. The [self-contained HTML report](../docs/reports/sle-new-frontier-20261003/index.html) presents the repaired workflow; the [original workflow report](../docs/reports/sle-new-frontier-20261003/original.html) preserves its failures and evidence separately.

These are synthetic, deliberately tractable scientific families. Hidden
parameters and structures create new instances, but do not by themselves prove
resistance to contamination or discovery of new scientific principles. Finite
Ising systems are not thermodynamic phase transitions; simulated microbes are not
calibrated organisms. Each environment documents its own limitations.
The [public-prior inventory](PUBLIC_PRIORS.md) records which governing families
were explicitly supplied in the completed GPT cohorts.

The initial formal pilot uses the first four environments. Gene regulation and
Ising and material history use a separate expansion cohort. Task orientation is separate from the world:
`open_discovery`, `mechanism_discrimination`, `regime_transfer`, `model_revision`,
and `boundary_mapping`; see [TASKS.md](TASKS.md).
Material instances vary the hidden mechanism class under the same public
instrument contract. This is an initial structural variation, not a tested
out-of-family or contamination-resistant benchmark.

The eighth world, [microecology_causal](microecology_causal/README.md), is registered
for explicit experimental selection. Its hidden causal structures share one
public batch instrument contract. Independent development review has checked
conservation and several limits of causal identification; registration does not
certify difficulty or mechanistic discovery.
It is outside the completed core/expansion cohorts and the existing seven-world
null calibration. Its separate offline development evidence is documented in
[operator notes](microecology_causal/SCIENTIFIC_NOTES.md).

The ninth world, [orbital_dynamics](orbital_dynamics/README.md), is also available
only for explicit experimental selection. Independent numerical checks and
matched circular-orbit examples distinguish apparent agreement from identified
force laws. Its private development calibration remains separate from GPT
results. The public 0.25 T claim lag excludes assigned initial/event values;
it is a pilot rule, not evidence of scientific discovery or detectability.

The tenth world, [pattern_formation](pattern_formation/README.md), defines a
64-site discrete laboratory observed through sixteen probes. Its finite-grid
semantics and several symmetry and growth limits have been reviewed. Probe
aliasing and exact-zero preparations can conceal internal dynamics. Numerical
work can fail explicitly; registration does not certify the full internal
parameter domain or promote its development scores to model results.

The eleventh world, [electrical_impedance](electrical_impedance/README.md),
measures independent sinusoidal steady states. Frequency is a control axis, not
elapsed time; it has no assigned initial readout or temporal-lag rule. Finite
passive circuits can share an identical port response, so accurate spectral
prediction need not identify an internal topology. Its prototype checks and
experimental registration are separate from the completed GPT cohorts.

The twelfth world, [spin_echo](spin_echo/README.md), exposes a bounded classical
magnetic ensemble with ideal instantaneous rotations. Static dispersion can
refocus while transverse loss remains, but finite mean-vector observations do
not uniquely identify an internal ensemble. Its 1 ms public claim lag and
known-coordinate exclusions are administrative guards, not detection or
discovery guarantees. It is outside the frozen GPT cohorts and the audited
seven-world null bank; prototype research and integration smoke tests are separate.
The [fixed reference study](spin_echo/REFERENCE_RESULTS.md) checks public-data
prediction with disclosed author priors and preserves plain-interpolation ties.
It is separate from model performance and does not establish a noise floor.

The thirteenth world, [population_drift](population_drift/README.md), measures
finite-ensemble expectations rather than individual random trajectories.
Boundary channels are current occupancies, including escape when permitted;
Gaussian sensor noise is distinct from the internally averaged drift. Fixed
public-readout checks passed, while two strict independent full-distribution
comparisons remain unresolved and are retained in its notes. Its public 0.25
replacement-clock-unit lag is an administrative eligibility rule. Experimental
registration and native engineering checks do not certify global numerical
accuracy or scientific difficulty.

An additional [optical diffraction prototype](optical_diffraction/STATUS.md)
has bounded coherent-scattering calibration and an isolated public-coordinate
policy. It remains **unregistered**, with no shared scoring route or GPT result.
It is not included in the eighteen registered worlds above. The angle-axis scoring,
equivalent-condition checks and actual agent service still require integration.

## Interfaces

[CONTRACT.md](CONTRACT.md) defines the operator-only `World` API, observation
format, public baseline and frozen submissions. The model receives only the
public description and its noisy experiment records. Simulator source, instance
seeds, test panels and private outcomes stay outside its sandbox.

Shared files directly under `env/` provide the registry, runner, SQLite request
ledger, verifier and HTML reporter. An experiment begins from a fresh preparation
inside the same fixed instance. The original persistent microecology laboratory
remains available with `python -m env.microecology`.

## Running a frozen cohort

Use a Linux machine with Bubblewrap, NumPy and SciPy. The existing SLE candidate
sandbox isolates analysis and predictions; there is no unsandboxed fallback.
The JSON model configuration is an operator-owned file outside Git.

```sh
python -c 'from env.ledger import CampaignLedger; CampaignLedger("/private/campaign/campaign-ledger.sqlite", 352)'
python -m env freeze \
  --cohort core-a1 \
  --environments microecology,coupled_oscillators,reaction_kinetics,heat_transport \
  --instances 5 --rounds 16 --exploration-rounds 14 \
  --task-profile open_discovery --output /private/campaign/core-a1-manifest.json
python -m env run \
  --manifest /private/campaign/core-a1-manifest.json \
  --config /private/model.json --campaign-root /private/campaign \
  --workers 8 --rpm 60
python -m env report /private/campaign/core-a1
```

The current pilot CLI explicitly requests `gpt-5.6-sol`, medium reasoning, 8,000
output tokens, non-streaming Chat Completions and no temperature. Configuration
must match the frozen manifest. This is an explicit pilot condition rather than
an API default or a model capability claim.

Freeze and run from the same immutable source checkout/archive. Changing source
invalidates a manifest; do not replace its hash to resume an old cohort. Every
network attempt is charged to one shared campaign ledger, including failures and
uncertain timeouts. HTTP requests are never automatically retried. Existing
cohort directories are not overwritten. A deliberate replacement run needs a new
cohort ID, recorded reason and enough remaining budget; failures remain visible.

`--presentation-profile apparatus_only` with oscillator/Ising environments reduces
equation-family hints; the default is `full_description`. Public action semantics
and the scoring rules remain visible. Family-informed baselines are not blind
controls. `--balanced-strata hysteresis_material` uses its trusted operator strata
to balance hidden mechanism classes before freezing; the private labels are never
included in the agent's problem. The experimental `microecology_causal` and
`orbital_dynamics`, `pattern_formation`, `electrical_impedance`, `spin_echo` and `population_drift` worlds also support this option when explicitly selected. Multiple selected worlds may be
comma-separated. Both settings are stored in the cohort manifest.

Future cohorts may explicitly use `--analysis-protocol sle-analysis-snapshots-0.1`
to enable named immutable parameter/code snapshots; see [MODEL_SNAPSHOTS.md](MODEL_SNAPSHOTS.md).
The default remains `legacy`. The exact snapshot contract and instance selection
are frozen in the manifest; old cohorts do not acquire this capability.

[PROSPECTIVE.md](PROSPECTIVE.md) describes a separate task executor that seals
competing predictions before obtaining new measurements, retains counterexamples,
and supports a new test after model revision. It uses the same Linux isolation
boundary and makes no model API calls by itself. Its outputs are evidence for
scientific review, not automatic D3/D4 scores.

[DOMAIN_MAPPING.md](DOMAIN_MAPPING.md) adds a separate experimental operator
executor for one frozen model on a finite ordered grid. It reports adequate,
inadequate, inconclusive and incomplete points against a justified tolerance,
without requiring a second rival or claiming a continuous boundary. Independent
code review, a native isolation gate and one bounded orbital author-reference
execution are complete. Its finite map contains two adequate and four inadequate
points under a fixed precision target; it is not yet an agent action in the
research runner or a GPT evaluation.

`report.json` and `manifest-private.json` contain private test material and full
transcripts. Keep them outside Git and candidate access. `summary.json` is a
compact aggregate; inspect any export before publishing. `index.html` links to
local raw records for operator review.

`python -m env.progress_report --cohort formal=/private/campaign/core-a1
--notes /private/curated-public-notes.json --output /public/progress` produces a
self-contained HTML and allowlisted aggregate JSON without raw targets or seeds.
Inspect curated notes before publishing. The normal per-cohort report remains
an operator artifact because it links to raw reports.
Public export is read-only on the source cohorts. A sanitized
[pilot progress report](../docs/reports/sle-env-pilot-20261003/index.html) is included
with separate core, expansion and development results.

For executable research before a final answer, see
[RESEARCH_RUNNER.md](RESEARCH_RUNNER.md): the experimental model interaction
supports source experiments, isolated fitting, model snapshots, frozen rival
predictions, independent observations and revisions. Its prospective evidence
has no automatic mechanism label or discovery-depth score. This new interface
has not yet received a live GPT benchmark run.
The [material reference example](hysteresis_material/RESEARCH_DEMO.md) exercises
that interface with an explicitly authored zero-API policy and immutable rival
snapshots. Its outcomes are reference-policy results, not model performance.

[PAIRED_DESIGN.md](PAIRED_DESIGN.md) generates future single-factor comparison
plans without launching requests. [PREDICTABILITY_DIAGNOSTICS.md](PREDICTABILITY_DIAGNOSTICS.md)
compares existing paired candidate/baseline errors;
[PREDICTION_DIAGNOSTICS.md](PREDICTION_DIAGNOSTICS.md) separates values assigned
by public controls when complete prediction matrices exist.
[CLAIM_PROTOCOL_FUTURE.md](CLAIM_PROTOCOL_FUTURE.md) keeps proposed interval-loss
and effect-significance changes disabled while their assumptions are calibrated.
None changes historical model scores.

[EVIDENCE_PACKET.md](EVIDENCE_PACKET.md) exports a separate review packet from
recorded public interactions. It preserves original public task context and
candidate reasoning while excluding operator score/identity/target metadata.
These packets document evidence gaps and do not themselves replay experiments,
authenticate time, or assign a discovery depth.
[DISCOVERY_EVIDENCE.md](DISCOVERY_EVIDENCE.md) adds manual, per-dimension judgments
with exact packet anchors and recorded-order checks. It preserves disagreements
without computing a depth grade or certifying the scientific interpretation.

[Analysis failure replay](../ANALYSIS_REPLAY.md) reconstructs archived public
analysis inputs in the Linux sandbox for a separately frozen diagnostic. It
preserves original time limits and results. Matching error types and enhanced
messages can narrow a diagnosis; replay does not prove the original cause or
change the model score.

## Evaluation and extension

[AUTHORING.md](AUTHORING.md) gives the current package layout, integration points,
bounded development procedure and distinction between prototype, experimental
registration and frozen model evaluation.

[EVALUATION.md](EVALUATION.md) specifies scores, denominators, evidence grades and
limitations. Add an environment by implementing the contract, writing independent
numerical checks, exposing a public-data-only baseline, then registering its name
and public claim-eligibility policy. Include it in task applicability and offline
calibration, and verify privacy/shape/finite-output invariants before API trials.
Run offline calibration on development seeds before freezing paid test cohorts.

```sh
python -m pytest env tests/test_runtime_shared_libraries.py
```

World tests run on macOS or Linux. The actual process/filesystem/network boundary
must also be tested on the Linux execution host, where the full security tests
should pass without platform skips.

## New unregistered prototypes (2026-10-05)

`adaptive_signaling` studies intervention identifiability of matched adaptive systems; `retention_transport` studies flow-history discrimination of retention and parallel passage. Both implement the trusted World interface and have bounded local numerical/reference checks, but are **not registered**, not available to the shared research runner or MCP, and not part of any model score. See [screening decisions](HARD_ENV_SCREENING.md) and the [development report](../docs/reports/environment-expansion.html). Formal admission needs shared adapters and broader calibration; local feasibility does not certify high difficulty.
