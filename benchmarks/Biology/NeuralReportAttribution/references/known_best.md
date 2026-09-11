> 2026-09-11 revision: the tables below are historical measurements of the retained
> `reference_legacy.py`, unless explicitly labelled as the revised reference.
> The new reference and all replay methods are fixed in `revision_replay.json`.
> Current source-bound replay is recorded in the final subsection below; prior tables remain historical.
> Neither this implementation change nor the old eight-run review establishes D16.

# NeuralReportAttribution: witness and construction record

## 1. Reference and sources

`verification/reference_fit.py` independently constructs the public four-population
frequency response and jointly fits neural and instrument nuisance parameters to
response and calibration likelihoods. It compares null, report-only and intrinsic
feedback models, and rejects excessive residuals. It imports no evaluator or truth.
Score 1 is the correct-parameter ceiling, not an empirical reference literal.
In the revised run both splits have zero FDR, full refusal, full supported-world
coverage and full null correctness. The gap to 1 is entirely the precision of the
two continuous couplings in six supported worlds per split, not unsolved model decisions.

[Friston et al., 2003, DOI 10.1016/S1053-8119(03)00202-7](https://doi.org/10.1016/S1053-8119(03)00202-7)
motivates input-state-output identification and effective connectivity. This is a
linearized local system, not full DCM, its hemodynamic model, or a validated theory
of consciousness. [Cogitate 2025](https://www.nature.com/articles/s41586-025-08888-1)
motivates separating theoretical subclaims and report confounds; no Cogitate data
or theory-specific prediction supplies simulated ground-truth labels.
An independent time-domain check integrates exp(A t)exp(-i omega t) and checks the
transfer response including mixing and feedthrough. This tests the numerical equation,
not its adequacy as a model of a human brain.

## 2. Baseline

The shipped candidate reads one report-on response and announces maximum allowed
feedback coefficients. It is legal and scores zero. A blanket null or refusal also
scores exactly zero. Null means no interpopulation coupling in this local model;
it never means no subjective experience. The 0.2 normalization offset subtracts
blanket refusal utility (2/10), not null-plus-refusal utility (4/10). Correctly
separating only these two kinds can score 0.25 with discovery coverage zero.

## 3. Ablation ladder

`scripts/audit_neural_report.py` repeats the secure baseline/reference and runs:

- `one_unit`: one repeat per bundle, 14 to 10 units.
- `six_units`: one calibration and responses at frequency indices 0 and 3 per report
  condition, 6 units total; the same joint likelihood and fixed refusal threshold.
- `ignore_instruments`: assume identity mixing, zero lag and zero feedthrough.
- `never_abstain`: disable both residual and minimum-feedback refusal rules.
- `no_model_selection`: fit only the recurrent family, retaining the refusal rules.

The original variable-noise version was independently measured by the maintainer in
[PR 73's first review](https://github.com/Geniusyingmanji/ScientistsLastExam/pull/73#issuecomment-5615520113),
using Python 3.12.3, NumPy 1.26.4, SciPy 1.11.4:

| Original-version strategy | Development | Heldout | Units |
|---|---:|---:|---:|
| reference | 0.8771937507 | 0.7403460929 | 14 |
| one_unit | 0.840330 | 0.703600 | 10 |
| reviewer 6-unit variant | 0.663560 | 0.739568 | 6 |
| ignore_instruments | 0 | 0 | 14 |
| reviewer never-abstain variant | 0.627194 | 0.490346 | 14 |
| reviewer no-model-selection variant | 0.279930 | 0.222694 | 14 |

The reviewer did not publish the full variant sources or exact two frequencies, so
our new runnable variants make their choices explicit and do not claim source identity.
The 14-to-6 heldout loss was only 0.000778 despite a development loss of about 0.214.
The experiment cap remains a resource constraint; budget allocation is not claimed as
a demonstrated difficulty source. The 10/14 variant also had only a small loss.

Historical builder evidence in `experiments/neural_report_2026-09-10.json` used
Python 3.12.3, NumPy 1.26.4, SciPy 1.13.1: reference 0.8770462287 / 0.7403329403
(see the JSON for authoritative full precision). Small solver-version differences
are expected; these decimals are measurements, not golden test assertions.
Both historical records predate the shared noise SD 0.012 revision.

Revised shared-noise measurements from clean source
`981802039e555698c463591553f54d8e03c2b261` on Linux, Python 3.12.3,
NumPy 1.26.4, SciPy 1.13.1, one OpenBLAS thread:

| Revised strategy | Development | Heldout | Units | Dev loss | Heldout loss |
|---|---:|---:|---:|---:|---:|
| baseline | 0.0000000000 | 0.0000000000 | 1 | +0.859489 | +0.743302 |
| reference | 0.8594885223 | 0.7433017461 | 14 | +0.000000 | +0.000000 |
| one_unit | 0.8291824705 | 0.7038548818 | 10 | +0.030306 | +0.039447 |
| six_units | 0.8276691478 | 0.6266631041 | 6 | +0.031819 | +0.116639 |
| ignore_instruments | 0.0000000000 | 0.0000000000 | 14 | +0.859489 | +0.743302 |
| never_abstain | 0.6094885223 | 0.4933017461 | 14 | +0.250000 | +0.250000 |
| no_model_selection | 0.2752635941 | 0.2204884271 | 14 | +0.584225 | +0.522813 |

Reference repeats took 87.0 and 88.2 seconds and matched every metric, including
the trusted per-instance records before redaction. All candidates above were valid.
The revised 6-unit schedule loses 0.031819 on development and 0.116639 on heldout;
it is explicitly different from the unpublished reviewer variant and does not
reproduce its near-zero heldout loss. No task or grid tuning followed heldout inspection.
These fixed schedules do not establish adaptive allocation difficulty.

Full precision, clean provenance, runtime/candidate hashes and aggregate metrics are
in `experiments/neural_report_revision_2026-09-10.json` at repository root.
The later documentation/evidence commits retain the tested Python sources unchanged.

## 4. Shortcut probes

The original 972-strategy grid inverted a single uncalibrated response and could
return only `recurrent` or `report_only`. Its zero score did not bound calibrated
inversion, null decisions or refusal. The maintainer measured a calibrated algebraic
3024-point grid at development 0.449754 / heldout 0.311061 using 8 units, and a
3-unit null-or-refusal strategy at 0.25 / 0.25 with zero discovery coverage.
These are attributed historical results, not reruns of unpublished reviewer code.

The revised audit keeps the raw grid and adds a fully specified 3024-strategy grid:
`verification/algebraic_probe.py` calibrates twice in each report condition, measures
two frequencies once each (8 units), removes low-pass filtering and C/B/D, and
computes `A = i omega I - inverse(R)`. It thresholds off-diagonal magnitude,
complex/frequency-varying apparent feedback, and intrinsic feedback, then scales
the two coupling estimates. It performs no likelihood optimization or information
criterion selection. All four answer types are available. The grid is fixed in
source; development alone selects thresholds and scales, then the selected source
is evaluated once through the sandbox on development and heldout. Cached development
scoring must match the sandbox result. Reported heldout outcomes never choose a grid point.

`null_or_refuse` uses one calibration and two responses in report condition 1
(3 units); an off-diagonal magnitude threshold separates null from refusal and
never makes a positive claim. Its fixed threshold is not selected on heldout.
Revised Linux results (same source and NumPy/SciPy versions as section 3):

| Probe | Development | Heldout | Units | Supported coverage (dev/heldout) |
|---|---:|---:|---:|---:|
| raw inverse-response grid, 972 strategies | 0 | 0 | 1 | 1 / 1 |
| calibrated algebraic grid, 3024 strategies | 0.7540713032 | 0.5456852969 | 8 | 1 / 1 |
| fixed null-or-refuse | 0.2500000000 | 0.2500000000 | 3 | 0 / 0 |

The selected calibrated configuration is (null threshold 0.13, mismatch threshold
0.35, feedback threshold 0.08, feedback scale 0.9, report scale 1.0). Both splits
have zero FDR and full refusal/null correctness. Calibration plus direct algebra
therefore already solves the discrete decisions; likelihood fitting improves
continuous precision. The revised shortcut is stronger than the historical reviewer
probe and is reported as such, not hidden behind the zero-score raw grid.
These finite probes do not exhaust shortcuts or measure independent model difficulty.

## 5. Frontier draw

No independent language-model draw, saturation study or evolution-gap run has been
performed for this task. Status remains `candidate`, the intended `hard` tier is
uncalibrated, and both lineage and construction status are `incomplete_legacy`.
The task is removed from the recorded-lineage whitelist. Builder tests and the
maintainer's technical review do not substitute for an independent frontier draw.

## 6. Construction errors and corrections

- Joint response/calibration likelihood replaced the initial exact-instrument fit.
- Parameter errors affect continuous recovery, not false discovery of a wrong model.
- Report conditions have distinct instrument calibration; raw response differences
  are not intrinsic-feedback evidence.
- An omitted slow state is distinct from a legal report-only or all-zero null circuit.
- The original unique public noise SD acted as a world identifier and enabled a
  zero-experiment lookup candidate to score 1. Noise is now the same 0.012 everywhere;
  the full public dictionary is identical across worlds and splits.
- Public `valid` previously included heldout failures. It now uses development only,
  as does feasibility. Trusted heldout validity remains available to reviewers.
  A sandbox probe injects heldout-only invalid answers using paid observation
  fingerprints; its temporary answer-membership table is never published.
- The wrapper now filters through `search_visible_metrics` before writing its output.
  Audit reports publish aggregate metrics only. Historical JSON was redacted to remove
  per-instance answer records; this does not erase their existence in Git history.
- Stronger shortcut evidence and the weak budget ablation replace the original
  overstatement. Missing calibration is recorded explicitly, not waived by a whitelist.
- The scoring axes and refusal-offset pattern reuse
  `StructuralEngineering/ModalDamageAttribution`. `QuantumControl/ActiveNoiseSpectroscopy`
  is another close neighbour, but has second-order-matched supported alternatives;
  this task exposes a simpler inverse-response route once instruments are calibrated.

## 7. Robustness, contamination and headroom

Tests check stable realizations, the time-domain equation, counter-seeded batch/query
order equivalence, global RNG independence, malformed answers, sticky overspend,
identical public problems, development-only validation feedback and wrapper output
filtering (including unknown future diagnostics). Candidate process and private tmpfs
reset between every world, including splits; a Linux regression tests globals and a
`/tmp` marker. Invalid answers never gain refusal credit.

Search receives only allowlisted development selection/feasibility metrics through
the shipped wrapper; rich aggregate axes remain trusted audit outputs. The deterministic
source-visible generator and paid response fingerprints still permit precomputed
memorization outside the sandbox. Removing the free public fingerprint does not
establish contamination resistance; server-held new instances are required.

Calibration presumes a controllable simulator, not an exact human neural-state clamp.
The omitted slow state is only one misspecification case. Improved continuous fitting,
uncertainty handling and broader misspecification checks remain possible, but neither
a reference gap nor weak raw-response probes establish frontier difficulty. Independent
neuroscience review and actual model calibration remain admission requirements.


## Revised reference: fixed Linux replay, 2026-09-11

Frozen source `045eb449aa8f19bf4ebc35f6c30f283db8765324`; Python 3.12 / NumPy 1.26.4 / SciPy 1.13.1, numerical libraries limited to one thread. Each of the twelve predeclared methods ran twice through the real Linux candidate sandbox, with all 20 worlds valid and identical complete metrics in each pair. Full records are private; scalar/hash receipts are in `experiments/neural_report_admission_methods_2026-09-11.json`.

| Method | Development | Heldout | Units/world |
|---|---:|---:|---:|
| reference | 0.8593526193 | 0.7433485399 | 14 |
| legacy_reference | 0.8594885223 | 0.7433017461 | 14 |
| algebraic_default | 0.7449182513 | 0.6079550292 | 8 |
| algebraic_grid | 0.7540713032 | 0.5456852969 | 8 |
| null_refusal | 0.2500000000 | 0.2500000000 | 3 |
| ignore_instruments | 0.0000000000 | 0.0000000000 | 14 |
| fixed_calibration | 0.0864724469 | 0.1314585052 | 14 |
| no_model_selection | 0.2752674776 | 0.2204951936 | 14 |
| never_abstain | 0.6093526193 | 0.4933485399 | 14 |
| one_unit | 0.8292816144 | 0.7038765984 | 10 |
| six_units | 0.8275903894 | 0.6266396418 | 6 |
| midpoint_only | 0.8593532059 | 0.7433485399 | 14 |

The new reference is numerically close to the old witness; it does not establish higher scientific difficulty. Approximate observed reference times were 19.7/19.7 seconds versus 89.2/89.3 for the retained old reference. Other validation jobs shared the host, so these are not controlled performance benchmarks.

All four declared scientific ability removals lose development score. The midpoint-only convergence diagnostic differs by less than 1e-6 and has no meaningful loss: algebraic initialization is a robustness measure, not evidence of a necessary scientific skill. The 10- and 6-unit diagnostics still show small development losses; acquisition difficulty remains unestablished.

The published grid winner remains 87.75% of the revised reference on development and does not meet the proposed, predeclared 20% relative separation. This proposed guard is stricter than the template default and remains subject to maintainer scientific review; it was not weakened after replay. The probe is legal and still solves all discrete decisions. Fixed probe replay is not independent model calibration. D16, domain review, fresh server-held instances and long-horizon headroom remain pending.
