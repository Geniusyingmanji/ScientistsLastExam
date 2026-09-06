# Known witnesses and limits

## Reproducing

Run `python -m unittest tests.test_process_microstructure_property_design`. All probes use the
deterministic CPU evaluator; no model, network service or stochastic optimizer is required.

## Reference

`verification/reference_process_archive.py` independently generates a 1024-point Latin hypercube,
scores it with the declared public low-fidelity mixture/crystallization proxy, greedily selects 20
proxy-hypervolume increments, and performs two deterministic 11-point-per-axis coordinate-exchange
passes. It imports neither the panel nor the scored oracle and runs as an ordinary isolated
candidate. It scores `1.0`: development raw/shifted hypervolumes are
`0.05589055199212832` and `0.05004532824833629`; held-out raw/shifted values are
`0.06125903702179302` and `0.055433072836922594`.

## Baseline

The shipped shortest, hottest, fastest-cooled, undrawn four-row archive is legal and scores `0.0`.
Its development raw/shifted hypervolumes are `0.03655170742063612` and
`0.032344076195489124`.

## Difficulty ladder

The deterministic ladder is baseline `0.0`, greedy 441-point blend-temperature shortcut
`0.24854152762865947`, the three greedy 343-point subspace probes at `0.6919779457497287`,
`0.2987325943208072`, and `0.4519928224629508`, independent reference `1.0`, and evaluator-aware
coordinate exchange at `1.0050830170752605`. A 2048-point public-only pool followed by the same
refinement scores `1.00037415439912`. This establishes measured shortcut separation, reference-
platform stability and uncapped headroom, not HY3 or long-horizon difficulty.

## Shortcut probe

The 441-point shortcut varies only blend fraction and anneal temperature while pinning shortest
time, fastest cooling and no draw; its raw development hypervolume is
`0.041358213393008`. Three 343-point grids vary blend plus two other coordinates while holding the
remaining pair at the original review constants: blend-time-draw, blend-cooling-draw, and
blend-temperature-draw now score `0.6919779457497287`, `0.2987325943208072`, and
`0.4519928224629508`. Before hardening those same grids scored `1.20449`, `1.00999`, and
`1.01105`. All four probes are below the independent reference, but they do not exhaust other
analytic shortcuts.

## Construction history

Review found a high-B corner, strong two- and three-coordinate shortcuts, instantaneous-style
crystallinity, an overly loose energy scale, and a fixed-bin reference whose bins had been selected
with the private oracle. The repair keeps mobility-limited crystallization and the explicit `0.35`
draw modulus gain versus `0.20` permeability penalty, increases reduced kinetic selectivity to
`Ec=7, k=700`, increases cooling sensitivity to `0.30`, and aligns the energy scale to the reachable
`7.5` envelope. The reference now performs its own candidate-equivalent public proxy search over
1024 points plus two coordinate-exchange passes. Increasing the otherwise identical public pool to
2048 changes the normalized score by only `0.00037415439912`. A separate evaluator-aware
coordinate-exchange red team finds raw development hypervolume `0.055988851669301024`, so score
remains uncapped.

## Robustness and model draw pending

Reference-archive ablations score `0.5240992860282923` without draw, `0.7647896745827635` at
shortest time, `0.7708825121464876` at fastest cooling, and `0.6727115591109907` at one low
temperature.
Held-out worlds, three sealed shifts, malformed artifacts and runner isolation are tested. HY3
draws, real polymers, higher-dimensional morphology, manufacturing validation and experiments
remain pending.
