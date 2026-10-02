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
