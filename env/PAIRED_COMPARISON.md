# Paired DeepSeek V4 Pro comparison

This prospective comparison reuses the complete 2026-10-04 GPT-5.6 campaign's
72 episode definitions: twelve worlds, three hidden instances each, two repeats.
The reference main score is 64.314108/100 and valid completion is 62/72.

The candidate is `deepseek-v4-pro-0813`, using the same configured API gateway.
One trivial connectivity call is separate from the evaluation. Native chat uses
`max_tokens` and `reasoning_effort=high`; GPT used `max_completion_tokens` and
`reasoning_effort=medium`. Effort labels are not equivalent across providers.
Both retain the 8,000 output cap, 180-second request timeout, 16 requests,
14 exploration rounds, 48 experiments, 30,000 units, 180 analysis seconds and
3,600-second episode wall limit. Eight workers and the 1,152-attempt cap remain
fixed. No retries, replacements or retrospective program repairs are allowed.
The first twelve runs retain the reference infrastructure stop rule.

`freeze-paired` reads the private reference manifest and validates its hash and
source archive. World generators, prompts, runner, sandbox, panel generator,
scoring, masks and claim verification must be byte-identical to the reference.
Only the two campaign orchestration modules may differ. A new private directory
and ledger are mandatory. No reference artifacts are overwritten.

Episode definitions, including world/panel seeds, panel hashes, episode IDs and
confirmation keys, are copied exactly. Thus identical observation-index/spec
requests and confirmation contrasts can share measurement randomness. Each
model independently chooses its experiments and predictions; reference model
traces and fitted programs are not supplied to DeepSeek. Identical episode IDs
are scoped by distinct campaign directories and model labels.

## Analysis fixed before candidate results

- Primary: all 72 planned episode scores, failures zero, six runs per world,
  twelve worlds equally weighted. Do not publish a final macro before closure.
- Show both models' three component means, valid completion, API failures,
  invalid programs, unfinished submissions, calls and actual reported model IDs.
- Pair by environment, instance index and repeat index. Report candidate minus
  reference, per-environment means and wins/ties/losses, without selecting runs.
- Average two repeats within each instance. Use the 36 instance pairs, with a
  fixed-seed bootstrap resampling three instance pairs within each of the twelve
  fixed environments, for a descriptive 95% interval of the macro difference.
  It is conditional on these environment families; only three independent
  instances per environment is a serious limitation. Do not treat 72 episodes
  as independent worlds or infer a stable general ranking.
- Separately report model-only means excluding infrastructure failures, plus a
  matched sensitivity comparison excluding a pair if either side has such a
  failure. These are descriptive selections, not fault-free causal estimates.
- Describe score saturation: fractions at or above 95 and at or below 5, per
  model and world; inspect whether model differences concentrate in delivery,
  prediction or quantitative claims. These cutoffs do not define discoveries.
- Inspect scientific evidence in changed or representative runs. Distinguish
  actual fitted/validated models, local reproduced effects, mechanism evidence,
  and final submission failures. Do not infer discovery depth from a score gap.

The comparison is sequential, not a randomized simultaneous service trial.
Provider reliability, hidden implementation differences and native reasoning
settings can affect the gap. A single comparator can demonstrate sample-level
separation or saturation; it cannot establish broad benchmark discrimination,
causal model ability, calibrated Discovery Depth or contamination immunity.
