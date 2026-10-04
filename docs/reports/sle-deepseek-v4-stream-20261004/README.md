# DeepSeek V4 Pro streaming client diagnostic

This archived pilot uses the unchanged GPT scientific instances and a streaming
transport, before the empty-visible-output adapter fix. It is not the corrected
model comparison and must never be pooled into its scores.

Nine closed runs exposed the old client raising complete replies without visible text
as wire decode errors; every such terminal response used 8,000 output tokens.
The saved usage does not independently identify how the provider allocated
those tokens internally. This incorrectly activated the infrastructure failure path. Real request
timeouts are distinct and remain transport failures. The original reports and
ledger are preserved without retrospective repairs.

See `../comparison.html` for the current paired comparison and
`../../../env/PAIRED_COMPARISON.md` for the protocol history.
Final pilot counts are taken from this directory's data.json; unset episodes
were not scored and cannot be interpreted as zero scientific ability.

Final preserved status: 12 closed, 64 requests (61 returned and 3 interrupted
at request deadlines). Nine terminal failures were empty-output decoder errors;
three were real request deadlines. No remaining 60 episodes were dispatched.
No completed scientific submissions or full 72-run score were obtained.
