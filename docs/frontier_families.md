# Frozen frontier families

## Why this is separate from a release score

A fixed benchmark release must be reproducible and comparable. A scientific frontier must also
be able to accept later problems, regimes, constructions, or discoveries without rewriting the
evidence produced by an earlier release. SLE therefore keeps two quantities separate:

- `combined_score` belongs to one frozen task package and is used for model comparison;
- `lifetime_frontier_credit` belongs to a stable task family and is an append-only record of
  independently verified frontier gains. The stored/CLI field is `lifetime_credit`;
  `lifetime_frontier_credit` is the descriptive name of the quantity.

An `uncapped` release score may exceed its score-one reference. It does not by itself prove that
the task will remain scientifically productive forever. Lifetime credit can grow across waves,
but must never be used to compare models that were evaluated on different frozen manifests.

At the 2026-09-12 integration snapshot, no task packages have `wave.yaml`. This is an opt-in
framework interface; its merge does not admit a family, award scientific credit,
or certify a model measurement.

## Opt-in metadata

Legacy task scoring needs no metadata migration. Existing run evidence does need a new run (see below). A family-aware package declares both fields in
`frontier_eval/metadata.yaml`:

```yaml
task_family_id: ScientificComputing/AdaptiveConservativePDEMethod
wave_id: wave-1
```

and ships `frontier_eval/wave.yaml`:

```yaml
schema_version: 1
task_family_id: ScientificComputing/AdaptiveConservativePDEMethod
wave_id: wave-1
predecessor_wave_sha256: null
cells:
  - id: smooth-advection-1d
    kind: optimization
    weight: 1.0
    objective: maximize
    reference_value: 0.0
    credit_scale: 1.0
    minimum_delta: 0.01
    semantic_contract:
      canonicalizer_id: conservative-scheme-v1
      canonicalizer_path: frontier_eval/contracts/conservative_scheme_v1.py
      canonicalizer_sha256: <sha256-of-versioned-canonicalizer-artifact>
      evidence_predicate_id: frozen-pde-panel-v1
      evidence_predicate_path: frontier_eval/contracts/pde_predicate_v1.py
      evidence_predicate_sha256: <sha256-of-versioned-verification-artifact>
      evaluation_panel_path: frontier_eval/contracts/pde_panel_v1.json
      evaluation_panel_sha256: <sha256-of-frozen-cell-panel>
      oracle_path: verification/evaluator.py
      oracle_sha256: <sha256-of-declared-evaluator-entrypoint>
```

For a discovery cell use `kind: discovery`, replace the objective fields with a positive
`credit_per_claim`, and add a stable `novelty_namespace`. The semantic contract binds the
versioned canonicalizer, confirmation predicate, frozen evaluation panel, and declared evaluator
entrypoint; paths must stay in the task package and their bytes must match the declared hashes.
`task_package_sha256`, rather than `oracle_sha256` alone, binds the complete task package including
the evaluator's imported helpers and data. The loader derives
`definition_sha256` from the
normalized cell semantics.
Authors may include that hash explicitly; a mismatch is rejected. A cell ID cannot later be
reused with different semantics.

The first wave has a null predecessor. A later wave names the semantic manifest SHA-256 of the
previous wave. Every historical wave must remain repository-visible: the repository audit rejects
missing predecessors, multiple genesis waves, forks, repeated wave IDs, and changed cell
definitions. Run manifests and evaluation requests also bind the current family ID, wave ID, wave
manifest hash, task package hash, runtime source hash, and trusted evaluator runtime condition.
The trusted runtime fingerprint identifies the Python ABI and audited distribution versions. It is
not a claim that every installed runtime byte is bit-identical.

The NMR candidate profile permits serial Numba JIT compilation. It fixes
`NUMBA_NUM_THREADS=1` and `NUMBA_THREADING_LAYER=workqueue`, and masks Numba's optional
`tbbpool` binary. The TBB backend is outside this single-threaded sandbox profile;
its absent `libtbb` dependency must not prevent ordinary `nmrsim.qm` imports. Shared
library checks still fail closed for every binary exposed to candidates.

## Trusted record contract

`FrontierLedger.record()` deliberately rejects direct callers. The only public credit path is
`promote_frontier_receipt()`: it first verifies the committed greedy trajectory and all durable
evaluation receipts, then extracts `frontier_records` and binds the request, metrics, candidate,
complete task package, runtime source, trusted runtime condition, and wave hashes into the event.
A candidate program must never choose its own canonical ID, scientific cell, weight, reference,
or minimum delta.

Model runs only produce receipts. A trusted operator promotes a receipt into one explicitly chosen,
cross-run canonical evidence root with `python -m sle frontier-promote --task ... --run-workdir ...
--ledger-root ... --request-id ...`. The command rechecks the current task/runtime hashes and the
run manifest before writing. Passing an individual model run directory as `--ledger-root` would
create an isolated ledger and is not a valid campaign-wide lifetime total.

`python -m sle verify-run --workdir ...` checks internal content consistency under the budget
declared by that run. Release/cohort evidence must additionally pass `--expected-budget N`; the
cohort runner supplies this external campaign contract automatically.

The verifier currently requires a completed proposal budget. A run that normally
stops at its active-wall horizon before consuming that budget is rejected as
incomplete by this contract. Clock checks do not establish that arbitrary two-hour
runs can be verified or promoted. The logical active clock also excludes failed
physical attempts and downtime between resumed invocations.

A completed greedy checkpoint can continue with a larger proposal budget. Historical
requests and receipts keep their original allocation and content hashes: allocations must
be nondecreasing, cover their proposal step, and stay within the final verified budget.
An unfinished baseline must first recover under its original budget; an already drawn
pending proposal must retain its original prompt before any extension. Extending a run
does not turn its earlier receipts into evidence for a separately allocated fresh run.

The first credited event for a wave freezes its task contract, complete task package, runtime
source, and trusted evaluator runtime condition. Later events in that wave must match all four.
Frontier events use their own schema version independently of wave manifests and evaluation
receipts. A ledger written under an older event schema fails closed and is not silently rewritten.

An optimization record contains:

```json
{"cell_id": "smooth-advection-1d", "canonical_id": "sha256-or-canonical-method-id", "value": 1.25}
```

It earns credit only when it improves the recorded incumbent by at least `minimum_delta`:

```text
credit = weight * scientific_improvement / credit_scale
```

A discovery record contains a frozen cell ID and evaluator-derived canonical claim ID. Deduplication
uses `task_family_id + novelty_namespace + canonical_id`. It prevents a repeated claim
within the same family/namespace, not semantic duplication under a different namespace. The first verified occurrence earns
`weight * credit_per_claim`; repetitions earn zero. Discovery
mechanism recovery, false-discovery rate, calibrated refusal, and attempted-discovery coverage
remain separate release metrics. Lifetime credit is nonnegative, cumulative, and does not
include false-discovery or refusal penalties; optimization record credit has no generic upper
bound. It is not an overall submission-quality score. The task evaluator must verify claims
and the contribution gate requires baseline/valid blanket-abstention results to emit no records.
Any family-level FDR eligibility policy or credit cap requires explicit maintainer approval;
this implementation does not silently introduce either policy.

## Integrity properties

The canonical ledger contains complete evaluator receipts and hidden metrics. Keep its root
outside every Git repository; the writer enforces owner-only ledger/event directories (0700)
and creates event files with mode 0600. Publish only a reviewed aggregate and ledger head hash,
never the raw ledger.

The local ledger stores each event as a separately fsynced, atomically published JSON document
under a POSIX advisory lock. Every event binds the previous event hash and is deterministically
replayed before another event is appended. Replay recomputes all deduplication and credit
decisions rather than trusting stored totals; a crash cannot leave a half-written committed event.

The hash chain is tamper-evident, not an external signature. Confirmatory use must publish or
otherwise independently anchor the ledger head hash. A local operator able to rewrite the whole
repository and every external receipt is outside this module's trust boundary.

The following never earns credit:

- an invalid or unverified evaluator result;
- a repeated canonical artifact within one cell or discovery within one family/namespace;
- an optimization smaller than the frozen minimum scientific delta;
- a candidate-created cell or weight;
- a changed cell definition under an existing cell ID;
- a wave that does not extend the recorded predecessor chain.

The repository family audit also rejects literally identical cell semantics under renamed IDs
or namespaces. It cannot decide whether differently encoded contracts represent the same
science. Wave review must reject renamed scientific claims, easy added cells, and surrogate-only
claims lacking required high-fidelity or fresh confirmation. These are task/review obligations,
not generic ledger invariants.

The same evaluation request is idempotent. A repeated request returns its original decision; a
different metrics receipt for that request is rejected. Within one wave, the same candidate artifact
must always map to the same canonical record set.

Synthetic deterministic worlds can establish benchmark-frontier credit. They must not be
reported as real-world scientific discovery without the task card's independent confirmation.

## Existing run evidence

Runs created before the trusted runtime binding was introduced cannot be resumed with this
framework, including legacy tasks without a family. Their manifests lack the required
`trusted_evaluator_runtime` and use the previous `runtime_environment` structure.
`verify-run` rejects these old runs and published summaries do not restore their validity.
Evaluation requests now bind `trusted_evaluator_runtime_sha256` and `frozen_cell`, so old
request hashes and ledger receipts cannot be reverified or promoted under this runtime.

Keep historical directories and reports as historical evidence under their original revision.
Start replacement runs in fresh directories with the new runtime and budget; do not edit old
manifests or resume an in-flight long-horizon run across this upgrade. An in-flight run may
finish under its original checkout, but it must be rerun to produce evidence for this framework.
Recovery audit rebinding does not migrate candidate runs or their receipts.

The existing recovery audit references an intermediate source revision. Integration must retain
that commit in history (a real merge, not squash); otherwise provenance checks cannot read it.
The integration review records the fresh baseline, recovery and preflight evidence
separately; those checks do not migrate historical model runs.
