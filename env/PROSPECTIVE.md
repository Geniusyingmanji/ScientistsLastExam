# Prospective evidence packages

`env/prospective.py` provides the evidence protocol, and the standalone
`env/prospective_runner.py` executes it through the existing `CandidateProxy`
sandbox. Together they turn two task-profile requirements into replayable
evidence: rival predictions recorded before a
discriminating experiment, and source-derived predictions tested in another
regime. Its protocol is `sle-prospective-evidence-0.1`. It does not modify the
runner, campaign, scoring, task-profile catalog or frozen core pilot.

The operational question is narrow: **Did two frozen predictors make sufficiently
different predictions for this preselected readout, and did fresh measurements
place one prediction within a small declared tolerance while excluding the
other?** This is a numerical comparison of specified predictors. It is not
identification of a mechanism, proof of a theory, or a measure of discovery depth.

## Why the current profile text needs this layer

`mechanism_discrimination` already asks for at least two plausible mechanisms,
predictions before the discriminating result, targeted observations and an
identifiability assessment. An explanation written after the episode cannot
establish that timing or show what a rejected account actually predicted.

`regime_transfer` already asks for a source-fitted relation, a prospective target
prediction and an assessment before refitting. A model fitted independently to
the target can otherwise be narrated as transfer.

This module freezes executable artifacts and full numerical outputs, records
the experimental plan before collecting any confirmation data, and preserves
counterexamples and later revisions. Scientific review still determines whether
the rivals were plausible, differ mechanistically, use a meaningful regime
change, and address an informative readout rather than a value fixed by a public
control. The module does not certify those judgments.

## Minimal protocol

An operator creates one bounded `ProspectiveSession` with public metadata and
four trusted callbacks. A candidate supplies one request containing:

- `profile`: `mechanism_discrimination` or `regime_transfer`.
- `scope`: the conditions and scientific claim being tested.
- Exactly two `rivals`, each with an ID, self-contained `predictor_code` defining
  `predict(spec)`, rationale, prior observation `evidence_ids`, and a numerical
  tolerance for the primary readout.
- One or two distinct legal `experiments`, each with an ID, `target` or
  `reference` role, and public spec. At least one must be a target.
- One primary `readout`: one to four preselected weighted row/channel terms.
  Every experiment must contribute. Weights are nonzero and in [-1, 1].
- A fixed `replicates` count in [4, 16]. There is no early stopping or increasing
  the count after seeing results.
- `revision_of` and `change_note`: null and empty for an initial test, or an
  explicit link to a completed counterexample when refining a predictor.

The primary quantity is `q = sum(weight * value / public_channel_scale)`. Thus a
treatment-minus-reference contrast uses weights +1 and -1; a single-channel
forecast uses one term. Code must return the entire normal values array for
each experiment. The registration stores those full arrays even though the
declared comparison uses only its primary scalar readout. This endpoint says
nothing about unselected channels or the rest of a trajectory.

Registration validates the plan against the operator's observation history,
executes each rival twice through the supplied isolated executor, and rejects
nonfinite, malformed or nonreproducible outputs. It freezes source code, source
hashes, complete predictions, prediction hashes, cited evidence, all prior-record
hashes, the public observation contract, runtime ID, experiment specs, readout,
tolerances, replication count and statistical rule. A durable registration event
must be acknowledged before collection is permitted.

Collection executes the entire fixed plan with operator-generated independent
noise keys. It saves every valid response, then computes a result from the
frozen predictions and observations. Failed registration or collection attempts
remain in the session and reserve their share of the test budget. A partial
collection has no scientific decision and cannot be retried. No user timestamp,
confirmation key or submitted observation can authorize collection.

## Statistical rule and tolerance safeguards

The operator supplies the publicly documented channel scales, noise standard
deviation upper bounds, and bounds on measurement-mean bias relative to the clean
response. None is chosen by the candidate or estimated from the selected result.

For primary terms belonging to experiment e, define:

```text
L_e = sum_terms_in_e abs(weight) * noise_std[channel] / scale[channel]
V   = sum_experiments L_e^2
B   = sum_all_terms abs(weight) * mean_bias_bound[channel] / scale[channel]
alpha_test = family_alpha / max_tests
r = B + sqrt(V / (replicates * alpha_test))
C = [mean_observed_q - r, mean_observed_q + r]
```

`V` allows arbitrary correlation between terms within one experimental response.
Distinct experiments and replicate runs must have independent measurement noise.
With a valid variance upper bound, Chebyshev's inequality bounds the chance that
the clean mean readout lies outside `C` by `alpha_test`. The bias allowance expands
the interval to cover a known observation transformation. This is conservative;
it is not a Student-t approximation or a fitted p-value. Model discrepancy is
handled by the declared tolerance, not disguised as extra measurement noise.

For current additive, unclipped Gaussian observations, the mean-bias bound is
zero. For the microecology adapter's clipping at zero and nonnegative clean
states, a valid channel bias bound is `noise_std / sqrt(2*pi)`: for clean value
`mu >= 0`, the clipping bias is `sigma*phi(mu/sigma) - mu*Phi(-mu/sigma)`, maximized
at zero. Clipping is 1-Lipschitz, so the same `sigma^2` remains a variance upper
bound. The operator must explicitly configure this public noise contract; the
module does not inspect a World, hidden parameters or clean targets. Other
measurement transformations require justified bounds before using this method.

The session fixes `max_tests` (1–8, default 3) and `family_alpha` (at most 0.05)
before the first test. All accepted attempts, including failed ones, consume a
slot. Under independent fresh noise and valid conditional bounds, a union bound
controls interval noncoverage across this one family by `family_alpha`, including
adaptively chosen refinements. It does not control unlogged restarts, arbitrarily
many sessions or cross-episode selection. The host must freeze one family per
episode and retain every attempt.

Let `p_A`, `p_B` be the frozen primary predictions, and `tau_A`, `tau_B` their
tolerances. The module uses the following distinct predicates:

1. **Planned separation:**
   `abs(p_A - p_B) - tau_A - tau_B > 2*r`. The same inequality must also hold for
   the target-only contribution, so disagreement confined to a known reference
   cannot produce a new-target discrimination endpoint.
2. **Within tolerance:** the entire data interval `C` lies inside a candidate's
   `[p - tau, p + tau]` band. This is an equivalence-style requirement on this
   particular readout.
3. **Refuted on the readout:** `C` and the candidate's tolerance band are disjoint.
4. **Scoped predictive discrimination:** planned separation holds, exactly one
   candidate is within tolerance, the other is refuted, and neither tolerance is
   marked wide. Otherwise the result is inconclusive, unless both are refuted.

Failing to refute a candidate is deliberately insufficient for adequacy. A
boundary-overlapping interval is inconclusive. If both candidates fail, the
result is `both_candidates_refuted`, which is useful counterexample evidence
rather than a reason to select the less wrong candidate.

Writing `W = sum(abs(weight))`, each tolerance has a hard upper bound of `0.2*W`
in normalized units. A tolerance above `0.05*W` is reported as wide and cannot
earn the discrimination endpoint even if the data fall within it. These are
explicit prototype resolution policies, not universal scientific thresholds.
They are fixed before observation, included in the registration, and require a
protocol-version change if altered. Scientific review must still justify the
chosen tolerance. The thresholds prevent arbitrarily broad bands from being
presented as successful discrimination.

## Novelty and theory refinement

The caller supplies the complete existing operator observation history, not
just the candidate's favorable citations. Previously ingested records cannot be
changed. Source citations must exist in that history. A target readout at a
previously observed coordinate under the same canonical controls is rejected,
even if the agent changes other sampling points. Known controls can be used as
an explicit reference. Initial-coordinate-zero readouts are excluded in this
environment interface.

## Material-world reference policy

`env/hysteresis_material/prospective_demo.py` supplies an authored investigator
for calibration of the real material interface. It obtains eight noisy,
same-sign high-field source trajectories, fits a saturating first-order account
and a cubic-drift account to identical public records, and freezes their
opposite-reset contrast after a new 300-second zero-field hold. The target is
then measured with 16 independent replicates per arm. The complete task uses
40 experiments and eight fresh sandbox prediction calls, with no model API.

```sh
python -m env.hysteresis_material.prospective_demo \
  --seed 7 --output /private/material-reference-new
```

This command requires the same Linux/Bubblewrap boundary as the prospective
runner. Fitting sees only public `id/spec/observation` records; it cannot read
the hidden mechanism class or parameters. Both source residuals are saved,
including when a rival is already a poor explanation of the source data. Some
instances may yield indistinguishable target predictions or refute both fitted
accounts; these outcomes are retained. The two scientific priors and the
high-field design are authored, so this is a task calibration, not a GPT score,
autonomous model selection result, or automatic discovery-depth certificate.

`env/hysteresis_material/refinement_demo.py` adds one bounded revision to that
authored policy. It starts a new task with a two-test family fixed in advance;
it does not reopen or replace an earlier reference run. If the initial cubic
program is refuted, the fitter receives only public source and counterexample
records. The revision permits a negative linear drift coefficient and therefore
a single stable state. It retains the old program byte for byte, then chooses
the largest old-versus-revised contrast from a fixed grid of 14 previously
unobserved fields and three hold durations. The model-only design search and
revised coefficients are saved before any new target measurements.

Both tests keep tolerance 0.07 and 16 replicates per arm. The complete policy
allows at most 72 experiments and 16 fresh sandbox calls, with family alpha
0.05 split over the two available tests. A failed or inconclusive revision is
retained; there is no seed retry or threshold adjustment. Source-fit residuals
are diagnostics, not independent validation. This supplied fitting strategy
tests the execution protocol, not autonomous scientific judgment.

```sh
python -m env.hysteresis_material.refinement_demo \
  --seed 7 --output /private/material-refinement-new
```

For `regime_transfer`, target controls must also differ from previously observed
controls; changing the sampling axis alone does not count. These comparisons use
canonical spec fields excluding the observation axis. They do not prove that a
syntactically different control is scientifically novel: redundant interventions,
nearly identical sample coordinates and interpolation still need review. The
module cannot prove that declared fitting citations are a complete account of a
candidate's reasoning or that a rival was plausible on the source data.

A revision must reference a completed test, retain the exact code of at least
one predictor refuted in that test, add a different code artifact, and cite a
fresh counterexample observation in the new rival's evidence. Its next target
must pass the same novelty rules. The old registration and failed forecasts
remain intact. This supports a concrete sequence:

```text
two frozen accounts -> selected new test -> both refuted
                    -> explicit revision + retained refuted account
                    -> different new test -> compare old and revised forecasts
```

Fitting the revision to the counterexample and reevaluating the same readout is
rejected. A successful new test demonstrates local predictive improvement over
the retained account. Whether the revision is a meaningful theoretical change
remains a scientific-review question.

## API and custody boundary

```python
from env.prospective import ProspectiveSession, recompute_result, replay_predictors

session = ProspectiveSession(
    public_observation_contract,
    validate_spec=validate_public_spec,
    predict=execute_in_existing_fresh_sandbox,
    observe=run_budgeted_public_noisy_experiment,
    persist=append_to_durable_operator_log,
    runtime_id=frozen_sandbox_runtime_identifier,
    max_tests=3,
    family_alpha=0.05,
)
registration = session.register(candidate_request, records=all_prior_public_records)
result = session.collect(registration["test_id"])
bundle = session.snapshot()
```

`public_observation_contract` contains exactly `environment`, `world_version`,
`axis_field`, `channels`, `scales`, `noise_std`, `noise_mean_bias_bound`. It binds
the observation semantics and world version, not the private instance recipe.

The executor signature is `predict(code, spec) -> values_array`; it must create
an isolated fresh process on every call with no world, network, private files,
future observations or access to the operator's callbacks. The module only
syntax-checks source and calls that executor. **Passing an ordinary callback is
not a sandbox.** The host must use its existing security boundary and execution
limits. The code is stored for replay; it is never passed to `exec` here.

The observer signature is `observe(spec, noise_key=...) -> public_observation`.
It must charge the host budget, preserve the same fixed instance, and honor
independent noise keys. It must never return a private clean target. The module
generates a fresh opaque session identifier and its own unique confirmation
keys. The host must not substitute candidate-provided keys or observations.

`persist(event)` must durably append an event and return a nonempty receipt
string. Events contain operator-controlled sequence numbers, previous-event
hashes and payload hashes. The registration event precedes collection-start and
observation events. Persistence failures block progression or leave an explicit
failed attempt; no partial-data verdict is produced.

Hashes detect changes against trusted anchors. They cannot prove chronology or
authenticity by themselves, and a receipt string is not a digital signature.
The host must protect the append-only log and preserve it outside the candidate
sandbox. `snapshot()` is an export, not a resumable or independently authenticated
session. There is intentionally no restore-from-candidate-JSON operation.

For offline numerical replay, obtain `expected_seal` from the trusted registered
event and `expected_observations_sha256` from the trusted completed event:

```python
recomputed = recompute_result(
    registered_payload, recorded_observations,
    expected_seal=trusted_registration_hash,
    expected_observations_sha256=trusted_completed_observation_hash,
)
code_checks = replay_predictors(
    registered_payload, execute_in_same_fresh_sandbox,
    expected_seal=trusted_registration_hash,
)
```

Reading both expected hashes from an untrusted rewritten bundle authenticates
nothing. Replay also requires the same execution runtime for byte-identical
numeric outputs. Neither replay function calls a simulator or model API.

## Executable standalone task

The operator API accepts experiment specs and predictor source; it never accepts
submitted observations, measurement keys, timestamps, or an arbitrary executor.
Every candidate prediction uses a fresh `CandidateProxy` with a bounded deadline
and memory limit. The sandbox mounts the frozen candidate **file**, the minimal
worker files, and approved numerical runtime. It does not mount the operator
directory, any World source, repository, prior results or host environment. There
is no in-process execution fallback when Bubblewrap is unavailable.

```python
from env.prospective_runner import ProspectiveTask, verify_directory

task = ProspectiveTask("hysteresis_material", operator_seed, new_private_directory,
                       limits={"predictor_seconds_per_call": 30.0})
problem = task.describe()  # public schema; never includes the seed or kernel
record = task.observe_source(public_spec)
# Fit candidate programs only from record["spec"] and record["observation"].
# Cite record["id"] in the request's rival evidence_ids.
answer = task.preregister(request)  # seals, then immediately collects once
report = task.finish()
checked = verify_directory(new_private_directory)
```

`preregister` returns `test_id`, `seal_sha256`, the structured `result`, and fresh
`observation_ids`. Later revisions use that test ID and cite the new observation
IDs; they must satisfy the protocol's retained-rival and new-target rules. The
caller can obtain full observed trajectories with `task.public_records()` and
execute another source experiment between tests. Scientific negative
results complete normally; operational failures close the entire task.

The instance seed is an operator-only constructor/CLI input. All source and fresh
observations pass through the same budgeted World call with an operator-generated
noise key. The key is never passed into the predictor's `predict(spec)` RPC.
Candidate parameters must be embedded in the frozen source; files alongside that
source are not available inside its sandbox.

Defaults are 32 actions, 3 prospective tests, 96 experiment attempts, 10,000
experiment cost units, 24 isolated prediction calls, 360 seconds of prediction
allowance, 15 seconds per prediction, 2,048 MiB per predictor, 300 seconds of
simulation, 30 seconds per simulation, and 900 seconds for the whole task. The
family alpha is 0.05. Operator overrides are fixed at task creation and included
in the private metadata and receipts.

Before starting each test, the operator checks that the **entire** fixed
replication plan and four prediction calls per experiment fit the remaining
budgets. Each candidate attempt is charged its full per-call allowance before
startup, including rejected, crashed or timed-out executions; actual elapsed
prediction time is recorded as well. Both charged and actual time constrain
further calls. Every dispatched World call consumes one attempt and its public
cost before simulation, including failed calls. Actual simulation time is
bounded per call and cumulatively. Invalid actions consume action budget and
close the task. An accepted plan is never shortened to fit remaining resources.
Unused capacity after failure is not counted as an executed experiment, and
failed tasks cannot resume or retry.

The output directory must not already exist (including a symlink). Private
directories use mode 0700, metadata, checkpoints and receipt files use 0600, and
the nonsecret candidate leaf uses 0444 so the sandbox UID can read its one bind
mount. Every receipt is a separately fsynced, atomically published, no-overwrite
file. An atomic head links its sequence and SHA-256 to the previous receipt.
The complete sealed registration is persisted before any confirmation call.
Valid partial observations and failed attempts remain in the private bundle and
raw receipt log. A filesystem failure leaves its artifacts for audit; it never
triggers implicit repair, resampling or automatic rerun.

`verify_directory` checks both receipt chains, operator metadata, input-plan and
candidate source integrity, then independently recomputes each completed numeric
verdict from its frozen full arrays and recorded observations. It also checks
that a confirmation's original observer response occurred after collection was
authorized. It does not execute candidates, call a World, or use a model API.
The log must remain in trusted operator custody: an attacker able to replace the
whole directory and anchor can manufacture a new chain. Hashes and permissions
are not a digital signature or a remote attestation protocol.

### CLI and offline example

On the Linux evaluation host with the existing numerical runtime and Bubblewrap:

```sh
python -m env.prospective_runner demo --directory /private/new-prospective-demo
python -m env.prospective_runner verify --directory /private/new-prospective-demo
python -m env.prospective_runner run --environment hysteresis_material \
  --seed 7 --plan /operator/plan.json --directory /private/new-material-task
```

The `demo` command uses a deliberately simple private synthetic instance. It
first observes a zero-drive source, seals two candidate coefficients, obtains a
counterexample that refutes both, fits a revision **only from the public observed
readout**, and compares that revision with a retained refuted predictor at a new
drive. Candidate execution is real sandbox execution even in this demonstration.
The fixture is not part of the registered scientific environments and does not
establish scientific novelty or mechanism identification. Changing the seed
changes its private coefficient; noise is fresh for each task. There is no
forced success, retry or seed selection if an operational or numerical test
fails. This demo makes zero model API calls.

`run` takes this JSON envelope. Each item in `tests` is the full request from the
minimal protocol above, including the embedded predictor sources:

```json
{
  "protocol": "sle-prospective-plan-0.1",
  "source_experiments": [{"...": "one legal public experiment spec"}],
  "tests": [{"...": "one complete preregistration request"}]
}
```

Source record IDs are `obs-source-0001`, `obs-source-0002`, and so on. A later
planned revision can use `"revision_of": "$previous_test"` and an evidence ID
such as `"$previous_fresh:0"`; the operator resolves these to the immediately
preceding completed test's real IDs. These aliases do not let a static JSON plan
fit a predictor to future data. An adaptive fitter uses the programmatic API
between completed tests and submits new code before its next fresh experiment.
The CLI exits nonzero on failure and keeps all partial artifacts. `--limits`
accepts an operator JSON file of limit overrides. The public CLI output omits
private seed, kernel, paths and arbitrary candidate exception text; the output
directory itself remains private and must not be attached wholesale to an agent.

## Minimal future episode-runner connection

The standalone task is executable now. The existing episode runner and its
SYSTEM prompt are unchanged. A later, separately frozen cohort could add one
action alongside existing actions:

```json
{"note": "Rival assumptions and the planned test.", "preregister": {"...": "the request fields above"}}
```

The host should implement that one action in this order:

1. Bind trusted public noise/scales metadata and an existing isolated predictor
   executor. Freeze the family size and alpha once per episode. Snapshot the
   complete observation history; expose only public metadata to the candidate.
2. Validate and reserve the **entire** plan's experiment units and number of
   observations (`replicates * number_of_experiments`), plus time for up to eight
   isolated prediction calls. The module does not manage the campaign budget.
3. Persist the research note, then call `register`. Its durable registration
   receipt is the gate to collection. Do not accept a submitted timestamp as
   evidence of preregistration.
4. Call `collect` once and run the fixed replication plan through the same
   budgeted observation path. Add all fresh observations, including valid partial
   results from failed attempts, to the episode's public record catalog.
5. Return the seal, structured result and observation IDs. Store the complete
   bundle and failed attempts under a separate prospective-evidence report field.
   Do not alter the prediction score, claim score, or automatic depth status.

An isolated-code failure, storage failure or incomplete collection is an
operational failure, not a scientific falsification. The trusted host distinguishes
candidate call/shape failures from candidate-file persistence, known sandbox
startup and cleanup failures. A `CandidateError` during worker construction can
originate in candidate imports or runtime initialization; it is explicitly
`PredictorInitializationUnresolved`, rather than automatically attributed to the
model or infrastructure. All attempts retain their charged allowance and bounded
failure-stage record. Original exception text and private paths are not returned.
A scientifically negative
result is retained rather than retried with different seeds. Session restart
after a process failure requires host-level auditing; this MVP does not provide
an automatic recovery flow that could resample a partly seen test.

The existing core-c2 pilot keeps its frozen code, prompts, source digest and
scoring. This prototype is for a future cohort. New files change the development
checkout's source digest and must not be copied into the frozen runtime.

## Verification

Protocol tests use local numerical fixtures and fixed-program replay. Standalone
operator tests exercise receipts, budgets and failure paths with a numeric
stand-in that only parses fixture literals and never executes source. Two
additional tests run real CandidateProxy sandboxes: the full revision demo and
probes for private files, host environment, network, forbidden process creation,
read-only candidate mounts, and fresh process state. These skip only on a
non-Linux platform lacking Bubblewrap; Linux without Bubblewrap fails. All tests
make zero model API calls. They cover sealing before observation, full-output
replay, tampering, equivalence versus nonrejection, both-rivals-failed cases,
noise/bias/correlation bounds, tolerance limits, novelty and sampling aliases,
refinement lineage, fixed replication and alpha budgets, deterministic code,
durable-write failures and nonretryable partial collection.

```sh
python -m pytest env/tests/test_prospective.py tests/test_prospective_runner.py -q
```
