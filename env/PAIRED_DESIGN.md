# Future paired cohort planner

`env.paired_design` creates a prospective, single-factor plan. It calls
`campaign.create_manifest` once to sample fresh hidden instances and private
panel specifications, then derives the planned arms from that template. It does
not run a cohort, execute candidate code or a World trajectory, contact a model
API, or inspect/create/extend a request ledger. Historical batches cannot be
imported or retroactively treated as paired.

Two factors are supported, in separate designs:

| Factor | Arm values | Held fixed |
|---|---|---|
| `rounds` | Two to four distinct integer allowances in [3,32], each exceeding the closing allowance | Snapshot availability and every other experiment, analysis, wall-time and verification limit |
| `analysis_protocol` | Exactly `legacy` and `sle-analysis-snapshots-0.1` | Rounds, exploration/closing allowance and all other resource limits |

`closing_opportunities` is common to all arms, defaults to 2, and must be at
least 2. In every arm `exploration_rounds = rounds - closing_opportunities`.
Changing a round allowance therefore changes the derived exploration allowance;
this is one controlled factor, not two independent budget choices. At least one
exploration round is required. The existing identical wall-time rule can still
force earlier closing, so the nominal scheduled opportunities are not a promise
that a model consumes all rounds. Experiment count/units and active analysis
time stay fixed even in the larger-round arm.

The worlds, private panels, source revision, task profile, scientific presentation
profile, scoring contract, model, decoding, and all non-factor limits are fixed
across arms. Snapshot treatment necessarily changes its public API contract,
instructions and allowed submission reference; scientific world presentation
and task orientation remain the same. There is no per-arm arbitrary override
dictionary. The validator rejects confounded arm differences, including changed
experiment/analysis budgets, source, task, presentation or decoding, even if an
operator recomputes a modified arm's manifest hash.

Within each pair, these values are identical:

* environment and hidden `world_seed`;
* `panel_seed` and the hashes of both private panel-specification lists;
* optional trusted sampling stratum;
* all common scientific and execution settings above.

Every arm has a distinct cohort and episode ID. Every episode receives a fresh,
unique `confirmation_key`. Exploration noise in the existing runner is keyed by
`episode_id:observation_id`, so two arms issuing the same experiment still get
independently keyed measurements. This is **not common random numbers**. The model
sampling itself is not seed-controlled. Agents can choose different experiments,
and fixed private panels do not imply identical learning trajectories.

The planner does not assign or execute a run order. A future execution protocol
should address temporal/provider drift and scheduling effects, for example by
counterbalancing arm order, before outcomes are collected. Pairing controls
instance and test-panel heterogeneity; it does not remove every source of
variation or establish a scaling law by itself.

Example round-allowance plan, five fresh pairs in one world:

```sh
python -m env.paired_design \
  --design-id future-rounds-example \
  --environments ising_spin --instances 5 \
  --factor rounds --values 8,16 --closing-opportunities 2 \
  --analysis-protocol sle-analysis-snapshots-0.1 \
  --task-profile mechanism_discrimination \
  --presentation-profile apparatus_only \
  --output /private/future-plans/rounds-example
```

This plans 5 pairs, 10 episodes, and **120 maximum model requests**. Snapshot
availability is held fixed. To isolate snapshot availability instead:

```sh
python -m env.paired_design \
  --design-id future-snapshots-example \
  --environments ising_spin --instances 5 \
  --factor analysis_protocol --values legacy,sle-analysis-snapshots-0.1 \
  --rounds 12 --closing-opportunities 2 \
  --task-profile mechanism_discrimination \
  --presentation-profile apparatus_only \
  --output /private/future-plans/snapshots-example
```

This also plans 5 pairs, 10 episodes, and **120 maximum model requests**. For
multiple selected worlds, counts multiply by the number of worlds. Optional
`--balanced-strata` names must be supported selected worlds, as in the existing
campaign contract; the same sampled class is then shared across each pair.
`apparatus_only` remains limited to its audited oscillator/Ising environments.

The Python API is `create_paired_design(design_id, names, factor=..., values=...,
...)`, followed by optional `write_design(design, new_directory)`.
`validate_design` checks the pair memberships, manifest hashes, single-factor
differences, unique keys, public count allowlist and required resource limits.
It performs no resimulation. Planning/writing also require the current source
digest to match the frozen template; source drift fails closed. Freeze from a
single immutable source checkout after development is complete. Do not edit a
hash to revive a stale plan, and choose a fresh design ID for a new plan.

Written files are:

* `a1-manifest-private.json`, `a2-manifest-private.json`, and further arm manifests
  when applicable, in the existing campaign manifest format;
* `paired-index-private.json`, containing shared contracts, private pair identities,
  world/panel seeds and hashes, membership, factor values and arm manifest hashes;
* `public-summary.json`, containing only protocol/plan status, planned pair/arm/
  episode counts, total maximum API attempts and `ledger_modified: false`.

The output directory must be new. Private files are mode 0600 inside a mode 0700
directory. No dataset, historical report, cohort result or ledger is changed.
Maximum requests equal the sum of `episodes_in_arm × rounds_in_arm` across all
arms, not the maximum of arm budgets. It is a planning upper bound, **not an
authorization to spend requests**. The existing 352-request cap remains untouched.
A plan may exceed it; the displayed requirement makes the shortfall reviewable.
Any execution needs a separate explicit decision and a check of the actual
remaining budget. This module has no run, ledger-path or cap-increase command.

```sh
python -m pytest env/tests/test_paired_design.py -q
```

Tests cover single-template sampling, real panel-hash equality, independent keys,
fixed budgets/closing opportunities, balanced private strata, rejection of mixed
factors and tampered settings, count-only export, immutable output directories,
source drift and forbidden network/ledger/execution calls. They collect no model
outcomes and support no claims about existing model performance.
