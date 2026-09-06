# OccupancyDetectionDesign

## Scientific problem

A nondetection does not prove absence. At each site a species has a latent occupancy state, and an
occupied site is observed only with a method- and accessibility-dependent detection probability.
Allocate a finite survey budget across sites, repeat visits, and two survey methods. Infer whether
occupancy increases, decreases, or does not change with the published habitat covariate, estimate
the effect and mean occupancy, or abstain when a linear-logit habitat model is inadequate.

Supported worlds use `logit(psi_i) = alpha + beta * habitat_covariate_i`. Conditional on
occupancy, repeat detections are independent. In model-inadequate worlds, occupancy instead has a
resolvable nonlinear habitat response or spatial structure along the transect. Those histories
require refusal rather than a forced linear effect.

## Candidate interface

Implement `infer_occupancy(problem, survey)`.

### Every key in `problem`

| key | meaning |
|---|---|
| `site_descriptors` | 24 mappings with `site_id`, `habitat_covariate`, `transect_position`, and `accessibility_index` |
| `survey_budget_units` | total cost allowance, 42 |
| `max_visits_per_site` | maximum number of surveys at one site, 3 |
| `survey_methods` | mapping from `rapid` and `intensive` to their integer `cost` (1 and 2) |
| `habitat_effect_bounds` | inclusive bounds for the reported logit-scale effect, `[-4, 4]` |
| `supported_effects` | allowed labels: `positive`, `negative`, `none` |
| `effect_tolerance` | absolute beta error where its continuous score reaches zero |
| `mean_occupancy_tolerance` | absolute occupancy error where its continuous score reaches zero |
| `evidence_requirement` | prose describing the minimum cited evidence |
| `occupancy_model` | prose defining the supported latent-occupancy model |
| `detection_model` | prose defining imperfect detection in the supported family |
| `abstain_when` | prose defining model-inadequacy refusal |

Each entry of `site_descriptors` contains exactly `site_id`, `habitat_covariate`,
`transect_position`, and `accessibility_index`.

### `survey(site_id, method)`

`method` is `rapid` or `intensive`. Calls cost the amount in `survey_methods`; overspending,
unknown sites or methods, and more than `max_visits_per_site` visits fail closed. The callback
returns exactly `query_id`, `site_id`, `method`, `detected`, `visit_number`, `budget_cost`, and
`budget_used`.

## Return value

Return a mapping with `abstain`, a finite `confidence` in `[0, 1]`, and at least four distinct
current-world `evidence_query_ids`. When not abstaining, also return `effect` (`positive`,
`negative`, or `none`), finite `habitat_effect` within the public bounds, and finite
`mean_occupancy` in `[0, 1]`. Malformed output and callback violations score invalid instead of
crashing the evaluator. `sle.contract_lint` is importable and free to call for shape checks.

## Scoring

On supported worlds, the mechanism score combines effect direction (0.45), continuous beta
accuracy (0.35), and mean-occupancy accuracy (0.20). Unsupported worlds score one only for
refusal. `combined_score` is the development mean normalized so blanket abstention is exactly
zero. Effect accuracy, beta score, mean-occupancy score, false discovery, refusal, supported
coverage, attempted discovery, confidence, budget use, and held-out transfer remain separate.
Held-out worlds and per-world truth are not search-visible.

## Relationship to nearby tasks

`PopulationGenetics/DemographicSFS` infers population history from allele-frequency counts and
has no repeated-detection latent state or field-survey design. `ClimateScience/ForcedSignalAttribution`
tests a known spatiotemporal fingerprint against modeled red variability; here the estimand is a
site-occupancy regression marginalized over nondetection, and refusal is triggered by nonlinear
or spatial ecological structure. `SystemsBiology/GeneNetworkIntervention` recovers a directed
mechanistic network from perturbations rather than a habitat association from repeat surveys.

## Rules and references

- Only edit `solution.py`; keep `infer_occupancy(problem, survey)`.
- Use deterministic CPU Python, NumPy, SciPy, and the standard library only.
- Do not read `verification/` or `frontier_eval/`, access the network, or create processes.

The latent-state likelihood follows MacKenzie et al., *Ecology* 83, 2248-2255 (2002), DOI
`10.1890/0012-9658(2002)083[2248:EORWPD]2.0.CO;2`. Repeat presence-absence data as information
about abundance and detection are discussed by Royle and Nichols, *Ecology* 84, 777-790 (2003),
DOI `10.1890/0012-9658(2003)084[0777:EAFRPA]2.0.CO;2`.
