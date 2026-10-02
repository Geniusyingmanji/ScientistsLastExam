# Batch scientific environment contract (pilot v0.2)

This contract supplements the persistent microecology CLI. Each environment owns
`env/<name>/world.py`, `world.json`, `README.md`, examples and tests. Shared runner,
scoring, ledger and report code live in Python files directly under `env/`.

## Python interface (trusted operator only)

```python
class World:
    name = "environment_name"
    version = "environment_name-0.2.0"
    axis_field = "times"  # canonical spec list corresponding to run()['axis']
    channels = ("observable_1", "observable_2")
    scales = (1.0, 1.0)  # fixed public normalization scales, not fitted on test data
    noise_std = (0.002, 0.002)

    def __init__(self, seed: int): ...  # fixed hidden mechanism for this instance
    def describe(self) -> dict: ...
    def validate(self, spec: dict) -> dict: ...  # canonical JSON-safe spec, ValueError if invalid
    def cost(self, spec: dict) -> int: ...  # deterministic positive cost, validate first
    def run(self, spec: dict, *, noise_key=None) -> dict: ...
    def panel(self, panel_seed: int, kind: str, count: int = 8) -> list: ...

def baseline(records: list, spec: dict) -> list:
    # Public-data-only baseline, no World instance or hidden parameter access.
    # Return an [n_rows, n_channels] JSON-safe array matching run(spec)['values'].
    ...
```

`run` always starts a fresh experiment with the instance's fixed parameters.
It returns `{"axis": [...], "channels": [...], "values": [[...], ...]}`.
Rows follow the public spec's requested time points or sensor positions; channel
order is fixed. No hidden parameters, topology, seeds or clean target are returned.
`noise_key=None` gives deterministic clean output for the private verifier. Any
non-null string selects reproducible independent measurement noise via a stable
hash of world seed and noise key. Avoid Python's randomized built-in hash.

`describe` provides units, experiment schema with concrete valid examples,
parameter ranges, public channel names, noise and normalization scales. It must
not disclose the sampled mechanism or private implementation. Input errors must
be clear, bounded and public-safe; invalid requests do not change an instance.

`panel` is operator-only. Kinds are `development`, `conditions`, `interventions`.
It returns valid experiment specs, deterministically using `panel_seed`. Conditions
vary legal initial values and observation regimes; interventions vary legal
manipulations. Do not expose test panels through `describe` or public experiments.
Different hidden seeds may change parameters and, where defensible, structures;
neither alone is advertised as proven contamination resistance.

Optional trusted-only `operator_strata` labels and `operator_stratum()` support
explicit balanced sampling at cohort freeze. They must never appear in `describe`,
observations, public errors or candidate context, and are not golden labels for
scoring. Unstratified sampling remains the default; the private manifest records
when a balanced sampling policy was selected.

`baseline` receives records shaped as `{"spec": ..., "observation": ...}` and
may only use that data and publicly documented ranges. An interpolation/nearest
experiment baseline is acceptable initially; avoid any hidden recipe dependency.

## Agent submission

The runner exposes budgeted experiments and isolated Python analysis. The final
frozen submission contains `predictor_code`, `claims` and `explanation`.
The predictor defines `predict(spec)` and returns the values array for that spec.
Its parameters/data must be frozen in its code; it cannot call the world, network,
operator files or future observations. Each prediction query uses an isolated
session. Experiment specs may be revealed after freezing; their outcomes remain
hidden until verification is finished.

Claims are quantitative paired contrasts, up to three:
`{"id": ..., "statement": ..., "control": <spec>, "treatment": <spec>,
"readout": {"row": 0, "channel": "observable_1"},
"interval": [lower, upper], "evidence_ids": ["obs-0001"], "scope": ...}`.
Verification checks fresh independent observations, precision and duplicated
claims. Free-text mechanisms and discovery depth require separately recorded
evidence review; numeric checks never certify a mechanism automatically.

## Engineering requirements

Use Python 3.8-compatible runtime syntax, NumPy/SciPy only for kernels. Validate
finite values, ranges, array shapes and bounded numerical work. Tests must cover
known limiting solutions or an independent solver check, invalid inputs, fixed
instance reproducibility, private/public separation, panel validity and baseline
shape. Keep local tests within the environment's `tests/` directory and use unique
test filenames. Do not import a benchmark's old golden-answer evaluator.
