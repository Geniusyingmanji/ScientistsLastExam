# Microecology: the first SLE virtual scientific world

This is a working construction prototype: persistent batch cultures, three strains,
anonymous chemical assays, interventions, an evidence log, and fresh checks of
agent-chosen numerical predictions. It does not require wet experiments or model
API credentials. It is not yet a calibrated discovery benchmark.

## Try it

From the repository root, use a Python environment with NumPy, SciPy, PyYAML,
and Matplotlib (plots only). Pytest is needed for validation. Existing supported
SLE host environments already supply the numerical dependencies. The construction
run additionally records the exact installed runtime versions in its private report.

For an isolated environment, `python -m pip install '.[world]'` installs these
optional dependencies without changing the certified `host`/`oracle` extras.

```sh
python -m sle world describe
python -m sle world demo --seed 7 --output-dir /private/tmp/sle-microecology-demo
python -m sle world replay /private/tmp/sle-microecology-demo/operator-report.json
```

Use `/var/tmp/...` on Linux. Choose a **new** output directory outside Git
checkouts. Reports are owner-only; the operator report contains the private seed,
model parameters and channel mapping. Do not give it to a candidate or commit it.

The demo writes `index.html`, `trajectories.png`, `trajectories.svg`, `demo.json`,
`public-report.json`, and `operator-report.json`. Open `index.html` to inspect the
public trajectories and confirmation results. Output directories are never reused.

### Run your own experiments

```sh
python -m sle world run --seed 7 \
  --actions examples/microecology/explore.json \
  --output-dir /private/tmp/sle-microecology-explore

python -m sle world run --seed 7 --interactive \
  --output-dir /private/tmp/sle-microecology-interactive
```

Interactive mode prints the public description, accepts one JSON request per line,
and returns one JSON response per line. The same session persists until EOF or
completion. EOF during exploration saves an exploratory report, not a completed
scientific evaluation. The last output object has `kind: session_summary`.

```json
{"request_id":"prepare","operation":"create","arguments":{"biomass":{"A":0.06,"B":0.04,"C":0.06},"nutrient":4,"volume_ml":10,"temperature_c":30}}
{"request_id":"grow","operation":"advance","arguments":{"hours":12}}
{"request_id":"read","operation":"measure","arguments":{"vessel_id":"vessel-0001","instrument":"counts"}}
```

On a host with the existing SLE **Linux CandidateProxy sandbox** configured:

```sh
python -m sle world run --seed 7 \
  --program examples/microecology/candidate.py \
  --output-dir /var/tmp/sle-microecology-candidate
```

Candidate programs implement `solve(description, act)` and receive only the public
description and action callback. There is no host Python execution fallback.
The trusted demo itself runs on macOS/Linux and is clearly recorded as an
operator-written policy; its success is not a model result. The Python
`WorldSession` object owns private state and must never be passed directly to
untrusted agent code.

### Bounded model pilot

```sh
python -m sle world run --seed 731 \
  --llm-config /private/operator/model.json --analysis \
  --max-model-calls 32 --wall-seconds 1800 \
  --output-dir /var/tmp/sle-microecology-model
```

The model receives only the public tool description and its own experiment history.
Each response supplies a brief research note and up to 64 sequential JSON actions,
or isolated Python analysis. Batches stop at the first error. `--analysis` requires
the existing Linux sandbox and never falls back to host execution. A model turn
can freeze predictions; another turn can interpret fresh confirmation results.
The model is not given the demonstration policy, recipe, or expected discoveries.

The pilot allows 2–32 model requests, at most 8,000 output tokens per request, a
bounded wall time and prompt size, and **no automatic transport retries**. The
config supplies the existing endpoint/model/decoding choices. A fsynced JSONL
ledger records each started request before network I/O; its path cannot be reused.
The ledger never records authentication headers or endpoint URLs. `agent-report.json`
records visible replies, research notes, public actions, reported usage, stop
reasons and provider-reported model identifiers separately from the requested ID.
Missing usage and unknown pricing remain unknown. World reports are checkpointed
after every turn; incomplete episodes are not labeled successful discoveries.

For an existing Azure deployment, set the config's `base_url` to
`https://<resource>.openai.azure.com/openai/deployments/<deployment>` and the
`model` to that deployment name. `--azure-api-version <version>` preserves the
deployment API version. `--azure-cli-auth` uses the host's existing `az` login,
keeps the token only in memory, and checks that it outlives the episode deadline.
No credentials are written to the reports or model prompts.

### Evaluation roadmap and first bounded comparison

The next steps are, in order:

1. Complete the exploration → frozen claims → fresh confirmation → interpretation
   cycle, and record forecast precision separately from effect-band consistency.
2. Add frozen executable predictions on unseen legal experimental conditions;
   evaluate on a fixed test panel separately from adaptive counterexample search.
3. Add mechanism-discrimination and temporal-response claims, then calibrate
   domain-specific Discovery Depth evidence requirements with controlled baselines.
4. Expand to unpublished mechanism structures and independent world families;
   parameter changes alone do not establish resistance to memorization.

Step 1 is implemented by `paired-effects-v2`: up to three primary claims, each
with eight sensor-noise replicates per arm, cited exploration evidence and a
central 90% predictive interval for the **mean** treatment-control measurement
difference. `forecast` is separate from the legacy `expected_difference` effect
band. The interval score is width plus 20 times the distance of the realized
mean outside the interval, in mmol C/L; lower is better. Report width, coverage
and score together. These descriptive scores concern agent-selected experiments;
they are not an interchangeable common-task score across agents. Neither one
confirmation batch nor three worlds establishes probabilistic calibration.

```sh
python -m sle world run --seed 1439 --budget 800 \
  --llm-config /private/operator/model.json --analysis \
  --max-model-calls 16 --exploration-rounds 10 \
  --evaluation-profile paired-effects-v2 --wall-seconds 900 \
  --output-dir /var/tmp/sle-microecology-eval

PYTHONPATH=. python examples/microecology/evaluate_gpt.py \
  --llm-config /private/operator/model.json \
  --output-dir /var/tmp/sle-microecology-gpt56-campaign
```

The operator launcher predeclares three new instances and a total cap of 48 API
attempts, including failures. Requests are sequential, with no automatic retries.
After ten model turns, the driver admits only `commit` until it succeeds, then
only `interpret`; it never fabricates claims. Each episode and its exact replay
are saved, including incomplete episodes. The campaign directory cannot be reused.
Mechanisms, novelty, unseen-condition generalization and Discovery Depth remain
unassessed by this first profile.

## World and experimental semantics

- Mechanism and parameters are fixed within an instance and all its confirmation
  cultures. Repeated experiments do not redraw the biological rules.
- Eight internal carbon pools obey a conservative ODE. A nutrient pulse imports
  carbon; depletion, filtration and displaced medium export carbon. All these
  flows are accounted. The pulse idealization has negligible volume.
- Vessels are finite batches. There is no hidden continuous nutrient inflow.
- Only `advance` moves the global simulated clock, advancing **all** cultures and
  detached samples. Thinking or reading does not grow the organisms.
- `create` prepares fresh cultures from standard stocks; `sample` consumes donor
  volume and records a child sample. Cell-free filtration removes all three
  strains. Samples continue evolving under their recorded temperature.
- `transfer` filters donor material and replaces an equal receiver volume. It
  removes donor volume, discards the receiver's displaced contents, and dilutes
  the receiver's cells. A transfer effect alone therefore does not isolate a
  chemical cause; appropriate dilution controls are needed.
- `measure` returns noisy, non-destructive biomass, nutrient, or chemical data.
  Chemical fractions have stable anonymous IDs within a world; their mapping is
  permuted across worlds. `deplete` is idealized selective fraction adsorption,
  not a realistic assay of unknown molecular identity.
- Dynamics are deterministic in v1. Measurement noise is independent Gaussian
  noise clipped at zero. Replicate confirmation varies sensor noise, **not**
  biological dynamics or model parameters. Near zero, clipping biases readings.
- Costs apply per physical operation and vessel-time, not just per tool call.
  Exploration and reserved confirmation have separately disclosed caps. Invalid
  valid-envelope requests consume a step but do not mutate the world or consume
  experiment units. Reusing a request ID with the identical request is idempotent.
- State-changing operations are atomic. Numerical failure rolls back the entire
  operation and stops the session as an infrastructure failure, not a false claim.

## Open claims supported in this version

`commit` accepts up to six `paired_effect` claims. Each defines a common initial
preparation, control/treatment schedules, an endpoint species and time, a numerical
interval for the treatment-minus-control effect, and 4–12 sensor-noise replicates.
Schedules currently support feeding, fraction depletion and temperature changes.
The statement and experiment are agent-chosen; there is no list of golden findings.

Commit freezes the **entire claim batch**, then new preparations execute the
declared experiments with the same underlying world. The verifier computes the
mean contrast and an approximate Student t interval, with alpha divided by the
number of claims in this batch. An interval wholly within the prediction is
`prediction_supported`; a disjoint interval is `prediction_refuted`; overlap
without containment is `inconclusive`. This approximate procedure is not a formal
FDR guarantee, especially near clipped readings. Selection among many exploratory
claims, multiple batches, and model-family uncertainty need further treatment.

All raw confirmation actions and observations are retained, including refutations.
After confirmation only one `interpret` action is accepted, bound to the frozen
claim hash. It cannot modify the claim or obtain more experiments. The interpreter
text is preserved but not automatically scored for scientific quality.

These checks validate only the declared **numerical contrasts**. They do not
certify that the prose faithfully describes them, identify a unique mechanism,
prove generalization, or award Discovery Depth. Empty/degenerate claims do not earn
a discovery score; there is no aggregate score in this prototype. More expressive
claims and independent counterexample searches are future extensions.

## What the demonstration does

Seven preparations compare A, AB, AC, ABC, and ABC with each anonymous fraction
depleted at 8, 12, 16 and 20 hours. Every vessel gets identical nutrient pulses
of 0.02 mmol C at 16 and 20 hours. Counts and chemistry are measured every two
hours through 32 hours.

The policy selects the fraction with the largest **observed** C rescue at 24 h;
it does not inspect the hidden channel mapping. It freezes the explored C and A
effects, tests whether the A effect vanishes when C is absent, and includes a
deliberately reversed C prediction as a verifier negative control. New experiments
then check all four claims. The missing-C control tests one necessary implication
of mediation; this is not sufficient to recover the whole feedback loop uniquely.

The feeding schedule matters: in an exhausted batch, removing inhibition need not
increase A biomass because nutrients can already be limiting. The demo's stated
scope includes both nutrient pulses. No sustained oscillation is promised.

## Implementation and extension boundaries

| Module | Responsibility |
| --- | --- |
| `sle/microecology_kernel.py` | Immutable mechanisms and conservative ODE evolution |
| `sle/microecology_lab.py` | Vessels, samples, interventions, instruments and material ledger |
| `sle/world_protocol.py` | Bounded JSON, public errors, event chain and identifiers |
| `sle/world_session.py` | Budgets, idempotency, freeze/interpret states and replay |
| `sle/microecology_verification.py` | Fresh checks of declared numerical contrasts |
| `sle/microecology_demo.py` | Trusted public-action construction demo and plots |
| `sle/world_cli.py` | JSONL, action files and existing sandbox adapter |

The CLI is registered as `sle world`; legacy episode modes and task registries
are unchanged. `world.json` documents the package; it is not a dynamic code-loader
or a claim that all future domains already fit this adapter. A second domain
should test and refine the generic boundary before freezing a plugin SDK.

Exact replay checks the private recipe, source file hashes, Python/NumPy/SciPy
versions and every event. Hashes bind contents, not independent scientific truth.
Cross-runtime portability should use declared numerical tolerances rather than
requiring bit equality; this prototype only exposes exact matching-runtime replay.

## Validation and remaining work

```sh
python -m pytest tests/test_microecology_world.py -q
```

Tests cover independent Radau/DOP853 solver agreement, nonnegative conservative
dynamics, extinct species, physical transfers, noise independence, global clock,
transactional rollback, resource limits, idempotency, private/public separation,
novel numerical claims and their opposites, freeze boundaries, tamper detection,
exact replay, and the C-dependent rescue demonstration.

Still unvalidated: frontier-model difficulty, structural anti-contamination,
stochastic biological replication, calibrated scientific depth, arbitrary new
claim semantics and mechanistic identifiability over the whole family. Parameter
jitter and channel permutation alone do not establish contamination resistance.
The selective instruments and invented kinetics are deliberately simplified.
