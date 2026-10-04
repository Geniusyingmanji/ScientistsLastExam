# DeepSeek V4 Pro corrected paired evaluation

Candidate: `deepseek-v4-pro-0813`. Reference: the completed 72-run GPT-5.6
campaign in `../sle-unified12-20261004/`. See `../comparison.html` for results.

The same 12 worlds × 3 hidden instances × 2 repeats use identical world and
panel definitions, observation noise identities, prompts, scientific execution,
score weights and external budgets. DeepSeek uses native high reasoning and
streaming; GPT used native medium and nonstreaming. These provider settings are
not equivalent amounts of computation.

The corrected streaming adapter preserves an empty completed response as one
invalid-action turn, matching nonstream chat. It retains token usage and finish
reason, never exposes reasoning as a visible answer, and does not retry.
Both earlier transport/client pilots are archived separately; their public
hashes and counts are bound to this campaign's manifest. Their outcomes never
replace or join the corrected scores.

A full macro requires all 72 episodes to close. Undispatched episodes remain
missing. The first twelve retain the frozen infrastructure stop rule. Public
artifacts omit hidden seeds, parameters, targets, raw traces and credentials.
