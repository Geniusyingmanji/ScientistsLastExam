# DeepSeek V4 Pro 32k continuation

Model: deepseek-v4-pro-0813. Frozen manifest: 0fec9da6ae722a06cbc321d47df928214cd82637eb750e46927deae27ab88d61.

Same twelve-world scientific design as the GPT baseline, but larger output and time budgets: 32,000 output tokens, 900-second socket timeout and 14,400-second episode wall limit. Other action and score limits remain unchanged. This is not an equal-budget model ranking.

Maximum 72 runs, 8 workers, 16 requests/run and 1,152 total requests. No retries or replacement runs. Stop after the first twelve if at least three infrastructure failures occur. Pending slots stay missing. Prior cohorts and diagnostic requests are never merged.

Public progress: data.json. Rendered report: ../deepseek-extended.html. No full macro score before all 72 slots settle. Raw trajectories and hidden targets remain private.
