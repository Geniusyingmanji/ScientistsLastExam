# Scientific task profiles

Task profiles specify the scientific work an agent should attempt within an
environment. They provide public prompts, machine-readable evidence checklists
and the scope of a scientific conclusion. They add no simulator access, scoring
weights, hidden answers, submission fields or model calls.

The catalog version is `scientific-task-profiles-0.1.3`. Stable profile names are
`open_discovery`, `mechanism_discrimination` and `regime_transfer`; each profile
also has its own `<name>-0.1.0` version. `open_discovery` is the default.

All three apply to the four core environments (`microecology`,
`coupled_oscillators`, `reaction_kinetics`, `heat_transport`) and to the expansion
environments (`gene_regulation`, `ising_spin`, `hysteresis_material`) and the
experimental worlds (`microecology_causal`, `orbital_dynamics`, `pattern_formation`). Applicability is a statement about
the scientific interface; it does not register an environment, select a cohort
or schedule an experiment.

## What the tasks measure

| Profile | Distinct scientific work | Required evidence | Limit of a positive conclusion |
|---|---|---|---|
| `open_discovery` | Select a question and develop an account supported by observations. | Question and scope; observed experiments; a quantitative account; uncertainty and an alternative or confound. | A finding within its tested scope; complete mechanism recovery is not required. |
| `mechanism_discrimination` | Compare at least two plausible causal or dynamical accounts through a targeted test. | Alternatives; their differing predictions recorded before the result; the targeted observation; comparison and revision; identifiability limits. | Discrimination among the stated alternatives under tested conditions, not uniqueness among all mechanisms. |
| `regime_transfer` | Use one relation learned in a source regime to predict a new regime prospectively. | Explicit source/target regimes; a shared quantitative relation; a recorded target prediction; source and target observations; quantitative error and scope. | Transfer across the tested regime change, not a universal law or uniquely identified mechanism. |

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
appear equivalent. Selecting either specialized profile, or exposing this new
catalog in a prompt, belongs in a newly frozen protocol. Expansion environment
applicability likewise does not add those environments to the existing pilot.

Run the model-free catalog tests with:

```sh
python -m pytest env/tests/test_task_profiles.py -q
```
