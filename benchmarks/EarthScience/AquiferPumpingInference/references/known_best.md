# Known best - AquiferPumpingInference

## Scoring

`combined_score` is clipped to `[0,1]`; a valid blanket `undetermined` answer is exactly zero.
Family accuracy is the fraction of all worlds with a correct confined claim or correct named
refusal and is reported separately with counts. The reference is a task-local evaluation witness,
not a claim of field-site optimality.

## Scientific target

Design a multi-radius pumping test, recover confined-aquifer transmissivity and storativity,
predict sealed drawdown, and distinguish leakage, a recharge boundary, and delayed dual-porosity
storage from the supported Theis family.

## Baseline

The shipped baseline makes one early observation and returns `undetermined` with in-bounds
parameters. It is valid and scores `0.000000` on development and held-out worlds, with zero
attempted-discovery rate.

## Reference

The truth-blind reference spends all 24 units across four radii and six logarithmic times. It fits
the confined and three alternative reduced-order families with deterministic bounded multi-start
least squares and applies an information-criterion margin. On clean Linux secure evaluation it
scores `0.985962` development and `0.983490` held out. Mechanism accuracy, supported coverage, and
correct refusal are all `1.0`; false discovery is zero. Parameter recovery is `0.993042/0.986158`
and sealed prediction is `0.974560/0.966455`. Two complete replays are identical.

## Ablations and shortcuts

| strategy | development | held out | mechanism | correct refusal |
|---|---:|---:|---:|---:|
| full multi-radius reference | 0.985962 | 0.983490 | 1.000/1.000 | 1.000/1.000 |
| one radius, repeated observations | 0.852296 | 0.839991 | 0.875/0.875 | 0.667/0.667 |
| fixed storativity | 0.699741 | 0.722078 | 1.000/1.000 | 1.000/1.000 |
| never refuse | 0.612462 | 0.609990 | 0.625/0.625 | 0.000/0.000 |

A reproducible 192-strategy sweep in `verification/shortcut_probe.py` uses early cross-radius
attenuation, late-time growth, and curvature thresholds but no nonlinear aquifer fit. Its best
development-selected strategy scores `0.361500` on both splits, obtains only `0.375` mechanism
accuracy, and has false-discovery rate `0.625`. Spatial diversity, parameter inference, and model
checking therefore each change measured capability.

## Model calibration

At executable task revision `d70ab470e`, one selection-blind first proposal per model used seed
845, temperature 0.7, `greedy_rewrite`, and explicit `chat_thinking: disabled`. Both exact model
IDs first returned `AQ_SMOKE_OK` in 32-token smoke tests. DeepSeek v4 Flash required a 16000-token
replay after its 8000-token output was truncated into a candidate runtime failure. The completed
Flash proposal is valid and scores `0.124000/0.000000`, with mechanism accuracy `0.125/0.000` and
false discovery `0.875/1.000`.

DeepSeek v4 Pro's first proposal is valid and scores `0.726552/0.726790`. It recovers parameters at
`0.992193/0.993442` and predicts at `0.965315/0.963268`, but identifies only one of three
unsupported mechanisms on each split: correct refusal is `0.333333`, false discovery is `0.25`,
and mechanism accuracy is `0.75`. Thus it demonstrates a strong Theis fit while retaining clear
headroom in conceptual-model diagnosis. The credential-free compact record is
`experiments/aquifer_pumping_deepseek_calibration_2026-09-08.json`; generated code, prompts,
endpoints, credentials, and logs are excluded.

## Limitations and provenance

The oracle is a deterministic radial reduced-order laboratory, not a full groundwater simulator.
It omits partial penetration, pumping-well storage and skin, heterogeneity, anisotropy, nonlinear
unconfined flow, irregular boundaries, correlated instrument drift, and recovery after shutoff.
The confined equation follows Theis (1935), DOI `10.1029/TR016i002p00519`; leakage is motivated by
Hantush and Jacob (1955), DOI `10.1029/TR036i001p00095`; boundary image methods follow Ferris et al.
(1962), DOI `10.3133/wsp1536E`; and dual-porosity behavior is motivated by Moench (1984), DOI
`10.1029/WR020i007p00831`.
