# Scientific task profiles

Task profiles specify the scientific work an agent should attempt within an
environment. They provide public prompts, machine-readable evidence checklists
and the scope of a scientific conclusion. They add no simulator access, scoring
weights, hidden answers, submission fields or model calls.

The catalog version is `scientific-task-profiles-0.1.7`. Stable profile names are
`open_discovery`, `mechanism_discrimination`, `regime_transfer`, `model_revision`
and `boundary_mapping`; each profile
also has its own `<name>-0.1.0` version. `open_discovery` is the default.

All five apply to the four core environments (`microecology`,
`coupled_oscillators`, `reaction_kinetics`, `heat_transport`) and to the expansion
environments (`gene_regulation`, `ising_spin`, `hysteresis_material`) and the
experimental worlds (`microecology_causal`, `orbital_dynamics`, `pattern_formation`, `electrical_impedance`, `spin_echo`, `population_drift`). Applicability is a statement about
the scientific interface; it does not register an environment, select a cohort
or schedule an experiment.

## What the tasks measure

| Profile | Distinct scientific work | Required evidence | Limit of a positive conclusion |
|---|---|---|---|
| `open_discovery` | Select a question and develop an account supported by observations. | Question and scope; observed experiments; a quantitative account; uncertainty and an alternative or confound. | A finding within its tested scope; complete mechanism recovery is not required. |
| `mechanism_discrimination` | Compare at least two plausible causal or dynamical accounts through a targeted test. | Alternatives; their differing predictions recorded before the result; the targeted observation; comparison and revision; identifiability limits. | Discrimination among the stated alternatives under tested conditions, not uniqueness among all mechanisms. |
| `regime_transfer` | Use one relation learned in a source regime to predict a new regime prospectively. | Explicit source/target regimes; a shared quantitative relation; a recorded target prediction; source and target observations; quantitative error and scope. | Transfer across the tested regime change, not a universal law or uniquely identified mechanism. |
| `model_revision` | Diagnose a previously observed prediction failure or limitation, revise the model and test it on new conditions excluded from revision. | Original prediction recorded before its result; actual counterexample/limitation and diagnosis; explicit revision lineage; prospective fresh prediction; new observation; failure and uncertainty accounting. | A revision supported by the fresh check; fitting the old counterexample or replacing old predictions does not establish improvement. |
| `boundary_mapping` | Map where one fixed model meets or fails a justified adequacy criterion across a declared control domain. | Frozen model and informative tolerance; ordered/continuous axis or path and concrete bounds; search/stopping plan; prospective observations; adequate, failed and unresolved regions with resolution. | A scoped transition bracket/region when evidence supports both sides, or a bounded report that no boundary was found; neither one transfer success nor one failure gives a complete boundary. |

`open_discovery` allows the agent to decide what is worth studying. It need not
organize the episode around a formal two-model comparison or a prospective
regime-change test. An informative negative result is a valid outcome.

`mechanism_discrimination` requires alternatives that could initially account for
the evidence. Merely renaming one model or listing two parameter estimates does
not satisfy this requirement. A parameter distinction is meaningful when it
expresses a substantive causal or dynamical difference and yields different
testable predictions. The agent should state a measurable readout and why the
anticipated difference exceeds relevant uncertainty, then record both predictions
before receiving the selected experiment's result. Rejecting both alternatives
or leaving them unresolved is acceptable. The scientific account must explain
what remains identifiable and what does not.

`regime_transfer` requires a source-derived relation and a prospective target
prediction. Its prospective uncertainty or tolerance must be justified and
informative enough to distinguish consequential prediction failure from agreement;
an interval covering every plausible outcome does not demonstrate transfer.
The regime change must be expressed using controls the environment
actually exposes. Initial-state preparation is useful where available; equilibrium
environments can instead vary temperature, fields, boundaries or other legal
controls. Independently fitting each regime is not evidence of transfer. If the
agent refits after a failed prediction, it should preserve the original result
and label the revision. The selected target is an ordinary exploration experiment;
it does not reveal or replace any private evaluation panel.

`model_revision` begins with a model prediction recorded before an actual result,
not a failure reconstructed in hindsight. The result must expose a supported
limitation relative to uncertainty and the original criterion. The diagnosis and
revision should identify what changed and why, preserve the old model and data,
and name all evidence used to revise it. A fresh test uses conditions not used to
construct or fit the revision; predictions and informative tolerances precede
that new observation. Claims of improvement compare unchanged original and
revised models on the same new readouts under a prespecified criterion. The
revision may fail. If no supported original limitation or no fresh test was
obtained, report that evidence gap without manufacturing a failure.

`boundary_mapping` fixes a model/version, source evidence and a scientifically
justified, nonvacuous adequacy criterion before mapping observations. It defines
a continuous or ordered legal control axis, or an explicitly parameterized path,
with concrete bounds and other controls held fixed. Sampling seeks both adequate
and inadequate predictions, with a plan for refining transitions and stopping
within the budget. Adaptive sampling may use prior points, but predictions for
each new point still precede its observation and use the same model and criterion.
Refitting or widening tolerance creates a different map, not a replacement for
the original result. A positive empirical boundary claim requires evidence for
both adequacy and failure supporting a transition bracket or region at a stated
resolution. Report gaps, uncertainty and any monotonicity assumptions; a finite
set of samples does not determine unmeasured intervals or a global threshold.

Both new profiles accept entirely inconclusive or budget-limited evidence.
Boundary search may find no transition within the tested domain. These are valid
scientific conclusions, not reasons to force a positive outcome or extend the
budget. Unperformed required tests remain `not_demonstrated`; an honest limited
conclusion does not automatically complete the evidence checklist. No task
matches mechanism labels against a golden answer or assigns a depth grade.

## Evidence and success semantics

The catalog's `evidence_requirements` are a checklist for a separate scientific
review. Each item has a stable ID, a minimum count and its count unit, permissible
evidence sources, a timing requirement and a substantive description. These
fields make the requirements readable by tooling; they are not an implemented
automated grading rubric. Counts alone cannot establish scientific adequacy.

Evidence sources are existing research notes, experiment records, analysis
records, the final explanation and the frozen predictor. Use observation IDs to
connect assertions to measurements. For a prediction that must precede a
result, the research note accompanying or preceding that experiment request must
contain the prediction before the returned observation is available. A statement
appearing only in the final explanation does not establish prospective timing.

The final submission stays `predictor_code`, `claims`, `explanation`. The profile
does not require extra JSON fields. The explanation should address each checklist
item and refer to earlier evidence. Quantitative claims remain optional and use
the existing paired-contrast format and verifier.

A review should keep three outcomes separate:

1. **Evidence process:** whether all required items are traceable, adequate and
   consistent with the timing requirement. Missing evidence is
   `not_demonstrated`; an unreviewed episode is `requires_evidence_review`.
2. **Scientific conclusion:** whether the observed evidence supports a scoped
   finding, discriminates the stated alternatives, demonstrates scoped transfer,
   falsifies the attempted account or remains inconclusive. A rigorous negative
   or inconclusive investigation may complete the checklist without a positive
   scientific finding.
3. **Numerical evaluation:** the existing prediction and paired-effect results.
   These retain their existing meaning and scoring. High predictive performance
   alone does not establish a mechanism; verified contrasts do not certify
   discovery depth. Profile choice adds no numerical score component.

No profile contains a golden mechanism, expected hidden topology or recipe, a
private test specification, or a rule that names a particular phenomenon as the
required discovery. No model is asked to assert success when the evidence is
insufficient. Review quality, experimental budget, noise, model misspecification
and limitations of the observable interface still constrain the conclusions.

## Small public API

```python
from env.task_profiles import get_task_profile, list_task_profiles

default_task = get_task_profile()
task = get_task_profile("mechanism_discrimination", environment="gene_regulation")
public_prompt = task["public_prompt"]
checklist = task["evidence_requirements"]
catalog = list_task_profiles(environment="ising_spin")
```

The functions return fresh JSON-safe dictionaries. Mutating a returned prompt or
checklist cannot change later calls. Names and optional environment arguments are
validated. The module imports only the standard-library copying helper and has
no file, network, environment, model-client or scoring dependency.

The batch campaign and research runners now freeze the selected profile name,
version and public contents in their manifests and expose them in the public
prompt. Profiles preserve the existing experiment limits, submission format and
numerical scoring. The experimental research runner separately supports immutable
models and prospective comparisons; see [RESEARCH_RUNNER.md](RESEARCH_RUNNER.md).
Comparisons between profiles should identify the different scientific
instructions and keep budgets and other conditions explicit; they should not
pool evidence-review outcomes under a single unqualified discovery rate.

The batch CLI accepts both new names through `--task-profile`; the research CLI
accepts them through `--profile`. For example, these commands freeze manifests
without issuing model requests or running trajectories:

```sh
python -m env freeze --cohort revision-plan --environments pattern_formation \
  --instances 1 --task-profile model_revision --output /private/operator/revision.json
python -m env.research_runner freeze --episode boundary-plan \
  --environment pattern_formation --seed 7 --profile boundary_mapping \
  --output /private/operator/boundary.json
```

Use a new destination and an operator-selected instance; seed 7 above is a
reserved development example, not a formal cohort suggestion. `full_description`
supports all five tasks. The new tasks are **not audited for `apparatus_only`**:
campaign freeze and direct projection reject those combinations. Existing three
task/apparatus combinations retain their exact scientific content and guarded
hashes, with only the catalog revision updated. Neither new task was validated
by a real GPT run in this implementation.

The research runner's scientific task name is distinct from the prospective
request's wire `profile`, which remains only `mechanism_discrimination` or
`regime_transfer`. These wire profiles do not add a boundary/revision score.
Research projections retain the new scientific checklist and explain use
of the existing `experiments`, `analyze`, `preregister` and `finish` actions.
Immutable snapshots pin model versions; preregistration still requires exactly
two substantive rivals and the existing target, readout, tolerance and replication
rules. For revision, `revision_of` keeps its existing preconditions: an earlier
completed test with a refuted rival, unchanged original source, cited
counterexample data and a new target. A suspected limitation does not fabricate
that lineage. For boundary mapping, retain the same primary model and criterion
through meaningful comparison tests, and report the domain-level assessment in
notes and explanation rather than treating one comparison as a boundary grade.

The separate experimental operator executor in [DOMAIN_MAPPING.md](DOMAIN_MAPPING.md)
can instead assess one frozen model on a fully registered finite grid, without
inventing a second rival. It seals all predictions before new observations and
retains adequate, inadequate, inconclusive and incomplete points at the original
family error allocation. Its output does not certify a continuous boundary or
discovery level. It is not wired into the existing research action protocol and
has no GPT results; real isolation and author-reference execution are separate
validation gates following the completed code review.

Research `finish` still requires explanation, known evidence IDs and at least one
completed test ID. An inconclusive completed test can support an honest finish.
If the budget prevents any completed test, preserve notes and the incomplete
report; scientific uncertainty is valid but does not bypass protocol completion.
Batch submission remains `predictor_code`, `claims`, `explanation`, with no new
mandatory fields. No runner budgets or historical scores are changed.

[DISCOVERY_EVIDENCE.md](DISCOVERY_EVIDENCE.md) records six manual evidence
dimensions with precise packet anchors. Successful predictions, meaningful rival
discrimination, transfer and empirical boundary investigations remain separate
judgments. The mechanical validator checks references and recorded order; it
does not assign a discovery level or decide whether a rival is scientifically
adequate.

## Why the existing core-four pilot remains unchanged

Adding this catalog does not retroactively select a profile for a frozen episode,
rewrite a prompt, change cohort membership or modify prediction scoring. The
existing core-four pilot continues under its original frozen protocol and source
snapshot. Its open-ended discovery intent corresponds to the new default, but
that correspondence is not a reason to relabel historical instructions or grade
them against additional requirements that they did not receive.

The source digest covers Python files, so adding this module changes the current
checkout's digest. Continue or replay an already frozen cohort from its frozen
source/runtime; do not replace its stored hash to make the modified checkout
appear equivalent. Selecting a nondefault profile, or exposing this new
catalog in a prompt, belongs in a newly frozen protocol. Expansion environment
applicability likewise does not add those environments to the existing pilot.

Run the model-free catalog tests with:

```sh
python -m pytest env/tests/test_task_profiles.py -q
```
