# Prospective evidence packages

`env/prospective.py` is an independent prototype for turning two task-profile
requirements into replayable evidence: rival predictions recorded before a
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
six-environment pilot.

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

## Minimal future runner connection

No connection is implemented in this change. A later, separately frozen cohort
could add one action alongside existing actions:

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
operational failure, not a scientific falsification. A scientifically negative
result is retained rather than retried with different seeds. Session restart
after a process failure requires host-level auditing; this MVP does not provide
an automatic recovery flow that could resample a partly seen test.

The existing core-c2 pilot keeps its frozen code, prompts, source digest and
scoring. This prototype is for a future cohort. New files change the development
checkout's source digest and must not be copied into the frozen runtime.

## Verification

Tests use local numerical fixtures, include a fixed-program fresh-process replay,
and make no paid API calls. They cover sealing before observation, full-output
replay, tampering, equivalence versus nonrejection, both-rivals-failed cases,
noise/bias/correlation bounds, tolerance limits, novelty and sampling aliases,
refinement lineage, fixed replication and alpha budgets, deterministic code,
durable-write failures and nonretryable partial collection.

```sh
python -m pytest env/tests/test_prospective.py -q
```
