# Three-species context discovery (prototype)

This is a new, unregistered environment version. Existing microecology and V1
results are unchanged. See PLAN.md for the frozen development unit and
DISCOVERY_RUBRIC.md for scoped equation recovery rather than exact-string grading.

The trusted kernel uses carbon-balanced metabolic fluxes and a regulatory state.
A secretes a signal which can change B's partition between C nutrient and
inhibitor production. Environmental sensitivity and finite regulatory response
create history-dependent interactions. Pool names exposed to candidates do not
identify chemical functions. The prototype has sensor noise only; biological
process variability remains future work, not an implemented feature.

`service.py` runs outside the candidate filesystem. `mcp_client.py` is the only
public bridge. It implements describe/experiment and spends one attempt on each
valid or invalid experiment, up to48. The candidate cannot request clean values,
hidden states, private parameters or evaluation targets.

The first g450 pilot uses GPT and Codex0.162.1,
GPT5.6sol/high. An outer bubblewrap namespace hides operator source, private data,
host credentials and host processes. Network loopback remains shared for the
existing inference proxy and experiment service; this is not a network adversary
security evaluation. Public analysis workspace is writable; runtime packages are
read-only. Filesystem denial probes precede model invocation.

The first pilot is engineering development, not a frozen six-case scientific
cohort. Codex's built-in reconnect behavior was observed despite the initial
no-retry intention; transport events must retain that discrepancy. Scientific
scores are unavailable until a final executable and discovery report exist.
