# Candidate-owned model snapshots (prospective API version)

`sle-analysis-snapshots-0.1` adds a small persistence API for fitted models. It
addresses loss of fitted parameters between scientific analysis and the final
self-contained predictor. It does not change the scientific worlds or scorer.
The original `predictor_code` submission remains supported.

This API is **opt-in for future episodes**. Set the operator instance field
`analysis_protocol` to `"sle-analysis-snapshots-0.1"` before freezing that episode's
manifest and source. If the field is absent or `"legacy"`, the runner preserves
the legacy analysis/submission interface; no model store is created. Unknown
versions fail before a model call. Existing frozen core-c2 and expansion-e1
artifacts and their source copies are not altered or retrospectively re-scored.

The normal cohort CLI accepts `--analysis-protocol sle-analysis-snapshots-0.1`
on `freeze`. It records the protocol on every instance and freezes the complete
public storage contract. `run` rejects contract or per-instance version drift
before opening the campaign ledger or contacting the model.

## Candidate workflow

In an `analyze` action, fit from the public records and save a named version:

```python
import numpy as np
t = np.asarray(records[0]["observation"]["axis"], dtype=float)
y = np.asarray(records[0]["observation"]["values"], dtype=float)[:, 0]
slope = float(t @ y / (t @ t))

code = """def predict(spec):
    return [[MODEL["slope"] * t] for t in spec["times"]]
"""
receipt = save_model("linear-fit", "v1", {"slope": slope}, code)
result = receipt
```

The receipt contains `name`, `version`, `sha256`, a logical URI such as
`model://linear-fit/v1`, storage bytes and whether code is included. The URI is
an identifier, not a filesystem path. Copy the receipt's first three fields into
the final submission:

```json
{
  "note": "Freeze the saved fit",
  "submit": {
    "model_snapshot": {
      "name": "linear-fit",
      "version": "v1",
      "sha256": "the 64-character digest returned by save_model"
    },
    "claims": [],
    "explanation": "Describe the evidence and limitations of this model."
  }
}
```

The trusted runner resolves the exact immutable version, binds its JSON
parameters to the global `MODEL`, and creates a self-contained `predictor.py`.
Every prediction still runs in the existing fresh `CandidateProxy` sandbox with
only the public query. It receives no analysis variables, records, model-store
callbacks, simulator, or targets. The saved code should use `MODEL` rather than
assuming that its old analysis variables exist. It must still define `predict`
and produce the correct numeric matrix.

Parameters can be saved before code is ready:

```python
receipt = save_model("fit", "v2", {"coefficients": coefficients.tolist()})
restored = read_model("fit", "v2")
result = {"parameters": restored["parameters"], "reference": restored["reference"]}
```

For a parameter-only snapshot, include both `model_snapshot` and
`predictor_code` in the final submission. If the snapshot already includes code,
an explicit submitted `predictor_code` deliberately replaces that saved code for
the final binding. The resulting source digest records this choice. Code is
ordinary Python source; optional module docstrings and `__future__` imports are
preserved. Preamble statements must occupy separate lines.

`list_models()` returns receipts without the parameter/code bodies. The same
catalog appears in each round's prompt, so losing an old model response does not
lose the reference. `read_model(name, version)` returns a detached JSON copy of
the saved parameters and code. Returning a very large read directly as analysis
`result` can exceed the existing 64,000-character result limit; inspect a small
summary instead. The full object is available to the analysis code.

## Persistence and limits

Saving is a synchronous RPC to the trusted per-episode store. Its validation and
atomic publication finish before the receipt is returned. A later analysis
exception, variable deletion or worker restart does not remove a successful
save. The store contains only values explicitly passed by the candidate; it
does not capture closures, arbitrary variables, interpreter memory or files.

Name and version each accept 1–48 ASCII letters, digits, dots, underscores or
hyphens, beginning with a letter or digit. Versions are immutable: an identical
save is idempotent, while changed content under the same name/version is
rejected. There is no `latest`, overwrite, deletion, arbitrary path, cross-episode
lookup or automatic reopening of an existing episode directory.

| Bound | Limit |
|---|---:|
| Saved name/version pairs | 16 |
| Total canonical snapshot storage | 262,144 bytes |
| Canonical parameter JSON per snapshot | 16,384 ASCII bytes |
| Predictor source supplied to a snapshot | 32,768 UTF-8 bytes |
| Final bound predictor source | 64,000 UTF-8 bytes |
| JSON nesting depth / traversal nodes | 12 / 4,096 |
| Candidate callback attempts per episode | 256, including rejected calls |

Parameters must be a plain JSON object containing finite numbers, strings,
booleans, nulls, lists and string-keyed objects. Integers are restricted to
±(2^53−1). Convert NumPy arrays/scalars explicitly. Cycles, custom objects,
tuples, bytes and the RPC-reserved key `__fs_type__` are rejected. Storage limits
include escaped canonical bytes, not just raw character count. The existing
analysis active-time, wall-time, worker memory and RPC transport limits continue
to apply. There is no additional model request or experiment cost.

Invalid inputs, exhausted quotas and failed atomic writes publish no snapshot
and do not consume storage capacity. Rejected calls still consume callback
attempts. No existing file is replaced. Final submission seals the store; no
later callback can create or change saved data. Final resolution itself remains
available even if the candidate has exhausted its callback allowance.

## Threat boundary and audit artifacts

`env/analysis_api.py` is trusted code with no world, registry, seed, target or
network dependency. Three existing JSON RPC callback handles expose only the
current store. No extra host directory or module is mounted in the analysis
sandbox, and `sle/secure_eval.py` is unchanged. Snapshot names never select a host
pathname: artifacts are operator-chosen, content-addressed JSON files under
`model-snapshots/` with directory/file modes 0700/0600.

JSON is bounded and validated before serialization. The restore path uses only
`json.loads`; there is no pickle, object hook, `eval`, or execution of candidate
code on the trusted host. Parameter JSON is serialized again as a JSON string
literal before source insertion, so quotes, backslashes and apparent Python
expressions remain data. The predictor code remains untrusted executable source
and runs only in the existing predictor sandbox. A successful save checks storage
and syntax, not scientific accuracy, safe algorithm behavior, or the presence of
a working `predict` entrypoint.

The callback transport retains its existing generic RPC message-size ceiling;
snapshot-specific smaller limits apply after decoding. The store does not claim
to repair unrelated RPC transport or OS sandbox vulnerabilities. Candidate
isolation continues to depend on the existing Linux/bubblewrap sandbox. Local
in-process test shims verify workflow behavior, not operating-system isolation.

Each artifact's SHA-256 covers the canonical protocol/name/version/parameters/code
envelope. A reference must supply the matching digest. Active resolution uses the
store's validated immutable bytes, not arbitrary files selected by the candidate.
The report includes the saved catalog, selected reference, analysis protocol, and
final bound-source SHA-256. `submission.json` retains the scorer-compatible
`predictor_code`, `claims`, `explanation` schema; `predictor.py` includes everything
needed for fresh-process replay. `source_digest()` already hashes the new module
and the modified runner/worker. Persisted snapshots aid audit/recovery, but this
version does not implement resumption of an interrupted scientific episode or
guarantee power-loss durability of directory metadata.

## Validation and future integration

The offline integration test fits a coefficient from actual public observations,
saves it, deliberately raises an error, drops all worker variables, reads the
snapshot in a new analysis namespace, and submits the named reference. The frozen
predictor then reproduces unseen query values. Other tests cover quotas,
nonfinite/deep/cyclic/object input, attempted path traversal, failed publication,
immutable versions, exact digest binding, cross-episode isolation, JSON injection
strings, future imports and removal of capabilities from legacy worker calls.

Run:

```sh
python -m pytest env/tests/test_model_snapshots.py env/tests/test_analysis_feedback.py env/tests/test_pilot_protocol.py -q
```

The native test additionally uses real `CandidateProxy` callbacks, confirms that
private host files are absent, and runs the bound predictor in a fresh sandbox.
It runs only on Linux with bubblewrap; unsupported hosts skip that one test.

For a future evaluation, predeclare `analysis_protocol` in every affected
instance, freeze the updated source, validate the native test on that executor,
and identify this interface version in the cohort report. Compare it separately
from legacy cohorts because it changes the candidate's persistence capability.
The prospective-rival runner is not modified; it can later reuse the same store
and bound-source function under its own declared action and budget contract.
