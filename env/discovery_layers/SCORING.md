# Run scientific scoring

The trusted evaluator consumes a frozen evidence directory and a separate review
JSON. It never imports candidate code. Numeric prediction diagnostics alone do not
produce semantic scores. The reviewer follows THREE_STAGE_JUDGE.md, retains a
trace, and supplies evidence-backed criterion and module judgments.

```
python -m env.discovery_layers.judge --environment ecology \
  --evidence /private/run/evidence --decisions /private/run/review.json \
  --output /private/run/scientific-assessment.json
```

A prospective evidence manifest must include the exact judge-contract.json frozen
for that run. To inspect an older submission under a new rubric, explicitly use
`--retrospective` and a new output path. This does not change its original grading.
Do not mix supplementary assessments with prospective benchmark results.

Evidence manifest: JSON mapping relative file paths to SHA256 digests. All files
are verified before aggregation; all cited paths must belong to the manifest.
Scores require reasons and evidence, including zero. Laws additionally require
all predefined modules, equally averaged. Output retains decisions, contract,
rubric/reviewer/evidence hashes, result and process scores, and provisional status.
Omitted criteria remain pending/null. Existing output files are never overwritten.

A same-family judge is a provisional semantic assessment, not an objective proof
or calibrated universal scale. Scientific truth checks and acquisition overlap
must be assessed by the reviewer; file hashes only establish artifact identity.
