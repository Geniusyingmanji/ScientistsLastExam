# Twelve-world common-protocol evaluation

Open [the standalone unified report](../overview.html) in a browser after
downloading the repository. GitHub's ordinary file view displays HTML source;
it does not host the rendered page.

`data.json` is an allowlisted export from the completed, fixed 72-run campaign.
The unified report does not reuse historical scores as new results.

GPT-5.6 scored **64.314108 / 100**, averaging six planned runs per world and
then weighting all twelve worlds equally. Valid completion was **62 / 72
(86.1%)**. Five API failures, four invalid prediction programs and one run
without a final submission contribute zero to the main score. Excluding only
API failures before averaging within each world gives the auxiliary score
**68.441583 / 100**. The campaign used 1,052 of 1,152 allowed API attempts;
there were no automatic retries or replacement runs.

Protocol: `sle-unified-score-1.0`, documented in
[`env/UNIFIED_EVALUATION.md`](../../../env/UNIFIED_EVALUATION.md).
Frozen evaluation source: `445b95fe85663969b52e7f7a52d94ff4ca20dd1d`.
The later report commit does not change this scientific source revision.

Each world has three independently generated instances and two runs per
instance. The main score includes failures as zero and weights worlds equally.
Two runs on one instance are not independent worlds. The score evaluates
prediction and effect replication, not scientific importance or discovery depth.

Public exports contain artifact hashes for provenance. Private seeds, validation
targets, raw model traces and API credentials are not included. Any published
scientific review is explicitly labeled with its evidence scope and reviewer
independence; model explanations alone are not treated as verified discoveries.

Regenerate the report from the repository root:

```sh
python3 docs/reports/render_overview.py \
  --unified-data docs/reports/sle-unified12-20261004/data.json
```

When the curated `review.json` is present, also pass
`--review-data docs/reports/sle-unified12-20261004/review.json` to include scientific
findings. The renderer checks each reviewed episode against the closed raw
report hash in the campaign export. Numerical aggregates and semantic review
remain separate inputs.
