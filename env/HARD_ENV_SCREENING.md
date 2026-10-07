# Next environment screen — 2026-10-05

This is a new development phase, not an extension of either frozen twelve-world cohort. No model requests are authorized or made here. The observed distinction between predictive accuracy and claim quality motivates these experiments; it does not prove that the new candidates will be hard for models.

| Rank | Candidate | Decision and discriminating experiment |
| --- | --- | --- |
| 1 | Adaptive signaling | Implement prototype. Feedforward cancellation and integral feedback can have identical input/output transfer functions. A selective reset of an auxiliary state distinguishes a matched pair; arbitrary stimulus waveforms alone cannot. This adds intervention identifiability beyond fitting a gene-regulation curve. |
| 2 | Retention transport | Implement prototype. Exchange with a retained pool and independent fast/slow passage can agree exactly at fixed flow. Pause and resume flow to test redistribution during the pause. This differs from the existing heat-transport world by its hidden storage and flow history. |
| 3 | Spatial anisotropic transport | Defer. Valuable spatial experimental design, but requires mesh convergence, boundary and instrument calibration beyond this small batch. Revisit ConvectionDiffusionOpt only after reading its forward solver. |
| 4 | Viscoelastic frequency response | Reject from this batch: broad linear-response equivalence to the existing electrical-impedance and climate worlds; a new label alone adds little. |
| 5 | Chaotic ecosystem with inaccessible states | Reject current formulation: no budgeted identifiability witness yet; sensitive numerical error could masquerade as scientific difficulty. |

## Frozen local plan (before development validation)

Implement two synthetic, dimensionless, linear dynamical instruments using matrix exponentials. These are deliberately simplified computational worlds, not validated biological or porous-media models. Each exposes the existing World Python interface, with explicit experiment histories and independent fresh preparation per call. Until shared claim, noise, presentation and sandbox adapters are audited, keep both **unregistered prototypes**.

Use exposed development instance IDs 100, 101 and 202 only, and record them as development/exposed rather than future private evaluation instances. For each world use at most six training experiments, six fresh validation experiments per instance. Local author-informed fitting knows the two formula families and search ranges; the model candidate would not. Limit fitting to two starts per family, 80 solver evaluations per start, and a hard counted 4000 forward predictions per instance. This reference is an optimistic feasibility check, not an agent result or a proof of unique identifiability. Retain failures rather than expanding the budget adaptively.

Check one exact observational-equivalence witness and one allowed intervention that separates it, conservation or equilibrium limits, independent solve_ivp agreement, noise and schema semantics, public-description invariance, panel validity and public-data baseline shape. The no-observation predictor returns zeros. The simple baseline uses nearest experiment records with time interpolation, and may fail on history changes. Compare clean held-out normalized RMSE only as a development diagnostic; do not invent a new discovery-depth score.

A prototype remains unsuitable for formal evaluation until a broader generated-instance calibration, noisy uncertainty analysis, structural holdout, and the shared runner adapters are complete. The released source and all development seeds are exposed. No contamination-resistance claim is made.

## Retained development failure

The first adaptation witness reset at t=5 after a down-step: separation was only 0.01139, below the predeclared 0.05 witness threshold. This was a weak design, not a numerical failure. The state-reset contrast depends on the transient reporter state; an intervention after adaptation can be nearly uninformative. The revised witness resets at t=1 during the initial transient, with the same parameters, stimulus history and threshold. This local design revision is exposed and must not be called prospective evidence.

## Local outcome

Eight focused numerical/contract tests passed. Both exact equivalence witnesses were separated by the permitted interventions. Three exposed development instances per world were fitted with six noisy experiments; all fits stayed below the 4000-forward-prediction cap. Aggregate errors are in `docs/archive/reports/environment-expansion-data.json`. This is author-informed feasibility, not demonstrated model difficulty.

Two deterministic calibration passes were executed. The initial empirical baseline used exact control equality and otherwise fell back to the first record; this was too weak. The second pass uses nearest public control history, with the same fixed queries and noise keys. Both private result files are retained; there is no additional independent experimental sample and no model request. Shared runner/MCP integration and broader calibration remain explicitly pending.
