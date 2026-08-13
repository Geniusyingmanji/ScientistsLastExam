# ElectrolyteConductivityDesign — allocate EIS assays and select a robust formulation batch

## Scientific setting

This task is an offline replay of a CC BY 4.0 high-throughput battery-electrolyte
dataset. The source contains 5,035 temperature rows from 504 independent experiment
IDs over EC/PC/EMC/LiPF6 formulations. Each experiment measures a complete
electrochemical-impedance series from −30 °C to 60 °C. Repeated formulations were
prepared and measured independently up to eight times.

You receive a degree-three ridge-regression proxy fitted only to 358 earlier complete
experiments across 85 formulations. The 23 candidate formulations come from two later
January 2022 campaigns and do not overlap the proxy-training compositions. The proxy is
scientifically useful, but the published one-shot study reports that high-temperature
optima moved substantially after new experiments.

## Your task

Implement:

```python
def design_electrolyte_batch(problem, assay):
    """Return {"formulation_ids": [three distinct candidate IDs]}."""
```

`problem` contains:

- `temperatures_c`: ten temperatures from −30 to 60 °C;
- `application_weights`: a non-negative normalized temperature-duty profile;
- `candidate_formulations`: 23 IDs with EC/PC/EMC/LiPF6 masses, two public ratios,
  and the historical-model proxy conductivity curve;
- `batch_size == 3` and `assay_budget == 8`.

`assay(formulation_id)` spends one unit and returns two independent experimental
temperature scans: their individual, mean, minimum and maximum conductivities, EIS-fit
quality, and relative cell-constant uncertainty. Repeated calls consume budget. Invalid
queries and overruns fail the world even if candidate code catches the exception.

Submit three distinct IDs from the candidate list. A submitted formulation need not have
been assayed, so a policy may learn a correction to the historical proxy and generalize.

## Evaluation

- `combined_score` is visible optimization utility normalized so the public-proxy batch
  scores zero and a full discovery-assay landscape witness scores one. Utility is 90%
  weighted log-conductivity quality and 10% formulation-space diversity.
- `robustness_score` uses the worse of the two discovery repeats at every temperature.
- `confirmation_score` and `confirmation_robustness_score` use two independent repeats
  that are never returned by `assay`; they are not used for search or normalization of
  the visible optimization score.
- `heldout_policy_score` and `heldout_robustness_score` evaluate three undisclosed
  temperature-duty profiles.
- Top-quartile hit rate, proxy false promotion, EIS fit quality, Arrhenius consistency,
  campaign coverage and assay efficiency remain evaluator-only diagnostics.

The nominal, repeat-robust and untouched-confirmation references are deliberately
different. One scalar cannot establish a universally optimal electrolyte, and the
underlying paper itself found that there is no single formulation optimal over the
entire temperature range.

## Available tools and resources

NumPy and SciPy are available. Literature on electrolyte transport, response-surface
modeling, active learning, robust batch design and experimental uncertainty can inform
the policy. Candidate execution is networkless and cannot read the frozen measurements.

## Rules and scope

- Only edit `solution.py`; keep `design_electrolyte_batch(problem, assay)`.
- Return exactly three distinct candidate formulation IDs.
- Use at most eight charged assays per application world.
- Deterministic CPU code only; no network or process creation.
- Do not read `verification/` or `frontier_eval/`.

This is a finite public-data replay. It optimizes ionic conductivity within one
EC/PC/EMC/LiPF6 system; it does not establish electrochemical stability, safety,
electrode compatibility, cycle life or complete-cell performance. It is neither a
prospective experiment nor autonomous battery discovery, and public data remain subject
to lookup and pretraining contamination.

References: Rahmanian et al., *Scientific Data* 10, 43 (2023), DOI
`10.1038/s41597-023-01936-3`; dataset DOI `10.5281/zenodo.7244939`;
Rahmanian et al., *Batteries & Supercaps* 5, e202200228 (2022), DOI
`10.1002/batt.202200228`; Flores et al., *Digital Discovery* 1, 440–447
(2022), DOI `10.1039/D2DD00027J`.

## Inputs the candidate receives

Every key the task passes to the candidate, taken from the baseline's reads and from the
evaluator's own construction of the input mapping. Names are part of the contract: a candidate
that reaches for one of these quantities under a different name raises at runtime and scores
nothing, and that zero cannot be told apart from a zero earned on the science.

| key | |
|---|---|
| `application_weights` | read by the baseline |
| `assay_budget` | passed in, unused by the baseline |
| `batch_size` | read by the baseline |
| `candidate_formulations` | read by the baseline |
| `objective` | passed in, unused by the baseline |
| `temperatures_c` | passed in, unused by the baseline |
