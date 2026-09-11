# NeuralReportAttribution — separate intrinsic feedback, report feedback and measured readout

Implement `infer_circuit(problem, experiment)` in `solution.py`. Use calibrated perturbation responses to infer the effective circuit, and refuse when a
four-state model cannot explain the responses. This is a **linearized neural-population
identification task**, not an operational definition of subjective experience and not
a contest between whole GNWT and IIT theories.

The input-state-output treatment is motivated by [Friston, Harrison & Penny (2003)](https://doi.org/10.1016/S1053-8119(03)00202-7).
We deliberately use the much narrower linear local model below, without the fMRI
hemodynamic model or a claim that its populations instantiate consciousness.
Report/sensor controls are inspired by the methodological issue in
[Cogitate (2025)](https://www.nature.com/articles/s41586-025-08888-1), not its data.

## Forward model and hypothesis boundary

In dimensionless model time, x=(V1,V2,P,R), and `dx/dt = A(s)x + B(s)u`, where
s=0 is no report demand and s=1 introduces report feedback. Matrix entries are
row=destination, column=source:

```text
A(s) = [ -1/tau0    local      0          0       ]
       [  a        -1/tau1     feedback   s*report_feedback ]
       [  0         b        -1/tau2     0       ]
       [  0         0         feed      -1/tau3  ]
H(s,omega) = diag(1/(1+i*omega*sensor_tau(s)))
             @ C(s) @ inverse(i*omega*I-A(s)) @ B(s) + D(s)
```

`recurrent` has intrinsic P→V2 feedback; `report_only` has that entry exactly zero
but may still have local V2→V1 recurrence and report-mediated R→V2 feedback.
`none` means **all six off-diagonal coefficients are zero**, not “no consciousness”.
Time constants lie in the public interval, off-diagonal coefficients in [0,1.2],
and the realized circuits are stable. The supported recurrent feedback is at least
`minimum_feedback`; a small fitted coefficient need not justify a positive claim.

C is sensor mixing, B is actuator spread, D is instantaneous sensor feedthrough;
each can differ across report conditions. The low-pass observer adds phase lag.
They are unknown, but noisy independent calibration is available. Calibration is an
idealized **in-silico instrument-identification operation**, not an assertion that a
human experiment can clamp hidden neural states or directly measure experience.
It returns instrument parameters and never A or a mechanism label.

Some worlds contain an omitted dynamical state or otherwise violate the declared
four-state family. Residual structure across frequencies should then prompt
`abstain`, not interpretation of sensor correlation as an intrinsic edge.

## Public problem — every key

| Key | Meaning |
|---|---|
| `population_names` | V1,V2,P,R in matrix order |
| `angular_frequencies` | 5 available positive omega values in inverse model-time units |
| `budget_units` | 14 total experiment units |
| `measurement_noise_sd` | Shared SD 0.012 of each real/imaginary response entry for one unit |
| `calibration_noise_sd` | SD of each instrument-parameter calibration entry for one unit |
| `time_constant_bounds` | allowed neural tau range [0.25,0.8] |
| `edge_bounds` | allowed off-diagonal coefficients [0,1.2] |
| `supported_models` | `recurrent`, `report_only`, `none` |
| `minimum_feedback` | 0.15 for a supported intrinsic-feedback claim |
| `report_conditions` | [0,1] |

All public problem values are identical across worlds and splits. The 14-unit cap
is a resource limit; allocation difficulty is not established by the current ablations.

## Charged experiment

```python
experiment({"kind":"calibration", "report":0, "frequency":0, "units":2})
experiment({"kind":"response", "report":1, "frequency":2, "units":1})
```

All four keys are required and extra keys invalidate the request. `kind` is one
of these two strings; `report` is integer 0/1; `frequency` is an integer index
0–4 (not an angular frequency value). Calibration uses index 0 as a required unused
sentinel. `units` is a positive integer. Booleans do not qualify as integer arguments.
Every operation costs `units`. Any malformed or over-budget operation latches the
campaign invalid even if caught; no unbounded allocation occurs before validation.

Calibration returns `sensor_mixing` (C), `actuator_mixing` (B), `feedthrough` (D),
each a 4×4 real array; `sensor_time_constants`, a length-4 real array; and `units`.
Every entry is an independent Gaussian calibration observation about its true
value, with SD=`calibration_noise_sd/sqrt(units)`. A noisy time-constant observation
may be negative; it is an observation, not a physical negative true time constant.

Response returns `real` and `imag`, each 4×4, plus `units`. They are independent
Gaussian observations of H with SD=`measurement_noise_sd/sqrt(units)` per entry.
Every response includes four independently stimulated input columns. Its price is
one bundle unit per repeat. Treating a whole response as four independent budget
charges is not required; ignoring the real instrument mixing is generally wrong.

Within each operation/condition/frequency, repetition advances an independent unit
counter. A two-unit observation equals the mean of its first two one-unit observations,
not a repeated copy of one noisy matrix. Reordering different experiments has no effect.

## Submission

```python
return {"model":"recurrent", "feedback":0.35, "report_feedback":0.45, "confidence":0.8}
return {"model":"report_only", "feedback":0.0, "report_feedback":0.45, "confidence":0.8}
return {"model":"none", "confidence":0.8}
return {"abstain":True, "confidence":0.8}
```

`model` is required except when `abstain` is true. For the two non-null models,
`feedback` and `report_feedback` are finite numbers in [0,1.2]; `report_only`
requires `feedback` exactly zero. They are ignored for null/refusal. `abstain`
defaults to false and must be boolean; `confidence` defaults to 1 and is finite in
[0,1], describing correctness of the *model decision*, not exact parameter values.

## Scoring

A correct supported model earns
`max(0,1-max(abs(feedback-true_feedback)/0.12, abs(report_feedback-true_report_feedback)/0.15))`.
A correct null decision or justified outside-family refusal earns 1; other answers
and invalid worlds earn zero. Development selection is
`max(0,(mean_utility-0.2)/0.8)`. Blanket null, blanket abstention and the shipped
overconfident baseline each score exactly zero. The ceiling 1 is a perfect model;
the truth-blind reference witness is not the normalization denominator. The 0.2
offset removes blanket abstention (2/10 utility), but correctly separating null
and outside-family worlds alone can earn 0.25 (4/10 utility), with no positive
discoveries. Read discovery coverage alongside the score.

False discovery is an incorrect positive model, distinct from continuous coupling
error. False discovery rate is false claims / positive claims (zero if no claims),
with numerator and denominator published to reviewers. Correct refusal, supported
claim coverage, null correctness, confidence Brier error and heldout recovery are
separate evaluator-only diagnostics, not averaged into an omnibus scientific score.
Search receives only development selection and feasibility, not heldout labels,
per-instance records or these axes. The shipped wrapper enforces this allowlist; public `valid` and `feasibility_rate`
depend only on development. Invalid attempts do not earn refusal credit.

The model defines identifiable **effective** circuit parameters, not sufficient
mechanisms for experience. Source-visible seeds allow prior memorization: formal
contamination resistance requires future server-held instances. Expert difficulty,
long-horizon improvement and independent neural-model validity are not yet certified.

## Reference method and validation status

The revised review-only reference uses calibrated inverse responses to initialize
an exact-derivative joint Gaussian fit of circuit and instrument parameters. It
also fits a fixed midpoint start, removes inactive parameters from each model,
and uses BIC and a fixed 0.1% chi-square residual tail check with the actual
observation and active-parameter counts. Calibration is noisy data, not exact
instrument truth. These are approximate finite-sample model checks, not a
calibrated probability of a scientific discovery.

The oracle, worlds, score and 14-unit/300-second limits are unchanged. The old
reference remains executable as `verification/reference_legacy.py`. Fixed
methods, ability removals and budget diagnostics are declared before Linux
measurement in `references/revision_replay.json`; every result, including an
ablation that does not lose, must be retained. The new reference remains a point
estimator with fixed acquisition; adaptive design and calibrated decision
uncertainty are not established. Independent model calibration remains pending.

## Measured construction checks

Historical Linux measurements of `reference_legacy.py` (before the 2026-09-11
reference revision), with shared noise SD 0.012:

| Strategy | Development | Heldout | Units |
|---|---:|---:|---:|
| joint likelihood reference | 0.859 | 0.743 | 14 |
| one repeat per bundle | 0.829 | 0.704 | 10 |
| two frequencies per condition | 0.828 | 0.627 | 6 |
| ignore instruments | 0 | 0 | 14 |
| never abstain | 0.609 | 0.493 | 14 |
| no model selection | 0.275 | 0.220 | 14 |
| calibrated algebraic grid winner | 0.754 | 0.546 | 8 |
| null-or-refusal only | 0.250 | 0.250 | 3 |

The reference and calibrated algebraic probe have correct discrete decisions on
both splits; their gaps are continuous coupling precision. The reference's development
losses are approximately 0.030, 0.032, 0.859, 0.250 and 0.584 for the five ablations
in table order. Fixed-schedule ablations do not establish adaptive allocation difficulty.
Neither the remaining reference gap nor the weaker raw-response grid proves frontier
model difficulty. The 3024-strategy calibrated grid is selected on development, then
confirmed once on heldout; the null-or-refusal probe makes no supported discoveries.

These finite builder checks used Python 3.12.3, NumPy 1.26.4 and SciPy 1.13.1.
Reference repeats took about 87–88 seconds. Full precision, source/environment binding,
protocols and historical reviewer results are in `references/known_best.md`.
Independent frontier-model calibration has not been performed.

## 关系与区别 / nearest neighbours

- `QuantumControl/ActiveNoiseSpectroscopy` (under Physics) uses supported, confounded
  and outside-family worlds with budgeted probing and refusal. Its supported alternatives
  deliberately match second-order statistics; here the calibrated inverse response
  exposes whether A[1,2] is zero, enabling a substantial algebraic shortcut.
- `StructuralEngineering/ModalDamageAttribution` (under Engineering) supplies the
  discovery-axis and blanket-refusal-offset scoring pattern. Here the observations
  are report-gated neural transfer matrices with sensor/actuator calibration, rather
  than structural vibration and environmental stiffness confounds.
- `CausalDiscovery/InterventionalSCM` uses static acyclic causal models. This task has
  cyclic dynamics, frequency-dependent sensors, report-gated paths and noisy calibration.
- `CausalDiscovery/SurvivorshipConfoundedDesign` concerns selection among survivors,
  not intervention spread, sensor phase or omitted dynamical states.
- `Physics/HiddenCouplingNetwork` recovers a sparse signed graph from nonlinear
  steady-state drives. Here the graph family is specified, measurements are complex
  frequency responses with separately calibrated instruments, and the output is an
  intrinsic/report mechanism decision plus two coupling strengths.
- `SystemsBiology/GeneNetworkIntervention` recovers a nonlinear regulatory network
  and designs a phenotype intervention. Here report demand gates a particular path;
  candidates separate it from intrinsic feedback and observer dynamics, without
  submitting a phenotype intervention.
- `Sensors/IMUBiasCalibration` identifies affine sensor errors; here sensor calibration
  is a nuisance stage before nonlinear dynamic mechanism comparison.

Review-only construction and ablation results are in `references/known_best.md`.
Only edit `solution.py`; NumPy/SciPy and standard-library CPU computation, no network,
process creation, or hidden-file access. `sle.contract_lint` is a free shape utility.

Current revised-reference replay (Linux NumPy 1.26.4 / SciPy 1.13.1): development
0.859353, heldout 0.743349. Removing instrument handling, calibration-uncertainty
fitting, model selection, or refusal lowers development score by approximately
0.859, 0.773, 0.584, or 0.250 respectively. Fixed algebraic probes still achieve
about 87–88% of the reference development score and solve all discrete decisions.
These checks do not establish hard difficulty or independent calibration.
