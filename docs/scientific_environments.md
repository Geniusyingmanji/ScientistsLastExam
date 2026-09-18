# Scientific discovery environments: evidence workflow and construction controls

The `sle episode` command defaults to **ground-truth-free evidence review**.
It supports multiple rounds of competing hypotheses, preregistered tests,
tool observations, isolated analysis and revisions, then freezes a dossier before
opening reserved measurements. Operational evidence checks are separate from
independent scientific review; no discovery score is inferred from prose or logs.
See the [primary discovery protocol](discovery_evaluation.md).

`DiscoveryEvidence/MeasurementAudit` accepts an operator-supplied measurement
bundle with provenance and a sealed data partition. It has no hidden mechanism,
generator or correctness evaluator. The bundled hand-entered example is strictly
a protocol fixture. Run it without an API call:

```sh
python -m sle episode --task MeasurementAudit --baseline protocol \
  --output-dir /var/tmp/sle-discovery-protocol
```

Five environments remain outside the admitted legacy task registry. The four
earlier synthetic environments support **explicit oracle construction diagnostics**:

- `CausalDiscovery/CausalTransportDiscovery`: reconstruct continuous dose-response
  curves across biomarker groups from costly, selectively assayed interventions;
  transport them to fresh population mixtures with honest uncertainty. Source
  observations alone cannot distinguish paired worlds. Missing bridge support
  requires partial identification, rather than a guessed point estimate.
- `SystemsBiology/EnzymeRecoveryDesign`: design loading, washout and rescue
  experiments under optical nuisance effects; distinguish reversible recovery
  from irreversible loss, and predict fresh conditions. Effective model complexity
  is a separate question from fitting a curve or guessing the generator's label.

The earlier prototypes remain available as controls:

- `CausalDiscovery/SurvivorshipAuditDesign`: population effects under direct
  treatment-dependent selection, stratification and paid random follow-up.
  **Historical control**: fixed-cell estimation is already a strong solution.
- `SystemsBiology/EnzymeMechanismDiscovery`: compositional dynamical mechanisms,
  costly measurements and perturbations, then fresh trajectory confirmation.
  **Protocol-only**: fixed experimental designs still recovered all mechanisms
  and passed all confirmations across the 60/80/104-unit budget study. It is not
  a sufficiently difficult replacement for the retired enzyme task.

These are **not frontier-qualified tasks**. The successors are construction
candidates: a more demanding contract does not by itself establish frontier
model difficulty. Strong fixed designs, prior-only predictions and redundant
high-order fits must remain visible in construction results. Repeated model
calibration and independent scientific review are still required.
Six saturated or shortcut-compromised legacy tasks are held by the separate
[eligibility policy](discovery_eligibility.md).

## Run without a model

```sh
python -m sle episode --list
python -m sle episode --task SurvivorshipAuditDesign --evaluation-mode oracle --baseline reference \
  --output-dir /var/tmp/sle-survivorship-reference
python -m sle episode --task EnzymeMechanismDiscovery --evaluation-mode oracle --baseline fixed \
  --output-dir /var/tmp/sle-enzyme-fixed
python -m sle episode --task CausalTransportDiscovery --evaluation-mode oracle --baseline reference \
  --output-dir /var/tmp/sle-transport-reference
python -m sle episode --task EnzymeRecoveryDesign --evaluation-mode oracle --baseline reference \
  --output-dir /var/tmp/sle-recovery-reference
```

Each output directory must be new, owner-only and outside every Git checkout.
Use `/private/tmp/...` on macOS. Full reports contain private world seeds,
outcomes and observations. Console output is a status/resource summary.

An operator-reviewed baseline uses only the public problem and experimental
callback, but executes inside the operator process; this mode is for construction
diagnostics. Candidate programs always use the Linux sandbox:

```sh
python -m sle episode --task SurvivorshipAuditDesign --evaluation-mode oracle --program candidate.py \
  --seed 8173 --max-steps 64 --wall-seconds 300 \
  --output-dir /var/tmp/sle-program-example
```

The self-contained program defines `solve(problem, experiment)`, where
`experiment(tool_name, arguments)` returns the tool observation. The runner
commits its returned claim. Oracle files and private seeds never enter its
workspace. NumPy/SciPy availability follows the existing CandidateProxy runtime.

## Run a model with experiment feedback

```sh
python -m sle episode --task MeasurementAudit --data-bundle /private/operator/study \
  --llm-config /private/config/model.yaml --analysis sandbox \
  --seed 9281 --max-steps 32 --wall-seconds 600 --experiment-budget 20000 \
  --output-dir /var/tmp/sle-interactive-example
```

This uses the existing SLE model configuration and transport. Credentials stay
in the operator configuration, outside source and agent observations. Each model
response must be one JSON action. The default evidence mode additionally supports
`hypothesize`, `revise_hypothesis` and `plan_test`, with the complete schemas in
the initial observation and [discovery protocol](discovery_evaluation.md):

```json
{"action":"experiment","tool":"public tool name","arguments":{}}
```

```json
{"action":"analyze","code":"result = 1 + 1"}
```

```json
{"action":"commit","claim":{"task-specific":"public claim schema"}}
```

The initial problem gives exact tool parameters, costs and claim schemas.
In evidence mode, the final claim is an evidence dossier with registered
replication tests; it does not use the legacy simulator's answer schema.
`analyze` runs in a persistent, single-process CandidateProxy sandbox. It can
read the JSON variables `problem`, `history`, and the explicitly allowlisted
`public_files`. For the enzyme pilot, `public_files['model.py']` supplies the
public numerical model; the agent may execute it inside its sandbox. Assign a
JSON-serializable value to `result`; captured output is bounded. Python never
executes in the trusted environment process. Linux/bubblewrap is required and
failure does not fall back to host execution. `--analysis none` explicitly
selects an experiment-only model condition.

## Paired construction controls

```sh
python -m sle episode-panel --task CausalTransportDiscovery \
  --policies reference fixed abstain --worlds 24 --seed-start 1000 \
  --metric curve_rmse --output-dir /var/tmp/sle-transport-panel
python -m sle episode-panel --task EnzymeRecoveryDesign \
  --policies reference fixed_optical fixed_orthogonal abstain --worlds 24 \
  --seed-start 1000 --output-dir /var/tmp/sle-recovery-panel
```

This runner executes only trusted, explicitly registered construction policies;
it makes no model API calls and is explicitly an oracle diagnostic, not the
no-GT evidence evaluation route. It uses the same generated world and budget cap for
every policy, resets each policy between worlds, and records actual expenditure.
Equal caps do not imply equal spending. `--budget-units` can override the cap for
a construction study; policies must support the chosen cap or report a budget
failure. A failed cell is not a zero scientific score.

Private `panel.json` binds source/runtime hashes and each individual episode.
Initialization failures have separate private failure records. Source changes
during execution invalidate the aggregate. Scalars are reported separately;
rates pool their numerators and denominators, with zero denominators remaining
null. Explicitly invalid metrics are excluded. Optional paired differences use
only the valid intersection and report how many pairs actually spent equally.
Paired worlds may share generator families: they are not independent model draws
and these descriptive comparisons do not establish statistical significance.

### Successor construction check (2026-09-18)

A separate 24-world source-bound transport panel completed all 216 cells. Six
experimental policies each spent exactly 12,000 units per world; prior-only,
bounds-only and abstention controls spent zero. Sixteen worlds had complete
support and eight required partial identification. On the complete-support
worlds, the joint precision condition gave:

| Policy | Joint success | Mean target-population RMSE |
|---|---:|---:|
| Reference recruitment policy | 12/16 | 0.01619 |
| Strong fixed source-plus-bridge design | 14/16 | 0.01565 |
| Fixed all-bridge factorial design | 8/16 | 0.01914 |
| Random bridge design | 11/16 | 0.01703 |
| Source extrapolation | 0/16 | 0.03829 |
| Zero prior, no observations | 0/16 | 0.03183 |

Source-only, bounds-only and full-abstention controls also achieved 0/16 joint
success. All four strong designs still resolved 36/36 scorable modifier
decisions: this component remains easy. Fixed design outperformed the reference
on this panel; no adaptive advantage is claimed. The declared joint precision
target adds quantitative requirements, but these are synthetic accuracy targets,
not clinical standards or evidence of frontier-model difficulty.

Private panel content binding:
`832f13506f6bc8b6bd5cc93387c864f182b5026ea4dc85cb99cb7cd6fa29871b`.
Full episode records remain outside Git. The task's separate public construction
report uses different worlds and binds its listed task source files; neither
panel contains frontier-model draws.

The recovery successor completed a separate 24-world, ten-policy panel (240
completed cells). All seven experimental policies spent exactly 48 units;
no-query and abstention controls spent zero. Scientific axes remain separate:

| Policy | Correct / certifiable components | Mean confirmation RMSE | Worlds with a predictor |
|---|---:|---:|---:|
| Reference | 42/45 | 0.00370 | 24/24 |
| Fixed mixed-readout design | 43/46 | 0.00322 | 23/24 |
| Fixed optical design | 43/45 | 0.00248 | 23/24 |
| Fixed orthogonal design | 36/45 | 0.00563 | 24/24 |
| Passive single-condition design | 28/45 | 0.08749 | 24/24 |
| Always fit and claim maximum order | 24/45 | 0.00647 | 24/24 |
| No-query fixed prior | 24/45 | 0.12301 | 24/24 |

Prediction error alone would hide the maximum-order strategy's 21/45 false
component assertions. Conversely, fixed optical fitting remains very strong:
43/45 correct certifiable components does **not** establish frontier difficulty.
The oracle initially certifies order in 21/24 worlds; the mixed fixed predictor
provides an additional valid lower-order witness in one world, hence its 46th
certifiable component. Unresolved order is excluded from the recovery denominator
and reported as unresolved, rather than used to depress a combined score. No
combined score is emitted by this successor. Missing predictions are excluded
from RMSE and explicitly counted above.
This small panel initially contains 13 certified zero-order worlds, eight
certified one-order worlds and three oracle-unresolved worlds, with no certified
two-order world. Analytic and adversarial unit tests exercise two-order
certification, but broader stratified world coverage is still required for
difficulty calibration; this panel cannot establish success on that stratum.

Private recovery panel content binding:
`cd3a008c41c1f1689ee40032240f74714068d7a55e7f0d4fb000439b8e4358c7`.
Both successor panels are construction diagnostics. The old tasks remain held;
neither successor is admitted on the strength of these results.

Validation of implementation revision `1c07d94c`: the focused local suite passed
170 tests (13 Linux-only checks skipped on macOS); the Linux Python 3.8 run passed
all 226 selected tests with real CandidateProxy/bubblewrap execution, including
both successor tasks, panel aggregation, episode/deadline regressions, task
inventory/eligibility checks and the existing secure-evaluation/wrapper suites.
Scientific difficulty and external domain validity remain separate release gates.

The program and interactive-model modes share a scientific environment but are
different solver conditions. Record and compare them separately. Model steps,
experimental cost units, analysis calls and elapsed time are separate resources.
Malformed actions consume a step. Overspending does not run an experiment.
Claims committed after the agent deadline cannot be scored. Confirmation is an
operator-reserved phase after commitment, outside the exploration budget.
The standalone POSIX CLI enforces a total deadline around model transport,
including retries and streaming. Embedded interactive calls must run on the
main thread with no existing interval alarm; unsupported contexts fail closed.

## Evidence and verification

The trusted session records action/observation pairs, actual experimental charges,
the frozen claim hash, confirmation, and private review output (or oracle output
in the explicitly selected diagnostic mode). The
agent receives confirmation measurements but no oracle metrics. No experiments
or revised claims are accepted after commitment.

`episode.json` binds task source hashes, runtime source and installed package
versions, private world seed, solver mode and model condition, plus an ordered
hash chain. `validate_episode_report` checks structural consistency and resource
accounting. Hashes are content bindings, not signatures or proof of trusted
origin; they also do not prove that a scientific interpretation is valid.

Keep separate statuses for completed evaluation, incomplete delivery, invalid
candidate, model transport error, infrastructure error, exhausted budgets and
incomplete evidence. Only completed evaluations carry scientific metrics.
Each adapter defines mechanism, prediction, false-claim, refusal and coverage
metrics with their denominators. No cross-task scalar average is introduced.
For tasks with no intrinsically unidentifiable worlds, calibrated refusal is
unmeasured with a zero denominator, rather than automatically perfect.

## Adoption and release gates

The architecture adopts immutable source/runtime identity and numerical scientific
checks from [ScienceIDE](https://arxiv.org/html/2609.19134v1), active perturbation
and structural versus predictive evaluation from
[SciGym](https://arxiv.org/html/2507.02083v1), and separate process/outcome evidence
from [TRACES](https://www.apodex.com/blog/apodex-discovery). This is independently
implemented SLE code; it does not bundle ScienceIDE's unreleased task bank or
claim a Harbor/container integration that has not been implemented.

For each successor task, require: a public complete contract; independent oracle
checks; truthful construction provenance; a matched-budget shortcut panel;
fresh private worlds and confirmation; repeated model draws with named budgets;
and independent scientific review. The old saturated task remains held until
its successor passes these gates. Adding noise, renormalizing a full score, or
renaming a task cannot qualify it.

The next environment backend can support scientific repositories and compiled
simulators through a separate container adapter. That backend must pass correct
witness, nop, bad-artifact, timeout and verifier-failure anchors before collecting
model numbers. The current release implements the interactive experiment backend
and the existing secure Python analysis backend, with CPU-only scientific pilots.
