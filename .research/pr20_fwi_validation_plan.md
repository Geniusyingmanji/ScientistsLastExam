# FWI substantive revision experiment plan

The baseline is PR head cc000759, evaluator SHA-256
9b786e4c449d4937efaeff1102ecc2d7b6396b0b7a2bb7e8b4c89cd3d63d7fb9.
The shipped score, development and held-out worlds, three-shot budget and 300-second
whole-evaluation timeout remain unchanged during solver development.

Develop numerical methods using development worlds only. Verify the discrete forward
operator against the frozen evaluator, and its adjoint against central differences.
Measure actual velocity RMSE, background-relative weighted error, waveform prediction,
refusals and runtime, not just aggregate score. Never pass truth to a solver.

After selecting the solver on development diagnostics, freeze its source hash before
evaluating the original held-out worlds and these predeclared additional worlds:

- Supported: seeds 71011, 71017, 71023, 71039, 71047, 71051, 71059, 71063,
  71069, 71081, 71089, 71099; variants 0 through 11 in that order.
- Null: (72011, null, 0).
- Background attenuation: (72017, misspecified, 1).
- Structured attenuation: seeds 72023, 72031, 72043; variants 2, 4, 6.

These are additional local validation worlds, not new production worlds or secure
server-held evidence. Their outcomes may expose remaining limitations. Do not tune
against them and then describe them as untouched validation.

Keep a before/after solver and spatial Gaussian-search comparator. Any unavailable
maintainer probe implementation must be described as independently reconstructed,
not an exact reproduction of that implementation.
