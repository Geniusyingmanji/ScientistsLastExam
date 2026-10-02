# Field-controlled material experiment

This instrument measures one normalized material `response` while a signed
external field is controlled. The material is fixed within an instance; its
response law and internal state are not supplied. The public instrument contract
is `World.describe()`. Operator source, tests, panels, manifests, and
`SCIENTIFIC_NOTES.md` are not agent attachments.

Each experiment uses these four required fields, with no extra keys:

| Field | Meaning and legal range |
|---|---|
| `reset` | `"negative"` or `"positive"`; begin from the same reproducible reference condition, then hold field −1.5 or +1.5 for exactly 300 s. This is a fixed finite history, not an assigned response or a claim of exact equilibrium. |
| `preparation` | Zero to six `{ "field": ..., "duration": ... }` steps, executed after reset and before the observation clock. Each field is applied immediately and held. Field is in [−1.5, 1.5]; duration is in [0.05, 300] s; total duration ≤600 s. |
| `protocol` | One to twenty `{ "time": ..., "field": ... }` knots. First time is 0; times increase by at least 0.05 s, and the final knot occurs by the final observation. Fields are in [−1.5, 1.5]. Apply the first field at t=0, interpolate linearly between knots, then hold the last field. |
| `times` | One to 129 strictly increasing observation times in [0, 3600] s. Times are measured after reset and preparation. |

All numbers must be finite real numbers, not booleans. Equal consecutive knot
fields create a dwell; changes in slope or direction create different ramp and
reversal histories. Field changes never assign a numerical response: the
response remains continuous. The t=0 response depends on the completed reset and
preparation. Reset and preparation are not observed. Every call is independent
of previous calls, and repeating a call repeats its entire reset/history.

Output contains only `axis`, `channels`, and `values`; values have shape
`[len(times), 1]` with channel `response`. Field units and response units are
normalized instrument units, and time is in seconds. The ideal response lies
within [−2.5, 2.5]. Independent additive Gaussian measurement noise has standard
deviation 0.006 response units, without clipping. There is no process noise.
The fixed normalization scale is 1.0 response unit. Each valid experiment costs
one unit.

For example, a triangular field sweep is:

```json
{
  "reset": "negative",
  "preparation": [],
  "protocol": [
    {"time": 0, "field": -1.2},
    {"time": 30, "field": 1.2},
    {"time": 60, "field": -1.2}
  ],
  "times": [0, 5, 10, 20, 30, 40, 50, 60]
}
```

The examples directory also includes a zero-field dwell after positive reset
and a ramp with a reversal and an intervening dwell. Compare preparations,
sweep durations, long dwells and reversal paths. A finite-rate loop alone does
not establish persistent memory; a replicated contrast does not certify a
unique mechanism.

The included baseline is an empirical history-neighbor predictor. It uses only
provided public experiment records: it compares field paths, durations,
preparations and reset polarity, then interpolates a nearby observed trajectory
after rescaling elapsed time. With no records it predicts zero. It contains no
material equations or private parameters, and should be treated as a weak
reference rather than a scientific performance ceiling.
