# Unified twelve-world evaluation

The user requested a common scoring protocol and new GPT-5.6 evaluations of the
original seven worlds and the five prospective worlds. This campaign uses
`sle-unified-score-1.0`. Historical scores and prospective verdicts are retained
as historical evidence, not converted into new scores.

The twelve worlds are microecology, coupled oscillators, reaction kinetics, heat
transport, gene regulation, Ising spin, hysteresis material, molecular forces,
climate response, catalyst aging, field ecology, and phase equilibria.

## Frozen design

- Three fresh hidden instances per world, two agent runs per instance: 72 runs.
- GPT-5.6 (`gpt-5.6-sol`), medium reasoning, at most 8,000 output tokens per
  request, 16 requests per run, 1,152 requests in a new ledger. No automatic
  retries or replacement episodes. The prior 720-request ledger is unchanged.
- Each run has 14 exploration turns and two final submission opportunities,
  at most 48 exploration experiments and 30,000 apparatus cost units, 180 active
  analysis seconds, and 3,600 wall seconds including verification. Eight workers.
  Apparatus units do not imply equal physical difficulty or cost across domains.
- The same public tool contract, persistent model snapshots, and scientific task
  apply throughout. Existing apparatus descriptions and their disclosed physical
  priors remain visible; this is not a controlled test of equal prior knowledge.
- The two runs of an instance share the hidden world and host prediction panels,
  but not observations or independent claim-replication noise keys. Uncertainty
  analyses must cluster by instance; six runs are three independent worlds.
- Before inference, freeze source digest, model configuration, all instance IDs,
  private panel hashes and random seeds. Exclude seeds found in saved historical
  manifests and exclusion records; known historical coverage gaps remain.

## Common score

Each run receives 50% new-condition prediction, 30% control-shift prediction, and
20% quantitative effect replication. Every component is on a 0–100 scale.

For each of eight host-chosen experiments in each prediction panel, compute
channel-scaled RMSE over retained output cells against the simulator's clean
expected response. Transform it with `100 * exp(-RMSE / 0.1)` and average
experiments equally. Component errors are squared before averaging and cannot
cancel by sign. Publicly assigned or redundant outputs are excluded according
to `unified_panels.mask_contract()`. Static row zero and habitat zero remain
valid; unknown initial states are not dropped merely because time is zero.

The molecular condition panel uses new geometries at 450 K; its control-shift
panel also varies temperature. Other domains retain their existing documented
host sampling domains. These panels measure predictive coverage of their stated
domains, not all physically legal experiments. Habitat contrasts are not
automatically causal interventions.

The agent freely selects up to three paired quantitative effects. It freezes a
90% prediction interval for the mean of 32 independent treatment/control pairs.
The raw interval loss is width plus 20 times distance outside the interval;
the score is `100 * exp(-loss / (0.1 * channel_scale))`. Average over exactly
three slots; missing and duplicate slots score zero. Public eligibility excludes
known aliases and immediate assignments. Numeric effect verification does not
certify scientific importance, unique mechanisms, or discovery depth. The raw
interval loss is a proper interval score; its nonlinear bounded index is not.

Final main scores include all six planned runs per world: invalid/no submissions,
program failures, and infrastructure failures contribute zero, with reasons
reported separately. This is end-to-end performance; infrastructure-free model
means are secondary. Average the twelve world means equally only after all 72
runs close. No pending score is silently treated as zero. Three-cluster estimates
per world are exploratory, not stable model rankings.

## Execution and reporting

`python -m env.unified_campaign freeze` creates the new private manifest and
ledger. `run` verifies the frozen source and settings, starts with one fixed run
per world, and then executes the remaining fixed runs. At least three
infrastructure failures in the first twelve stop further dispatch for diagnosis;
these failures remain in the record. Scientific failures do not trigger stopping.

The exporter publishes only allowlisted aggregate metrics, endpoint statuses,
request counts and artifact hashes. Private seeds, targets, model code and API
configuration remain outside the repository/site. The unified HTML accepts this
public file via `docs/reports/render_overview.py --unified-data ...`. Previously
reviewed discoveries are labeled historical until new traces are reviewed.

This campaign unifies numerical scoring. It does not by itself calibrate
Discovery Depth, establish memory-contamination resistance, or make the earlier
two evaluation protocols comparable. Open-ended scientific conclusions still
require evidence review, including useful refutations and scope changes that
the numerical score does not fully reward.
