# AlloyHardnessOptimization — design a study-held alloy batch

## Scientific setting

This task is an offline experimental-design replay built from the Borg et al. compilation of
multi-principal-element-alloy measurements. The data are grouped by full publication DOI: rows
from one paper are never randomly split across training and evaluation. A public degree-two
ridge proxy is fitted to 197 recipes from 44 papers published through 2016, with equal total
weight per paper. Its ridge strength is selected by leave-one-DOI-out error using only those
historical papers. Every eligible 2018–2019 composition-series paper is retained as a later
study world.

In each world you see several room-temperature alloy recipes, their normalized atomic
compositions, coarse processing category, and historical-proxy hardness. You may purchase two
measurements replayed from that world's paper, then submit three alloys and a 90% hardness
prediction interval for each. Because the final batch is larger than the assay budget, at least
one selected alloy must be an unmeasured extrapolation if both assays are spent on distinct
selected candidates.

Composition and a coarse process label do **not** determine hardness. Detailed thermomechanical
history, microstructure, indentation protocol and laboratory effects are incompletely recorded.
Treat the proxy and callback as study-specific evidence, not as a universal materials law.

## Your task

Implement:

```python
def design_alloy_batch(problem, assay):
    """Return:
    {
      "alloy_ids": [three distinct candidate IDs],
      "predictions": {
        candidate_id: {
          "predicted_hardness_hv": finite number in [0, 2000],
          "interval_hv": [lower, upper],
        },
        ... exactly the three selected IDs ...
      },
    }

    assay(candidate_id) returns:
      hardness_hv:      Vickers hardness reported in the current held study;
      budget_cost:      one charged assay unit;
      remaining_budget: units left after the assay.
    """
```

`problem` contains:

- `candidates`: candidate `id`, normalized atomic `composition`, `processing_method`, and
  `proxy_hardness_hv` for every recipe in the current study;
- `batch_size == 3`, `assay_budget == 2`, and `required_prediction_confidence == 0.90`;
- an explicit `scope_warning` about unmeasured process and microstructure variables.

Repeated assays consume budget. Invalid queries and budget overruns fail the world even if
candidate code catches the callback exception. Prediction intervals must be ordered, finite,
inside `[0, 2000]`, and contain their submitted point estimate.

## Evaluation

- `combined_score` is development study-held batch utility normalized so the historical-proxy
  batch scores zero and an exhaustive full-study witness scores one. Utility combines normalized
  reported hardness (90%) and atomic-composition diversity (10%).
- `heldout_policy_score` applies the same policy to five DOI-held studies fixed by a hash split.
- prediction error, 90% interval coverage and interval width are scored separately, including
  the selected-but-unmeasured alloy.
- top-candidate recovery, proxy false promotion, assay efficiency and per-study outcomes remain
  evaluator-only.
- where the compilation contains an exact composition/process match from another DOI, its
  hardness is reserved from the proxy and reported only as sparse independent-confirmation
  evidence. Most candidates have no such match, so confirmation coverage is itself reported.

No single scalar establishes a new alloy. A high in-paper score can fail source-held transfer or
independent confirmation, and wide intervals can attain coverage without useful precision.

## Available tools and resources

Literature on high-entropy alloys, study-grouped validation, active learning, distribution shift,
and uncertainty calibration can inform the policy. The runtime candidate is networkless and
cannot read the frozen evaluator data. NumPy and SciPy are available.

## Rules and scope

- Only edit `solution.py`; keep `design_alloy_batch(problem, assay)`.
- Return exactly three distinct IDs from the supplied candidate list and predictions for exactly
  those IDs.
- Use at most two charged assays per study. Repeats consume budget; caught callback violations
  still fail.
- Candidate code receives a fresh sandbox process and private tmpfs for every study. Do not use
  study identity, split labels or evaluator-only fields.
- Deterministic CPU code only. NumPy/SciPy/standard library; no network or process creation.
- This is a finite public-data retrospective replay, not a prospective alloy discovery. New
  claims require controlled processing, microstructure characterization, replicated indentation,
  independent synthesis and relevant mechanical-property tests.

References: Borg et al., *Scientific Data* 7, 430 (2020), DOI
`10.1038/s41597-020-00768-9`; Figshare dataset v9, DOI
`10.6084/m9.figshare.12642953.v9`.

## Inputs the candidate receives

Every key the task passes to the candidate, taken from the baseline's reads and from the
evaluator's own construction of the input mapping. Names are part of the contract: a candidate
that reaches for one of these quantities under a different name raises at runtime and scores
nothing, and that zero cannot be told apart from a zero earned on the science.

| key | |
|---|---|
| `assay_budget` | passed in, unused by the baseline |
| `batch_size` | read by the baseline |
| `candidates` | read by the baseline |
| `objective` | passed in, unused by the baseline |
| `required_prediction_confidence` | passed in, unused by the baseline |
| `scope_warning` | passed in, unused by the baseline |
