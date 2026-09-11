# ThermochemicalCycleAudit — decide what a reaction-enthalpy network supports

## Scientific setting

Thermochemical networks (the structure behind Active Thermochemical Tables) close under
Hess's law: any cycle through the reaction graph must sum to zero. A batch of
interconversion enthalpies over eight isomers, each with a stated instrument and
uncertainty, is therefore over-determined, and its closure residuals are evidence.
The audit must decide what that evidence supports — that the batch is consistent, that
one determination is faulty, that one instrument drifted — and must refuse attributions
the network cannot determine.

## Your task

```python
def audit_thermochemical_cycle(problem, replicate, cross_check, budget_units):
    """Return a mapping with exactly:
      verdict: one of "consistent" | "single_fault" | "instrument_drift" | "underdetermined"
      flagged_measurements: list of measurement ids (may be empty)
      drift_instrument: instrument name when verdict is instrument_drift, else ""
      corrected_enthalpies: mapping covering every measurement id with a finite value
      confidence: finite scalar in [0,1]
    """
```

`problem` is a mapping with the keys

```text
species                           eight isomer names
measurements                      list of {id, reaction, stoichiometry, value_kj_per_mol,
                                  sigma_kj_per_mol, instrument} — thirteen determinations
instrument_sigma_kj_per_mol       precision class of each instrument
reference_state_offsets_kj_per_mol  published phase-convention offsets a single
                                  determination may silently carry
replicate_cost / cross_check_cost 1 / 3 budget units
budget_units                      6 total
network_note                      closure statement
```

`replicate(measurement_id)` charges 1 and returns `{id, value_kj_per_mol,
sigma_kj_per_mol, instrument, budget_cost}` — an independent repetition by the same
instrument: the random error shrinks, instrument drift and a determination-specific
systematic offset persist. Repeating an original transcription or reference-state
record instead produces a fresh determination.

`cross_check(measurement_id)` charges 3, is available once per measurement, and returns
the same keys with `instrument: reference_lab` — a higher-precision re-determination by
a different instrument, which reveals systematic errors.

Overspending or malformed calls invalidate the world even when caught.

## Evaluation

- `combined_score` is the development score above both null strategies (always call
  the batch consistent or always return `underdetermined`). The normalization floor
  is the maximum of the passive-auditor mean, the clean-world fraction and the
  potentially unresolved-world fraction. Per world it blends
  closure-correction gain (45%), verdict correctness (35%) and flagged-set diagnosis
  (20%). Both null strategies score exactly zero even if their corrected values improve.
  A refusal on an identifiable world, or an unengaged consistency claim on a faulty
  world, earns no mechanism credit.
- Verdict targets: clean worlds → `consistent`; a drifting instrument →
  `instrument_drift` naming the instrument; a localized faulty determination →
  `single_fault`.
- Some rank-deficient network branches do not identify a unique faulty determination
  without an informative cross-check. The candidate must infer those branches from the
  published stoichiometric design and decide when the available evidence warrants a
  localized claim.
- False discovery includes unsupported attribution in clean or still-unresolved worlds.
  `false_discovery_world_count` is the corresponding denominator;
  `refusing_world_count` counts worlds that remain unidentifiable after the submitted
  query sequence, and `resolved_world_count` counts informative resolutions. A refusal
  rate with no eligible world is reported as `null`.
  Declining to attribute a fault does not itself count as a discovery attempt or a
  false discovery; `development_discovery_coverage` is divided only by worlds in which
  a fault/drift attribution is warranted after the submitted query sequence.
- `robustness_score` repeats the audit on held-out networks, corruptions and noise.

This is a synthetic procedural network, not a claim about real isomer thermochemistry.

## Oracle and difficulty

Species enthalpies are seeded; instrument assignment is balanced across three
precision classes. Difficulty levels 1–3 scale all
uncertainties (1.0 → 1.55) and drift magnitudes; level 1 is the shipped default.

## Rules

- Only edit `solution.py`; keep the complete function signature.
- Deterministic Python/NumPy/SciPy/stdlib code only; no network or process creation.
- Do not read `verification/` or `frontier_eval/`.
- Laboratory errors and overspending invalidate the world even when caught.
- Use `sle.contract_lint` for free local shape checks before returning an inference.

References: Ruscic et al. (2004), J. Phys. Chem. A, doi:`10.1021/jp047912y`;
Bross, Thorpe & Ruscic (2026), J. Phys. Chem. A, doi:`10.1021/acs.jpca.6c03567`. These motivate
thermochemical-network auditing; the benchmark uses the synthetic network stated above.

## 关系与区别 / Relationship to nearby tasks

DiscrepantMeasurements reconciles eight groups measuring one particle-physics constant
with no budget and no closure structure; ProspectiveMetaAnalysis screens literature
evidence. This task audits a Hess-closure network where the constraints themselves
localize faults, spends a replicate/cross-check budget against systematic-versus-random
error, and its refusal world is an information decision on a rank-deficient branch.

## Admission and reference scope

This package remains **candidate**. The runnable reference uses public inputs only.
Reference methods, calibration measurements, shortcut probes and ablation diagnostics
are recorded in the maintainer-facing `references/known_best.md`, which is not served
to candidates. They do not replace clean Linux sandbox replay, independent
thermochemistry review or a frozen frontier-model calibration draw.

## Frontier-Eng overlap comparison (2026-09-06)

无. Nearest catalog entries: snar_multiobjective; mit_case1_mixed; reizman_suzuki_pareto. Replicates and cross-checks diagnose enthalpy-network inconsistency, instrument drift and unidentifiable fault attribution. FE selects reaction conditions for yield or waste; no measurement-consistency verdict is requested.

See `.research/pr9_frontier_eng_overlap_2026-09-06.md` for the pinned 47-task paper and complete available repository catalog. The requested 95-entry source could not be reconciled with the available 78 rows (84 expanded tasks); source reconciliation and maintainer acceptance remain pending.
