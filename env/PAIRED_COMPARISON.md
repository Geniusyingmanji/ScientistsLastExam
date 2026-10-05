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
Only the two campaign orchestration modules and the opt-in chat empty-output
adapter in `sle/llm.py` may differ. A new private directory
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

## Transport amendment, before the streaming comparison

The nonstream pilot reached its frozen infrastructure stop rule: all twelve
first-wave runs failed with `RemoteDisconnected` after 24 total requests
(12 returned, 12 failed). No scientific completion or 72-run macro was obtained.
A single separately logged replay of a failed request with streaming returned
in 120.01 seconds, reaching the same 8,000-token cap (`finish_reason=length`).
It is a transport diagnostic, not a repaired episode or scored result.

A new **streaming** campaign is therefore frozen against the same GPT design.
It preserves the output/request/experiment/analysis/wall budgets, native effort,
no-retry policy and first-wave stop rule. Streaming is its only change from the
nonstream DeepSeek configuration. Its manifest binds the failed pilot's public
artifact hash and counts. The failed pilot, trivial connectivity call and stream
diagnostic remain separately disclosed and are never merged into the new scores.
GPT used nonstream transport, so service/transport effects remain a limitation.


## Empty visible output amendment

The first streaming pilot exposed a client inconsistency: a complete response
containing only reasoning was raised as a transport error, whereas nonstream
chat returns an empty string. The corrected prospective campaign enables
`chat_empty_response_as_text`: completed empty answers consume an invalid-action
turn, preserving usage and stop reason. It never substitutes reasoning content,
retries requests, or increases any budget. Real transport errors still fail.
Both earlier pilots remain separate and their public hashes are bound in the
corrected manifest. No previously scored episode is repaired or pooled.

## Prospective extended-output continuation (2026-10-05)

The corrected campaign stopped after twelve runs: ten request deadlines and two
round-limit non-submissions, with 94 requests; sixty slots were never dispatched.
Its report and all raw results remain immutable. A separately logged diagnostic
replayed one previously interrupted request: HTTP 200 and first bytes arrived at
2.204 seconds, data continued arriving, and the 245-second deadline fired before
any terminal SSE marker. This one replay supports a generation-time bottleneck;
it does not establish the cause of all ten historical failures.

The explicit `extended-output-v1` profile is a **different-budget system
evaluation**, not an equal-budget model ranking. It changes only these limits:

| Limit | Frozen GPT / earlier DeepSeek | New DeepSeek |
| --- | ---: | ---: |
| Output tokens per request | 8,000 | 16,000 |
| Socket timeout seconds | 180 | 900 |
| Episode wall seconds | 3,600 | 14,400 |

The existing outer request deadline remains socket timeout + 65 seconds, bounded
by remaining episode time. The longer episode limit prevents the new request
allowance from silently consuming the entire original wall budget. Request
counts (16 per episode, 1,152 for the campaign), 8 workers, experiments (48),
experimental cost, active analysis (180 seconds), science source, scoring,
instances, panels and action prompts remain unchanged. Maximum configured output
allowance becomes 18,432,000 tokens over the full campaign; actual usage is
reported separately and missing usage is unknown. No automatic retry or repair
of earlier submissions is permitted. Empty visible replies remain invalid
actions and never expose internal reasoning as an answer.

Before launching this new frozen campaign, a separate one-request diagnostic
must finish with a terminal event and nonempty visible output under the proposed
configuration. It is not a score or an extra episode. The first-twelve stop rule
still applies: at least three infrastructure failures stop further dispatch.
No later campaign or additional budget increase is automatic.

The manifest binds both the GPT design and the corrected stopped predecessor.
New public results use a separate page and data file. Any eventual paired score
difference and cluster interval describe the two observed systems under their
declared budgets; they cannot isolate model capability from compute or latency.
