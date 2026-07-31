# CatalystDeactivationLab — run a stateful catalyst laboratory under instrument drift

## Scientific setting

Catalytic rate measurements are path dependent when each reaction irreversibly deactivates a
finite catalyst coupon. Instrument gain and baseline can also drift while parallel reactors
finish out of order. Treating an old observation as if it belonged to the current coupon or
silently retrying a destructive experiment can therefore corrupt a kinetic conclusion.

Supported worlds follow the public reduced-order model

```text
q(T, C) = 10**log10_A * exp(-Ea / (R*T)) * C / (1 + 0.4*C)
lambda(T, C) = d_ref * C * exp(30000/R * (1/500 - 1/T))
activity_after = activity_before * exp(-lambda * duration)
true_product = activity_before * q/lambda * (1 - exp(-lambda * duration))
raw_signal = gain(event_index) * true_product + offset(event_index) + noise
```

where gain and offset are linear in physical event index. Some worlds have resolvable abrupt
instrument drift or two-site deactivation outside this declared family and require abstention.
This is a synthetic kinetic laboratory, not evidence about a named catalyst.

## Your task

Implement:

```python
def investigate_catalyst(problem, experiment):
    """Return a kinetic/model decision and a fresh-batch operating policy."""
```

`problem` contains the public equations, parameter/condition bounds, four fresh coupon IDs,
their current state versions, the current laboratory state version, a 12-act budget and a
maximum concurrent batch size of three.

Call `experiment(requests)` with a list of one to three request dictionaries. Every new request
must contain a unique string `request_id`, `kind` (`"blank"`, `"standard"` or `"reaction"`) and
the current `lab_state_version`. A reaction additionally contains `coupon_id`, the current
`coupon_state_version`, `temperature_k`, `feed_concentration` and `duration_min`. Reactions on the
same coupon cannot be scheduled concurrently.

The callback returns completed events in physical completion order, which may differ from the
submitted order. Each event carries its immutable event ID, scheduled and execution parent
versions, coupon parent event, instrument sequence, latency, and post-event state. A reaction
permanently changes that coupon and each coupon permits at most three reactions. An exact retry
of an already completed request ID returns the cached observation without another physical act.
Reusing an ID with a different payload, using a stale state parent, exceeding the budget or
reusing an exhausted coupon invalidates the world even if your code catches the exception.

Return a dictionary with:

- `log10_preexponential`, `activation_energy_kj_mol`, `deactivation_rate_per_min`,
  `gain_drift_per_event`, and `offset_drift_per_event`;
- `operating_policy` with one `temperature_k`, `feed_concentration`, and `duration_min` for three
  cycles on a sealed fresh coupon;
- `confidence` in `[0,1]` and boolean `abstain`;
- `evidence_event_ids`, the immutable callback events used for the conclusion;
- `final_lab_state_version` and `final_coupon_state_versions` copied from the final callback
  state.

## Evaluation

- `combined_score` is the development geometric joint of lineage completeness, kinetic and drift
  recovery, sealed fresh-condition prediction, and operating-policy utility, normalized above
  the always-abstain baseline.
- `robustness_score` replays prediction and the committed operating policy on a sealed fresh
  catalyst batch with shifted activity and kinetic/deactivation parameters.
- held-out worlds, unsupported-family refusal, confidence calibration, stale-parent attempts,
  duplicate physical acts, sample use, out-of-order completion and per-event lineage remain
  evaluator-only.

The benchmark measures whether code can reason over a controlled state machine and known kinetic
family. It does not validate a reactor, catalyst, autonomous laboratory or scientific discovery.

## Rules

- Only edit `solution.py`; keep `investigate_catalyst(problem, experiment)`.
- Deterministic CPU code using the Python standard library, NumPy and SciPy only.
- Do not assume hidden-world order, seeds, parameters, drift type or latency.
- No network or process creation. Do not read `verification/` or `frontier_eval/`.

References: Franceschini and Macchietto, DOI `10.1016/j.ces.2007.11.034`; Bartholomew,
DOI `10.1016/S0926-860X(00)00843-7`; Häse, Roch and Aspuru-Guzik,
DOI `10.1016/j.trechm.2019.02.007`; Burger et al., DOI `10.1038/s41586-020-2442-2`;
MacLeod et al., DOI `10.1126/sciadv.aaz8867`.
