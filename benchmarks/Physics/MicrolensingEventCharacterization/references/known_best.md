# MicrolensingEventCharacterization reference results

## Reference

The truth-blind reference uses all 24 r-band observations. It profiles a bounded source fraction
over a Paczynski grid, uses a robust preliminary fit before jointly profiling a positive Gaussian
anomaly, and independently fits sinusoidal variability. BIC selects among the three supported
families; an excessive best-fit residual triggers refusal of a mixed out-of-family event.

The current deterministic calibration is **0.926256** development `combined_score` and
**0.933409** held-out raw mechanism composite. Model accuracy, supported-world coverage and
ambiguous-world refusal are all 1.0 on both splits. The remaining headroom is continuous duration,
anomaly-amplitude and feature-time recovery, principally in binary-lens events. The reference is a
capable anchor, not a ceiling.

For point and binary lenses, `timescale_days` is the observable full width at half maximum of the
underlying point-lens excess flux. This avoids rewarding guesses of a blending-degenerate latent
Einstein time. For variable sources it remains the period.

## Model draws

All existing DeepSeek measurements predate the current mixed-family worlds and feature-time/FWHM
contract and are historical only. On revision `9a208cf45782592aaf12215b9917d63d4159d122`, one
selection-blind proposal per model was generated with seed 0, temperature 0 and thinking explicitly
disabled. DeepSeek V4 Flash scored 0.287244 development; Pro produced a valid blanket refusal and
scored 0.000000. Earlier ten-proposal runs on another scoring revision reached 0.250000 and
0.260876. None of these values is presented as current calibration.

Fresh model draws are required after the executable design and shortcut margin are frozen.

## Baseline

The legal baseline takes six r-band observations and reports fixed point-lens values. It scores
**0.000000** development and **0.169350** held-out raw mechanism, with `valid=1`. Blanket refusal
also scores exactly **0.000000** development by construction.

## Ablations

Current task-local deterministic capability controls are:

| Candidate | Development combined | Held-out raw composite | Observations |
|---|---:|---:|---:|
| Full bounded reference | 0.926256 | 0.933409 | 24 |
| Reference with eight-epoch cadence | 0.694989 | 0.710742 | 8 |
| Reference with refusal disabled | 0.592923 | 0.683409 | 24 |
| Baseline | 0.000000 | 0.169350 | 6 |
| Blanket refusal | 0.000000 | 0.250000 | 6 |

Sparse cadence loses both model identification and continuous recovery. Disabling refusal preserves
supported-family fits but loses the full unsupported-family axis. The full reference therefore uses
both capabilities materially.

## Shortcut probe

Two executable probes are registered in `TASK_CARD.yaml`:

| Probe | Development combined | Held-out raw composite | Reference ratio |
|---|---:|---:|---:|
| Best of 576 no-fit statistic policies | 0.542283 | 0.590183 | 0.5855 |
| Fixed-source Paczynski/residual/sinusoid fit | 0.417203 | 0.613960 | 0.4504 |

The no-fit family scans round thresholds for mean flux, fraction below baseline and second
difference, plus fixed lens duration and variable period. Its winner is shipped as
`verification/shortcut_constant.py`. The second probe implements the maintainer's C12 attack:
fixed source fraction, a cheap Paczynski SSE grid, maximum positive residual for a binary anomaly,
and sinusoidal least squares. It is shipped as `verification/shortcut_textbook.py`.

The 20% relative-margin ceiling is 0.741005. Both probes remain below it. All four world families
have overlapping r-band flux-range intervals, so the old range classifier no longer separates the
labels. The reported uncertainty is a common instrument floor and cannot identify refusal worlds.

## Construction findings

Earlier revisions were broken by successively stronger review probes. A nine-observation constant
candidate first reached 0.888889 against a 0.560636 reference. After tighter continuous scoring and
constant uncertainty, a 24-observation textbook candidate still reached 0.929167 against a 0.652036
reference, and a development fingerprint lookup reached 0.999236. Those failures showed that
implementation-level hardening alone was insufficient.

The current revision changes the scientific recovery problem rather than merely its normalization:
source fraction and impact parameter span wider ranges; point, binary, variable and mixed events
overlap in flux range; anomaly position, width and amplitude vary; unsupported worlds combine lensing
and variability; non-refusing claims must also locate a defining feature; and invalidity anywhere
forces `combined_score=0`. The reference was rebuilt as a bounded physical fit instead of a free
linear-scale fit.

## Robustness

The evaluator rejects malformed outputs, duplicate observations, overspending, unknown epochs and
fabricated evidence. It resets a sandboxed candidate session before every world, including the split
boundary. Any invalid world forces `valid=0` and `combined_score=0`. The reference and registered
probes are deterministic in local replay; final pinned-Linux sandbox replay and the complete
task-specific contribution gate must be recorded after committing the frozen executable revision.

Reproduce the current task-local calibration with:

```bash
python benchmarks/Physics/MicrolensingEventCharacterization/verification/calibrate.py
```
