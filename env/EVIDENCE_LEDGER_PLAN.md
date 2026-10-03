# Next interface experiment: persistent, bounded evidence

This is an implementation and comparison plan. The evidence ledger is not
implemented, no new model cohort is scheduled, and no performance improvement is
claimed. Existing named [model snapshots](MODEL_SNAPSHOTS.md) are already an
optional capability; this proposal complements them with selected evidence that
remains visible at finalization.

The microbial, oscillator and reaction audits found useful analyses followed by
lost or changed model parameters, citation/protocol mismatches and unreconciled
predictions. These records motivate a trial; they do not prove that the interface
caused the errors. Early submission, remaining-budget displays, research notes,
an observation catalog and the latest two analysis results already exist.

## Implementation contract

1. Keep the canonical experiment/analysis/code archive immutable. A visible card
   is a bounded projection of an already-public value or candidate-authored text,
   with an exact record pointer, source digest, coordinate and model version.
2. Let the candidate explicitly pin, replace, unpin or annotate cards. Separate
   evidence, predictions, model versions and interpretations. Scientific prose
   remains candidate-authored; the runner does not select promising findings,
   name a mechanism or generate a scientific verdict.
3. Preserve the last successful analysis reference separately from the latest
   timeout/error reference. A failed analysis never overwrites a successful
   result with null. Do not invent intermediate fitted state that was not saved.
4. Include the same selected ledger at every subsequent prompt and finalization.
   Reading pinned material uses the existing prompt budget and does not require
   another paid analysis call. Use a declared common prompt-packing policy so the
   treatment cannot silently receive more total context.
5. Bind predictions to recorded request order and exact target protocols.
   Same-request prediction-before-observation is allowed. Legacy statements with
   missing bindings remain unknown; recorded order is not authenticated time.
6. Validate metadata atomically and independently of the scientific action. A
   rejected ledger update preserves the old ledger and does not refund a model
   turn or invalidate an otherwise legal experiment. No silent truncation or
   automatic eviction of candidate-selected evidence.

Proposed visible limits are 16,384 total UTF-8 bytes, eight live cards, 1,536 bytes
per card, six referenced scalar cells per evidence card, 384 bytes per text field,
four update operations, four short action-status receipts and four diagnostics.
The total-byte cap takes precedence. Archived versions do not bypass existing
storage or retrieval limits.

Mechanical diagnostics may check exact pointers, digests, declared coordinates,
protocol differences, version/order, explicit reference-support ranges and
selected values against declared intervals. Missing inputs produce `not_checked`.
The minimal arithmetic is bounded subtraction of two selected saved numeric
literals; it performs no interpolation, fitting, simulation, uncertainty
estimation or search. Display units, operands and the declared numeric policy.
An interval for a fresh replicate mean is not adjudicated by comparing it with
one historical noisy pair.

## Acceptance before a model trial

Use synthetic public records to check exact copied values, unchanged history,
version identity, chronology with missing fields, nonfinite/oversized rejection,
atomic updates and persistence after timeouts. Confirm that hidden world state,
evaluation targets and other episodes are inaccessible. Check total prompt
packing and full resource receipts in the native isolation path. These checks
establish interface behavior, not scientific correctness.

Then freeze a small matched interface pilot, for example five predeclared pairs
of fresh microecology instances. Keep theory, model settings, all resource caps
and evaluation panels fixed; randomize condition order. Preserve rejected cards,
ignored diagnostics, failed fits and incomplete runs. Adaptive experiment
choices may diverge, so individual noisy records are not identical paired data.

Measure final availability of selected evidence, model-version continuity,
protocol/citation mismatches, retained failed predictions and actual token/CPU
cost. Review scientific support separately, blind to condition and private
scores, retaining disagreements. Five pairs are a feasibility study, not a
powered improvement claim or a scaling law. The comparison evaluates the
declared persistence/checking interface bundle; it does not isolate memory from
arithmetic checks. A new frozen cohort and sufficient reserved API budget are
required; the current 352-attempt campaign is not extended.
