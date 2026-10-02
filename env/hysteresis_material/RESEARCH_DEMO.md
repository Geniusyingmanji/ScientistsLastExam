# Material research-runner reference example

`research_demo.py` is an authored, zero-API policy that uses the real
`env.research_runner.run_research` interface on `hysteresis_material`. It provides
the same JSON experiment, analysis, preregistration and finish actions that a
model client supplies. This checks execution compatibility and preserves a
scientific trace. It is not GPT performance, autonomous discovery, a replacement
for the earlier prospective demonstrations, or an automatic D3/D4 assessment.

The execution plan was saved before native execution at
`calibration/material-research-driver-reference/analysis-plan.json` under the
central private artifact root. It fixes four development seeds: 7, 46, 1439 and
8743. A recorded arithmetic correction reserves eight prediction calls and
120 predictor seconds: two targets × two rivals × two executions for the
existing determinism check. No result motivated that correction.

## Four actions and fixed budgets

1. Observe eight source experiments: negative and positive resets, no
   preparation, and constant fields of matching sign at magnitudes 1, 1.15,
   1.3 and 1.5. Each samples 0, 0.5, 1, 2, 3, 5, 8, 12, 20, 40 and 80 seconds.
2. Send self-contained Python to the existing `IsolatedAnalysis` sandbox. Fit
   two authored accounts to those public records and use `save_model` to save
   each finite fit and its predictor as immutable `v1` snapshots.
3. Preregister both exact `{name, version, sha256}` receipts. Predict two new
   zero-field holds after opposite resets at 0 and 300 seconds. Compare the
   positive-minus-negative response at 300 seconds, divided by the public
   channel scale, with tolerance 0.07 per rival. Collect eight fresh replicates
   of each target under one test, with family alpha 0.05.
4. Finish by citing actual observation/test IDs and reporting the host outcome,
   observed contrast, interval and frozen rival predictions. Negative and
   inconclusive results remain valid completed tests.

Per instance the ceiling is four reference calls, one isolated analysis with
90 seconds including worker setup, 24 experiment calls, eight predictor calls
of at most 15 seconds each, 120 simulation seconds, and 600 total wall seconds.
The four-instance ceiling is 16 reference calls and 96 experiment calls.
Model API calls and ledger operations are zero. The host's existing budget
admission rules apply; the script does not increase budgets after a failure.

The source fits consume at most 80 `least_squares` function evaluations per
account, including neither Jacobian evaluations in SciPy's reported `nfev` nor
the final diagnostic residual. A separate counter includes those evaluations
and enforces a ceiling of 500 residual calls per account. Both the SciPy count
and actual residual count are retained. The host's analysis deadline is the
ultimate wall bound. Finite unconverged fits are saved with explicit unsuccessful
optimizer status; an exception is retained as a failed fit. There is no refit,
replacement rival, target retry or fallback to host-side analysis.

## Prior knowledge and scientific limits

The author supplies two five-parameter families in measured response units:

| Authored account | Response equation | Start | Lower / upper bounds |
| --- | --- | --- | --- |
| Saturating relaxation | `dy/dt = (o + A tanh(k h + b) - y) / tau` | `(0,1,1.2,0,9)` | `(-.2,.4,.2,-.4,1)` / `(.2,2,4,.4,60)` |
| Cubic drift | `dy/dt = d + a(y-o) - c(y-o)^3 + f h` | `(0,0,.09,.09,.07)` | `(-.2,-.04,.001,.003,.001)` / `(.2,.04,.4,.4,.4)` |

For the cubic row the parameter order is `(o,d,a,c,f)`. A positive linear
coefficient is a prior favoring a double-well shape; bias and forcing still
affect whether a particular field has multiple stable equilibria. The identifier
`cubic_memory` is a rival program name, not proof of retained memory. Field and
response units and the time axis come from the public apparatus contract.

The initial response for each reset is the mean of its four public time-zero
observations. Subsequent source residuals exclude only time zero and are fitted
without private state or reset-equilibrium information. Reset estimation noise
is not propagated as a fitted-parameter confidence interval. The cubic response
is integrated with LSODA (`rtol=2e-6`, `atol=2e-8`); prediction uses the same
equation with tighter tolerances and respects preparation steps and piecewise
linear drive knots. The source design, starts, bounds and target are fixed for
all instances before any observations.

These authored priors are substantial information. The source fields may
already make one rival implausible, and source RMSE and optimizer status remain
visible in its preregistered rationale. High-field fits may leave low-field
behavior poorly identified. The fresh test compares two frozen point predictors,
not every parameterization of their entire families. A rejected point fit does
not falsify its whole family; an adequate prediction does not identify a unique
mechanism. A 300-second response does not prove infinite-time memory. The
host's noise interval concerns fresh readout noise, not parameter uncertainty
or structural completeness. No outcome receives an automatic depth grade.

## Isolation, identity and artifacts

`create_reference_manifest` freezes `client_kind="scripted_reference"`,
`requested_model=null`, empty API decoding, the reference identifier and this
module's SHA256. The shared source digest separately freezes the runner,
scientific host, snapshot binder and all other Python runtime source. The client
has no model config, reports no provider metadata or token usage, and records
`reference_request_attempts` separately from zero `model_request_attempts`.
Its factory receives only a transport directory and the declared source hash;
it never receives the manifest, hidden seed, World, private parameters or target
truth. Like any Python client factory, it is trusted operator code, not itself
a process security boundary. This specific implementation has no oracle/file
inspection path beyond writing its own public prompt/response logs.

All fitting code is sent as the analysis action. Its only data dependency is
the eight public `records`; numpy, SciPy and the candidate-owned `save_model`
callback supply its other capabilities. No `env` import, operator mount,
World access, random seed generator or file access exists in that source.
The predictor reads `MODEL` restored by the existing JSON snapshot binder in
the existing fresh predictor sandbox. Parameters are not interpolated as
executable Python. Production offers no alternate analysis/predictor factory.

The host gives source observations and confirmations distinct private noise
keys. It seals all predictions and the fixed replication count before collecting
fresh data. This is independent noise, not common random numbers. No target
data enters either fit, and the client cannot add a fifth action or retry a
request. Both snapshot hashes are checked against the public catalog before
preregistration; failed/partial snapshots are not silently replaced.

The CLI freezes all selected manifests before its first experiment. The new
0700 output directory contains the private plan and source copy, followed by
anonymous instance directories with the existing runner's manifest, raw public
transport logs, driver receipts, analysis history, snapshot bodies/receipts,
prediction files, science receipts and final/report files. A read-only receipt
replay checks sealing order, unique observation keys and numerical verdicts.
The wrapper also matches the replay count, complete numerical-result list and
receipt head to the driver's scientific report. A completed reference requires
exactly one completed test. A valid partial archive alone cannot verify a
completed report; `archive_verified` records that narrower check separately.
Replay does not rerun a World or candidate. Public summaries expose status, budgets,
timings, source-fit diagnostics, bounded error categories and outcomes, with no
hidden seed, stratum or fitted parameter values. All planned failures remain
rows; no new composite score is generated. Existing output paths are refused.

## Run and validate

Run from the frozen repository on the Linux host configured for the existing
native candidate sandbox:

```sh
python -m env.hysteresis_material.research_demo \
  --output /absolute/new/private/material-research-driver-reference
```

The default is the prespecified four seeds in order, executed sequentially. An
explicit development subset such as `--seeds 7` is useful for a separately
labelled smoke check; it does not count as completion of the four-seed plan.
Duplicate seeds and other seeds are rejected. `run_frozen` additionally rejects
manifests that change the reference's fixed plan. Never reuse a prior p1/p2
directory or run this via the API/ledger CLI. A nonzero exit preserves partial
artifacts; it does not authorize a rerun. Successful interface validation
requires both driver completion and a successful receipt replay, regardless of
which scientific outcome occurred. `completed_instances` counts driver
completion; `verified_completed_instances` additionally requires that replay.

Local small tests:

```sh
python -m pytest -q env/hysteresis_material/tests/test_research_demo.py
```

The numerical fixtures use independently generated analytic public records and
in-process execution of fixed authored code only. They check immutable hashes,
data dependence, failed/unconverged fits, analytic zero-field limits, legal
design/budget arithmetic, JSON actions, identity, tamper rejection and failure
denominators. They do not establish native isolation. The production path is
checked to dispatch the shared runner without an analysis override. An explicit
remote native test is available only on Linux when
`SLE_RUN_MATERIAL_RESEARCH_NATIVE=1`; it must run in a new separately labelled
directory and is not part of the four-seed calibration. Native execution and
four-seed results were intentionally not run locally during implementation.
