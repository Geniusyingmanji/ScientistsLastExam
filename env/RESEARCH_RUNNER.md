# Interactive prospective research tasks

`research_runner.py` connects a model to `ProspectiveTask` and the isolated
analysis/model-snapshot interface. It is a separate experimental protocol,
`sle-research-agent-0.1`; it does not change the historical pilot runner or its
0–100 score. No live GPT evaluation of this new interaction protocol has been
performed in the first campaign.

The model chooses a question, observes public experiments, fits candidate
programs in isolated Python, seals two predictions for a new experiment, sees
the resulting evidence, and can revise an account before a new test. It may
finish with discrimination, rejection of both accounts, or an inconclusive
result. There is no hidden-mechanism label to match and no automatic discovery
depth grade. Scientific review must still evaluate rival plausibility,
mechanistic meaning, scope and whether the chosen question was informative.

## Actions and artifacts

Each response has `note` plus exactly one action:

| Action | Effect |
|---|---|
| `experiments` | Collect up to eight public source experiments under the same hidden instance and finite task budget. |
| `analyze` | Run isolated Python over all public records/history; immutable model versions can be saved with `save_model`. |
| `preregister` | Bind inline or saved predictor programs, seal their full forecasts and experimental design, then collect the entire fixed independent replication plan. |
| `finish` | Save findings, limitations and valid observation/test citations; requires at least one completed prospective test. |

The last model turn permits only `finish`. A completed task is a technical
completion, including a well-recorded negative or unresolved result; it is not
a successful mechanism discovery. Saving fitted parameters is optional and does
not prove that the fit is correct. A snapshot reference in a rival resolves to
exactly its recorded version and SHA-256; future versions cannot replace it.

Public prompts contain the apparatus, observation/noise contract, task intent,
remaining allowances, observation catalog, candidate-owned model catalog,
research notes and recent public results. The analysis worker sees all observed
records and history. Large recent results remain accessible in analysis rather
than being invented from a compact prompt. The new research profile projects
out the old pilot's final predictor/claim submission instructions.

The private output contains the frozen manifest, model transport receipts,
chronological driver receipts, public history, saved model versions, final
interpretation, and a `science/` task with the original prospective seals and
full measurements. These are operator artifacts, not public benchmark pages.
`python -m env.prospective_runner verify --directory RUN/science` checks the
scientific receipt chain and numeric verdicts without a new model/simulator call.
It does not authenticate arbitrary replacement of the entire operator archive.

## Freeze before execution

```sh
python -m env.research_runner freeze \
  --episode prospective-development-01 --environment hysteresis_material \
  --seed OPERATOR_ONLY_INTEGER --output /private/new-manifest.json

python -m env.research_runner run \
  --manifest /private/new-manifest.json --model-config /private/model.json \
  --ledger /private/existing-campaign-ledger.sqlite \
  --directory /private/new-research-run
```

Freeze performs no model request. A limits JSON can contain `driver` and `science`
overrides; limits are fixed in the manifest. The default driver permits 24 model
turns, 120 active analysis seconds and 1,800 wall seconds. The scientific task
retains its own tighter default wall budget and finite experiments, units,
prospective tests, isolated prediction calls and allocated execution time.
The actual task and driver deadlines jointly constrain progression.

Run checks source, system, public description, task, snapshot contract, model and
decoding against the frozen manifest. It requires an **existing** shared attempt
ledger with capacity for the entire maximum model-turn allowance. It never
creates or expands a ledger, substitutes a model, retries transport, or resumes
a prior task directory. The first campaign's remaining capacity is insufficient
for this protocol; the executable path is tested with scripted clients, not
represented as another GPT result.

## Failure attribution

Invalid JSON/analysis requests consume a model turn; malformed experimental and
preregistration actions close this prototype scientific task. Valid partial
observations and spent allowances remain. Analysis and candidate programs use
the existing Linux/Bubblewrap isolation; there is no in-process fallback.

Known storage/runtime failures are distinguished from candidate execution
failures. A worker startup error that cannot be separated into candidate import
versus sandbox initialization is reported as `initialization_unresolved`, with
`failure_attribution="unresolved"`; it is not silently assigned to either a
model-error or infrastructure denominator. Late final-write and cleanup failures
cannot leave an apparently successful research run. Candidate feedback uses
bounded categories rather than private exception paths/messages.

Tests cover immutable freeze contracts, model/decoding mismatch before requests,
partial and invalid actions, elapsed budgets, snapshot persistence, source/model
binding, public-only observations, late failures, cleanup and typed attribution.
The Linux end-to-end test uses real isolated analysis and predictions with a
scripted model client: observation → saved models → prospective seal → fresh
measurements → final report. It makes zero API calls and establishes interface
execution, not autonomous scientific ability.

```sh
python -m pytest tests/test_research_runner.py tests/test_prospective_runner.py -q
```

## Authored reference policies

The Python-only `create_reference_manifest(...)` path freezes an explicit
`scripted_reference` identity, implementation hash and bounded action-call time.
It sets `requested_model` to null and `decoding` to an empty object. A trusted
reference client must expose matching `client_kind`, `reference_id` and
`reference_source_sha256` attributes, implement the same `complete` action
interface, and return no provider metadata or token usage. Its implementation
must be inspected to establish that it makes no API calls; a Python identity
assertion is not a host network sandbox.

Reference requests have their own counter and journal event names. They cannot
contribute model-request counts or impersonate a model/provider in the report.
Invalid authored actions are attributed to `reference_policy`, and completion
retains `autonomous_discovery: false`. The ordinary API CLI rejects these
manifests before opening a ledger or constructing an API client. It has no new
budget bypass, reference-mode CLI switch, or automatic fallback.

The reference policy still uses the same isolated analysis and prediction
workers, immutable snapshots, scientific budgets, prospective seals, receipt
chain and negative-outcome semantics. This path supports authored integration
and learnability experiments; it is separate from live model evaluation.
