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

These are synthetic, deliberately tractable scientific families. Hidden
parameters and structures create new instances, but do not by themselves prove
resistance to contamination or discovery of new scientific principles. Finite
Ising systems are not thermodynamic phase transitions; simulated microbes are not
calibrated organisms. Each environment documents its own limitations.

The initial formal pilot uses the first four environments. Gene regulation and
Ising and material history use a separate expansion cohort. Task orientation is separate from the world:
`open_discovery`, `mechanism_discrimination`, and `regime_transfer`; see [TASKS.md](TASKS.md).
Material instances vary the hidden mechanism class under the same public
instrument contract. This is an initial structural variation, not a tested
out-of-family or contamination-resistant benchmark.

The eighth world, [microecology_causal](microecology_causal/README.md), is registered
for explicit experimental selection. Its hidden causal structures share one
public batch instrument contract. Independent mechanism-design review remains
pending; registration does not certify difficulty or mechanistic discovery.
It is outside the completed core/expansion cohorts and the existing seven-world
null calibration. Its separate offline development evidence is documented in
[operator notes](microecology_causal/SCIENTIFIC_NOTES.md).

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
included in the agent's problem. The experimental `microecology_causal` world also
supports this option when explicitly selected. Multiple selected worlds may be
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

## Evaluation and extension

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
