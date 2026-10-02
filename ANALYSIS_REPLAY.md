# Offline analysis failure replay

This diagnostic replays recorded analysis source under the current enhanced error
worker. It does not ask a model to revise source, run a World, execute a predictor,
recompute a score, or change any original report. A repeated `TypeError` means only
that the same error type occurred under the declared replay conditions. It does
not establish that the original failure had the same cause.

The fixed study is all 29 `TypeError` analysis events in the existing
`process-resource-audit` for `core-c2` and `expansion-e1`: 11 core episodes and no
expansion episodes qualify. Each selected episode includes every analysis from
its first analysis through its final selected `TypeError`: 72 calls in total,
including 41 originally successful calls and 2 originally failed `SyntaxError`
calls. No later analysis is run. There is one attempt per episode and no retry.

## Recoverable evidence and limitations

The original report contains response source, full prior public turns, and all
observations. The transport log contains the exact public problem and prompt.
Preparation authenticates the transport request hash, report prompt/system
hashes, public catalog, research notes and recent results. Final records must
equal the ordered concatenation of every history observation, including retained
observations from partial invalid experiment batches.

Each analysis receives the original response's source, its own authenticated
problem, observations strictly before that round, and original history strictly
before that round. Public-input fields, the full payload and raw UTF-8 source
receive separate SHA-256 bindings. No verification panel, final prediction,
operator state, submission or later observation is supplied. Candidate-generated
history content is treated as data; it is not host instructions.

A single `CandidateProxy` process maintains each episode's analysis namespace.
Earlier successful **and failed** analyses run in original order because a failed
analysis may leave variables or functions behind. Fresh RPC payloads overwrite
`problem`, `records`, `history` and `result` exactly as the current worker does;
other namespace state persists. Replay feedback never replaces original history.
Candidate mutations to one injected payload cannot change the host's frozen
inputs. Episodes have separate processes.

The original namespace was not serialized. Exact state is therefore unavailable:
randomness, current clocks, unseeded optimization, imported modules, temporary
files, library versions and execution time may differ. Matching all earlier
result receipts is useful evidence but cannot prove identical hidden namespace
state. A changed earlier result sets `prefix_diverged_before_event` for subsequent
events. Enhanced feedback adds diagnostics; its fields are excluded when comparing
the old receipt's `ok/error/result/stdout` content. New messages are not injected
into subsequent history.

Missing or ambiguous public-input evidence skips the entire episode with an
explicit gap. Snapshot-enabled protocols are unsupported and skipped; the
selected original episodes used the legacy protocol. Any original worker timeout
in the required prefix is treated as an interrupted namespace. Missing or changed
raw evidence prevents execution. Nonreproduced failures remain unresolved.

## Budget and isolation

The total active allowance per episode is at most its original 60 seconds,
including worker startup. Each call is further capped by the logged original
remaining active allowance and wall allowance, reduced by half their recording
rounding units. Actual elapsed call time is subtracted. These logged allowances
precede the original model response; exact original per-call wall allowance is
unavailable. Hardware, startup and timing changes can stop this replay at a
different point. No extra diagnostic time is added.

Only `run-native` can instantiate the production executor. It requires Linux
Python 3.10 or newer (including `Path.is_relative_to` and dictionary union),
Bubblewrap, the exact reviewed plan and source SHA-256, and the operator's host
attestation `62910175`. The attestation is an explicit deployment assertion, not
machine authentication; the operator must deploy to that host. There is no
local-Python fallback. The source fingerprint binds the replay module, worker,
RPC code, sandbox driver and package pin policy. The run manifest records Python,
NumPy, SciPy, source hashes, Python/Bubblewrap executable hashes and sandbox
settings. Original reports retain only an aggregate source digest, not separate
worker/runtime versions; that digest is copied to each private episode receipt.

The existing sandbox uses `--unshare-all`, process-denying seccomp, a private
tmpfs, read-only runtime/package mounts, a memory limit and active deadlines.
There are no callbacks, credentials, model clients, network or host data mounts.
There is no package installation/download path. This module neither imports
`env.runner` nor executes candidate strings in the host process.

All episodes and public-input hashes are prechecked **before** constructing the
first executor. Output must be a fresh directory outside original cohort
directories. A persistent sibling `*.native-run-claimed.json` file is created
exclusively before any execution. It remains on failure or interruption; the tool
does not retry the same plan. Do not copy/rename a plan to bypass this rule.

Each completed or skipped event is written immediately to an exclusive private
file, before the next call. Cleanup errors preserve the events, set the episode's
`complete` to false and record a bounded error class; later planned episodes can
still run once. External interruption produces an invalid final summary when
Python can unwind. A hard kill can prevent finalization, so an absent summary is
never interpreted as success; existing event files remain private evidence.

## Commands for the operator

Use the existing remote Python environment that already supports the sandbox.
Do not install packages or run the selected candidates locally.

Preparation and precheck perform only JSON/file operations and can run locally:

```sh
python -m env.analysis_replay prepare \
  --artifact-root /path/to/sle-env-eight-hour-20261003 \
  --study-plan /path/to/calibration/analysis-failure-replay/study-plan.json \
  --output /path/to/calibration/analysis-failure-replay/replay-plan-private.json

python -m env.analysis_replay precheck \
  --artifact-root /path/to/sle-env-eight-hour-20261003 \
  --plan /path/to/calibration/analysis-failure-replay/replay-plan-private.json

python -m env.analysis_replay source-fingerprint
```

The fixed audit references use relative raw paths when preparing the replay
plan, so the complete evidence tree can be transferred without editing its JSON.
Review and freeze the source, then record the plan file hash and emitted source
fingerprint. Run the following **only on host 62910175**, once:

```sh
python -m env.analysis_replay run-native \
  --artifact-root /remote/path/to/sle-env-eight-hour-20261003 \
  --plan /remote/path/to/replay-plan-private.json \
  --output /remote/path/to/new-native-diagnostic-output \
  --reviewed-plan-sha256 REVIEWED_PLAN_FILE_SHA256 \
  --reviewed-source-sha256 REVIEWED_SOURCE_FINGERPRINT \
  --host-attestation 62910175
```

The output directory's parent must exist. No output file is overwritten. Original
52 raw report/transport hashes are checked again at the end, including failure
paths that reached execution; source hashes must also be unchanged. Root's
deployment freeze remains necessary to avoid external changes during execution.

## Outputs and interpretation

Private per-episode receipts bind original event IDs and history pointers to
payload/code hashes, original and replay result digests, error type, phase,
candidate line and a message of at most 600 characters. Result and stdout bodies
are never copied. Executor errors copy no host stderr or traceback. Messages are
private candidate-controlled data and must not be published verbatim.

`summary-public.json` is built from a literal allowlist of integer counts and
error/phase/status categories. It contains no episode IDs, paths, source,
observations, raw messages, model identity, scores or completion-rate estimates.
An unknown error label becomes `other`. The summary describes diagnostic calls,
not original model performance. Original completion and scores remain unchanged.
It is written only after final raw/source hash checks, with explicit `status` and
`conclusions_valid`. A changed or unreadable input/source, cleanup failure or
interrupted study produces `invalid`/false while retaining all planned
denominators and a `not_attempted` target count. Budget stops and declared input
gaps can produce `partial`; those categories support no conclusion about the
unreplayed failures.

Report same-type reproduction as: “The recorded error type was reproduced under
the declared conditions; the replay message/phase suggests a diagnostic category.”
Do not report it as a confirmed original cause. Report failed reproduction,
budget stops and input gaps separately, without attributing an unobserved cause.

Tests use deliberately non-executable source strings and inert receipt-returning
executors. Run only this focused file for the offline checks:

```sh
python -m pytest -q tests/test_analysis_replay.py
```
