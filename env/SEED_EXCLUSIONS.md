# Operator seed exclusions for future cohorts

`create_manifest(..., seed_exclusions=body)` and
`create_paired_design(..., seed_exclusions=body)` accept an explicit private
operator corpus. Both planning CLIs accept `--seed-exclusions-file PATH`.
Nothing searches directories, infers exposure from old reports, or fills in a
list for the operator. These are **world seeds**, not panel or observation keys.
The operator must maintain and review the corpus before freezing a new cohort.

The exact JSON schema is:

```json
{
  "protocol": "sle-seed-exclusions-0.1",
  "environments": {
    "ising_spin": [901, 903],
    "spin_echo": [911]
  }
}
```

These numbers are fictional test examples, not an exposure inventory. Names
must be registered worlds. A corpus can include worlds not selected by this
particular cohort, so one corpus can be reused across plans. Every seed list
must already be sorted and unique. Values must be JSON integers in
`0..2147483647`; booleans, floats, duplicate JSON keys, unknown fields/worlds,
nonfinite values, and other schemas are rejected. Limits are 262144 UTF-8
bytes, 4096 seeds per world, and 16384 seeds total. The explicit path must be a
regular file; size is checked before opening and the read is also bounded.

The existing reserved seeds remain excluded in every world, as do world seeds
already assigned to another row in the same cohort. The optional corpus adds
per-world exclusions. Each row permits at most 4096 world-seed proposals,
including initial selection, exclusion retries, and balanced-stratum retries.
The existing 128 stratum-check bound also remains. Panel-seed draws do not
consume the world-seed counter. Exhaustion raises before a manifest is written;
no partial cohort or substitute sampling strategy is emitted.

Without the option (`None`), ordinary sampling order and the 0.4 manifest
shape remain unchanged. Only formerly unbounded reserved-seed retry loops now
have a finite failure bound. Source hashes naturally change with source code.
An explicitly supplied corpus, even an empty one, creates cohort protocol
`sle-pilot-cohort-0.5`, with the complete validated corpus in `seed_exclusions`
and its canonical SHA-256 in `seed_exclusions_sha256`. Every row carries that
same hash. Canonical hashing uses UTF-8 compact JSON with sorted object keys.
It does not alter seed lists or discover additional exclusions.

`run_cohort` strictly parses JSON and checks this binding, its protocol, and
all row seeds before reading credentials, constructing a ledger/client/worker,
or creating a directory. Paired plans freeze the same complete corpus and
hash across all arms and the private shared contract; `validate_design` checks
those bindings as well as its existing arm invariants. Public summaries expose
only the exclusion protocol, environment count, seed count, and hash. The
private corpus, manifests, and paired index must stay private. A hash is a
consistency identifier, not a confidentiality guarantee.

This is semantic consistency validation, **not independent manifest
authentication**. Row hashes bind each row to the declared corpus, rather than
signing its seed or authenticating operator history. A coherent rewrite of an
entire package, including protocol downgrade to legacy, is outside this guard.
Retain an independently controlled immutable plan if that threat matters.
Legacy inputs still validate as legacy; historical cohorts are not upgraded or
relabeled. Existing source-hash checks still require the appropriate frozen
checkout when executing old cohorts.

Example future planning command (requires an operator-prepared private file):

```sh
python -m env freeze --cohort future-example --environments ising_spin \
  --instances 5 --seed-exclusions-file /private/operator-exclusions.json \
  --output /private/future-example-manifest.json

python -m env.paired_design --design-id future-pair --environments ising_spin \
  --factor rounds --values 8,16 --seed-exclusions-file /private/operator-exclusions.json \
  --output /private/future-pair
```

The sampler prevents selecting declared excluded seeds. It does not establish
contamination resistance, independence of latent structure, meaningful task
novelty, or a statistical structural holdout. It does not authorize execution,
change request budgets, collect outcomes, or regrade past cohorts.
