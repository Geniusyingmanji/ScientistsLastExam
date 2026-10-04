# DeepSeek V4 Pro nonstream transport pilot

The paired comparison hit its preregistered infrastructure stop rule. All twelve
first-wave episodes failed with `RemoteDisconnected`: 24 requests, 12 returned,
12 failed. The other sixty runs were not dispatched. No 72-run score exists.
These failures do not measure scientific discrimination against GPT-5.6.

The public export is preserved in `data.json`. One separately logged streaming
replay returned in 120.01 seconds with the fixed 8,000-token cap and a length
stop. It was diagnostic only and did not repair any episode.

A separate streaming campaign uses the same GPT reference instances and budgets;
its manifest binds this pilot's hash. See `../comparison.html` for the current
comparison and `../../../env/PAIRED_COMPARISON.md` for the design and amendment.
