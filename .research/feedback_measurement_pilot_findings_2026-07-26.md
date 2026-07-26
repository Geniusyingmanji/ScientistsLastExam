# Four-condition feedback measurement pilot findings

Date: 2026-07-26 (UTC).

## Result and evidence boundary

The preregistered measurement pipeline completed all **16/16** scheduled cells with no failed or
recovered attempt. The matrix covers two tasks, four feedback modes, two local replicate
identifiers and three proposals per cell. All prompt hashes and byte counts, parent/release
lineage, manifests, checkpoints, retained proposal sources, schema-v2 trajectories, task-specific
science axes and provider usage records passed the strict analysis. Provider accounting is
complete for all **48/48** proposal calls. This evidence calibrates the measurement pipeline and
permits design of a later Track F study.

It does **not** identify a causal feedback effect. The endpoint exposes no server-side generation
seed, so equal local identifiers do not pair model randomness. Each task-condition cell has only
two identifiers, realized resources differ, the tasks use finite public or simulated worlds, and
there is no prospective independent scientific validation. The pilot therefore estimates neither
a population effect nor model ranking, defines no cross-task science score, and does not
demonstrate autonomous scientific discovery.

The authoritative artifacts are:

- preregistration v3, SHA-256
  `13278d14205209c3e904212597fce800b81e32b7e3eb1eabf26c9d7faf870b02`, frozen against
  source revision `ae6090ffcfb19b3c0ae64f04b0c8bc7d650d549b`;
- prerequisite full suite v18, SHA-256
  `d624bb9a3568849676c0dc2598c7929e1215390db05e4291eac972d45d61c35d`, with **519/519**
  tests passing;
- prerequisite protocol smoke v3, SHA-256
  `d5bc921af2b9eb8010a8187bf2fad5632b61e46115b7b31993b598f34a96c7a6`, with **8/8**
  zero-budget cells passing;
- [raw 16-cell report](../experiments/feedback_measurement_pilot_2026-07-26_v1.json), SHA-256
  `5e543cdfd36bc560b6f79601c1ab92dec6ecd3f2457abdb46a6d878c034cf15f`;
- [strict derived analysis](../experiments/feedback_measurement_pilot_analysis_2026-07-26_v1.json),
  SHA-256 `dbb392acb89fe36da243765f8be92a55ad1039e7c2b9cbc8e0930559e2c4aa5e`.
- post-pilot security audit v41, SHA-256
  `d2082abe9a2f23604a426fc831126b548374d5a9c4ea5a5a00c4c9c60e1dcb8e`, with **18/18**
  adversarial tests passing on clean source `08ec441`.

## Descriptive outcomes

The four modes separate online metric-rich feedback (`normal`), scalar-only feedback
(`score_only`), two-step-delayed artifact release (`delayed_replay`) and frozen-parent
best-of-batch selection (`selection_blind`). Score-only remains an online-selection treatment; it
is not a no-feedback control.

The table reports the best combined score at the complete three-proposal horizon and at the
preregistered common realized total-token horizon. Scores are comparable within a task only.

| Task | Mode | Full horizon, id 0 | Full horizon, id 1 | Common-token horizon, id 0 | Common-token horizon, id 1 |
|---|---|---:|---:|---:|---:|
| Active law | normal | 0.797390 | 0.798314 | 0.796926 | 0.798314 |
| Active law | score only | 0.760925 | 0.798230 | 0.744985 | 0.798230 |
| Active law | delayed replay | 0.998551 | 0.797921 | 0.998551 | 0.796404 |
| Active law | selection blind | 0.796497 | 0.793914 | 0.796497 | 0.793914 |
| Diffraction grating | normal | 0.077897 | 0.198820 | 0.077897 | 0.198820 |
| Diffraction grating | score only | 0.320060 | 7.46e-17 | 7.46e-17 | 7.46e-17 |
| Diffraction grating | delayed replay | 0.090693 | 0.195027 | 0.090693 | 7.46e-17 |
| Diffraction grating | selection blind | 0.244893 | 7.46e-17 | 0.244893 | 7.46e-17 |

The common horizons are 14,395 and 14,472 tokens for ActiveLawDiscovery and 11,491 and 10,663
tokens for DiffractionGratingDesign. Complete-cell totals range from 10,663 to 22,937 tokens, so
equal proposal counts do not imply equal compute. The common-token results also differ from the
complete-horizon results in cells whose useful proposal finishes after the shared cutoff. Any
scaling curve must therefore report both charged proposal/experiment cost and realized token
cost.

All **24/24** ActiveLaw proposals are evaluator-valid. Diffraction has **9/24** valid proposals,
for **33/48** across the matrix. Invalid proposals remain outcomes rather than exclusions. The
ActiveLaw delayed-replay artifact for identifier 0 reaches 0.998551 with zero development and
validation false discoveries, while the corresponding identifier 1 artifact reaches 0.797921
and retains one false discovery in each split. Diffraction condition ordering also reverses
across identifiers. These reversals are compatible with uncontrolled generation variation and
rule out treating the observed ordering as a stable feedback result.

## Claim audit

| Claim | Evidence | Disposition |
|---|---|---|
| The four-condition measurement pipeline ran as preregistered. | 16/16 terminal cells, 0 failed attempts, complete lineage/prompt/provider checks. | Supported for this pilot. |
| One feedback mode improves scientific optimization. | Two unpaired local identifiers per condition; condition directions reverse; resources differ. | Not identified. |
| GPT-5.5 has a population-level capability ranking on these modes. | No server-side seed and no independent repeated cohort. | Not estimated. |
| A single cross-task discovery score can be reported. | The two evaluators expose different science axes. | Rejected; keep axes task-specific. |
| The run demonstrates autonomous scientific discovery. | Finite public/simulated worlds and no prospective or independent scientific validation. | Not supported. |

## Consequences for Track F

The pilot supports the following design requirements, not outcome claims:

1. Freeze a new preregistration after any change under `frontier_science/`, `scripts/`, `tests/`,
   `benchmarks/` or `requirements-upstream.txt`; v3 cannot be reused after such a change.
2. Use at least ten independent runs per condition. If provider-side seeds remain unavailable,
   randomize the unpaired execution order and state that limitation rather than calling local
   identifiers paired seeds.
3. Plan precision and multiplicity before the confirmatory cohort. Keep task-specific mechanism,
   prediction, refusal, false-discovery, transfer and robustness outcomes separate.
4. Retain intent-to-evaluate denominators, invalid proposals, retries and all prompt/lineage
   records. Report both the configured proposal horizon and common realized resource horizons.
5. Use fresh or server-held worlds, then require independent domain-scientist review and
   prospective or orthogonal replication before any scientific-discovery claim.
