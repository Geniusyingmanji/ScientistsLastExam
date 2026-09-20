# Measurement audit: discovery from evidence without an answer key

This is a **protocol fixture and generic measurement adapter**, not an admitted
hard science task. Its default hand-entered table has no empirical scientific
meaning. Operators may instead provide a provenance-documented observation
bundle. No hidden mechanism, simulator parameters, reference discovery, target
label, `evaluate` method, or scientific correctness scalar exists here.

Develop competing falsifiable hypotheses about the measurements. Describe why
an experiment could distinguish them, register predictions before observing
that experiment, and revise or reject hypotheses when evidence disagrees.
Conclude with the scope of support, counterevidence, unresolved alternatives,
and limitations. The evidence protocol checks the chronology and numerical
compatibility of claims; those checks do not prove that an explanation is true,
causal, novel, useful, or the only explanation compatible with the data.

## Available measurements and tools

The public problem contains a hash-bound data manifest, units, column meanings,
sample counts, provenance assertions, and exact tool schemas. The candidate
sees neither the data bundle's filesystem path nor the broker's private files.
It can repeatedly call tools and use the session's isolated Python analysis.

* `read_measurements` returns selected numeric columns from exploration rows;
  `partition` must be `exploration`, `offset` is zero-based, and `limit` is 1–256.
  Cost is returned rows times selected numeric columns.
* `summarize` computes a mean or a two-group mean difference. Supply all five
  arguments: `partition`, `column`, `statistic`, `group_column`, `group_values`.
  For a mean, both grouping fields are null. For `mean_difference`, the value
  is the second group's mean minus the first group's mean. Both groups need
  two samples; otherwise the observation reports `insufficient_samples` and
  null numerical values. Cost is the total number of rows in the requested
  partition, independent of grouping. Preflight costs therefore cannot leak
  sealed group membership.

Both tools issue broker observation records. Queries reuse fixed observed rows;
repeating a query never creates an independent sample. All queries are charged,
including repetitions. The total budget is 4096 units across exploration and
replication. The runner may impose stricter step, time, and analysis limits.
Each observation binds its source CSV hash, partition, measured columns, and
the actual included sample IDs in `evidence_scope`. The ledger uses overlapping
source footprints to detect already exposed measurements even when the earlier
query returned raw rows and the later query returns a summary. A prediction
registered after partial exposure is not counted as prospective evidence for
that reused source. Row IDs are disclosed only when measurements are observed.

For a scalar prospective prediction, use the generic protocol measurement
selector `{"path": ["value"], "reducer": "scalar"}` on a `summarize` test.
Register the complete test and competing hypothesis predictions before running
it. Dossier `replication_tests` identify already registered sealed-partition
tests. The runner reserves their costs before immutable commitment, opens the
replication partition once, and executes them. Exploration closes at this
transition; no revised dossier or new replication test is accepted afterwards.
The adapter itself supplies observations; the generic broker owns registration,
commitment, evidence identity, and review.

`examples/discovery_actions.json` is a complete deterministic action replay:
two competing hypotheses, an exploration test registered before any data are
observed, a separate reserved-partition prediction, and a committed dossier.
It asserts only descriptive compatibility in the engineering fixture. It is
not a reference scientific solution or evidence of model discovery ability.

## What the diagnostics mean

The reported standard error is sample standard deviation divided by sqrt(n).
For independent groups it is the square root of the sum of the two squared
standard errors. This formula can be inappropriate for clustered, correlated,
or selected measurements; those possibilities belong in assumptions and
limitations. The adapter does not infer randomization, correct multiplicity,
test significance, or decide causality. Groups are numeric observed categories,
not an assertion that treatment was randomly assigned.

A compatible held-out mean is evidence about that mean under the stated
conditions. It cannot rule out every alternative mechanism. Wide predictions
can be compatible without being discriminating. A failed prediction is useful
counterevidence, and an inconclusive result is allowed. Chronological process
checks and compatibility counts must be reported separately from expert
judgment of reasoning, novelty, scientific importance, and external validity.

## Operator measurement bundle

`MeasurementEnvironment.from_bundle(path)` and `create_environment(seed,
bundle_path=path)` accept exactly two files: `manifest.json` and
`measurements.csv`. The bundle and every ancestor must have no symlinks; both
files must be ordinary files; extra files and directories are rejected. Data
is loaded into an immutable episode snapshot, and content hashes enter the
public binding. Hashes bind bytes, not the truth of provenance statements.

The manifest has exactly `schema_version` (1), `dataset_id`, `provenance`,
`columns`, and `files`. `files` is
`{"measurements.csv": "<sha256 of exact CSV bytes>"}`. Each column object has
exactly `name`, `unit`, and `description`. There may be 1–16 numeric columns.
The CSV header must be `sample_id,partition,<column names in manifest order>`;
sample IDs must be globally unique. Partition values are `exploration` and
`replication`, with at least two rows each. Measurements must be finite and
have absolute magnitude at most 1e100; missing values require an explicit
upstream documented handling policy. At most 10,000 rows and 4 MiB per file
are accepted.

Provenance has exactly these fields:

* `kind`: `observed_measurements` or `protocol_fixture`;
* `citation`, `collection_description`, `target_population`,
  `independence_unit`: nonempty descriptions;
* `replication_design`: `held_out_same_source`, `independent_collection`, or
  `protocol_fixture` (the last must match fixture kind);
* `limitations`: one or more explicit limitations.

Assign partitions before the agent session. A same-source held-out partition
is not an independent external replication. An independent-collection label
is an operator assertion requiring scientific review, not verified metadata.
Use one row per declared independence unit; the loader checks unique IDs, not
actual subject identity, independence, collection practices, consent, or
sampling validity. Public source data may already be known to a model; network
isolation and sealed files do not remove training contamination.

The default fixture and every external bundle use the same table for every
runner seed. Repeated seed runs are **not distinct worlds or fresh samples**.
The fixture supports engineering tests only. Real scientific claims require
appropriate observed datasets, provenance review, independent measurement
where possible, expert assessment, and calibration of model behavior.
