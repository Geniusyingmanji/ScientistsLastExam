# EnzymeRecoveryDesign

**Candidate, difficulty unmeasured, not frontier eligible.** Determine whether
an enzyme preparation suffers irreversible damage and how many effective
reversible kinetic populations can be resolved. Choose inhibitor loading,
washout, readout and controls under 48 experiment units; freeze a kinetic model
before fresh confirmation. This is an original, explicitly limited effective
model, not identification of unique microscopic binding sites or a wet-lab result.

## Science and measurement

During loading at dose D for L minutes, each subpopulation j reversibly binds
inhibitor, with fraction f_j, association constant kon_j and dissociation constant
koff_j. Washout removes free inhibitor; bound populations recover for t minutes.
Independent irreversible damage during loading has hazard k_loss*D. Activity is:

```text
q_j = f_j * (kon_j*D)/(kon_j*D+koff_j)
          * (1-exp(-(kon_j*D+koff_j)*L)) * exp(-koff_j*t)
A(D,L,t) = exp(-k_loss*D*L) * (1-sum(q_j))
```

There are zero, one or two effective reversible populations. Their fractions sum
to at most 0.9. Damage may coexist with binding. Population exchange during
loading is independent, and the damage hazard applies equally to populations;
these are defining abstractions rather than a claim about every real enzyme.

The optical readout includes gain, offset and a decaying matrix carryover:

```text
carry = c * D/(1+D) * (1-exp(-L/tau)) * exp(-t/tau)
y_optical = gain * (A + fresh_rescue) + offset + carry
y_orthogonal = A + fresh_rescue
```

The orthogonal activity assay avoids this optical artifact but costs more.
Matrix blanks have A=0; standards have A=1. Fresh rescue is enzyme introduced
after loading, contributes known fresh activity, and has not experienced the
loading treatment. Rescue pairs measure optical gain; they alone do not
distinguish every damage/binding/artifact alternative.

Biological recovery and optical carryover can give exactly equal time courses at
one loading condition. Varying loading/dose can distinguish their different
dependencies, so a broad optical-only design is a valid alternative to blanks or
orthogonal assays. No particular diagnostic sequence earns automatic credit.

The public `model.py` supplies equations and the resolution certificate without
private seeds or answers. Relevant background for this abstraction includes
[progress-curve analysis with product inhibition](https://pubmed.ncbi.nlm.nih.gov/3120622/)
and [enzyme-inactivation diagnostics](https://www.sciencedirect.com/science/article/abs/pii/S0301462206002651).
The particular population/carryover generator is original to this task.

## Public problem and assays

All `problem` keys:

| Key | Definition |
|---|---|
| `task_id` | `SystemsBiology/EnzymeRecoveryDesign` |
| `contract_version` | `recovery-candidate-v1` |
| `budget_units` | 48; a fresh assay uses fresh preparation under its specified loading |
| `evaluation_role`, `frontier_eligible` | Candidate construction status, not difficulty certification |
| `units` | Time in minutes; dose relative; activity relative to fresh enzyme |
| `bounds` | Dose `[0.1,4]`, loading `[0.2,8]`, washout `[0,40]`, rescue `[0,0.5]` |
| `generator_ranges` | Positive loss `[0.008,0.07]`; pool fraction `[0.1,0.45]`, kon `[0.12,2.8]`, koff `[0.025,1.4]`; gain `[0.8,1.2]`, offset `[-0.06,0.06]`, carryover `[-0.35,0.35]`, tau `[0.3,20]` |
| `predictor_ranges` | Broader allowed fitted ranges: loss `[0,0.1]`, fraction `[0,0.9]`, kon `[0.04,5]`, koff `[0.005,3]` |
| `tools` | Exact assay keys, readouts, controls, charges and returned fields |
| `noise_sigma` | Independent additive Gaussian, optical0.012 and orthogonal0.015 |
| `claim_schema` | Exact claim keys and allowed structural/partial answers |
| `equivalence` | Resolution tolerance0.01 activity, public comparison grid, order-certification semantics |
| `confirmation` | Twelve independent mixed-condition orthogonal assays after immutable commitment; prediction tolerance0.05 |

Use `experiment("assay", arguments)` with **all six exact keys**:

```json
{"dose":1.0,"loading":2.0,"washout":8.0,"rescue":0.0,
 "control":"specimen","readout":"optical"}
```

Controls are `specimen`, `blank`, `standard`; readouts are `optical`, `orthogonal`.
Nonzero rescue is allowed only on specimens. Optical costs1, orthogonal costs3;
nonzero rescue adds1. Each assay returns `evidence_id`, a copy of `arguments`,
`value`, and `sigma`. Negative noisy readings are retained. Independent
replicates cost full assays. Invalid input or overspend consumes no budget.
There is no diagnostic metadata, mechanism hint or world seed in the response.

## Claim and uncertainty

```json
{"decision":"partial","irreversible_loss":false,"pool_count":null,
 "model":{"k_loss":0.0,"pools":[{"fraction":0.3,"kon":0.7,"koff":0.12}]},
 "evidence_ids":["assay-0001"]}
```

Return exactly these five keys. `decision` is `discover` (both structural fields
resolved), `partial` (exactly one null), or `abstain` (both null, model null).
`irreversible_loss` is boolean or null. `pool_count` is0,1,2 or null, and refers
to the **minimum resolved effective order at the declared resolution**, not
the number of microscopic conformers. Models contain `k_loss` and zero to two
pool objects, each with `fraction`, `kon`, `koff`. Fractions sum to at most0.9.
Exactly identical kinetic pools merge; zero-fraction pools disappear. The
claimed count must match the model after these exact simplifications. A model
containing two identical half-fraction pools therefore claims count1, not2.
Loss claims must match whether fitted `k_loss` is positive. Evidence IDs must
refer to distinct actual observations; an empty list is legal but proves no
experimental support. Citation count receives no scientific reward.

The declared comparison grid uses doses `[0.2,1,4]`, loading `[0.3,2,8]`, and
washout `[0,0.25,0.5,0.75,1,2,3,4,6,8,10,12,16,20,30,40]`. Resolution is a
maximum activity difference of0.01 on this grid. Fresh confirmation uses new
continuous conditions, so fitting only grid values cannot replace a model.

The trusted verifier distinguishes a constructive simplification from a proof
that simplification is impossible:

- A zero/one-pool predictor within tolerance is a **positive witness**. A
  submitted one-pool model can supply a witness missed by the verifier's search.
- A washout range exceeding twice the tolerance excludes every constant
  recovery curve at that loading condition, establishing a nonzero order.
- For four equally spaced times, one exponential plus any constant has
  `Delta0*Delta2-Delta1^2=0`. Two pools are certified only if this determinant
  exceeds `2*epsilon*(abs(Delta0)+abs(Delta2)+2*abs(Delta1))+8*epsilon^2`.
  The bound covers all four activity errors. An irreversible constant and offset
  cancel in differences; optical gain/carryover must first be calibrated or
  bypassed. The verifier applies the certificate to latent normalized activity.
- Failed nonlinear fitting and a nonpositive certificate are inconclusive.
  Such cases permit a partial order answer and receive no resolved-order credit.
  An accurate overparameterized predictor does **not** establish minimum order.

This is a sufficient finite-resolution certification procedure, not a complete
identifiability theorem. Unresolved means the available certification procedures
did not settle order; it must not be called a proven indistinguishable world.

## Frozen confirmation and metrics

After the claim freezes, twelve new dose/loading/washout combinations, sometimes
with rescue, produce independent orthogonal measurements. The claim cannot be
revised. Confirmation is reproducible and independent of exploration history;
the verifier rejects substituted observations or changed claims.

Private metrics remain separate:

- `mechanism_recovery`: correct certified component claims / available certified
  components; unresolved order is excluded from this denominator.
- `certified_component_accuracy`: correct claims / the available certified
  components. Loss always has a defined truth; order may remain uncertified.
- `false_discovery_rate`: false claims / claims with certified truth. Unresolved
  order assertions are separately `unsupported_order_claims`, not mislabeled as
  known false claims.
- `component_coverage`, `discovery_coverage`, `resolved_order_coverage`,
  `order_resolvability_rate`, `order_refusal_rate`, and overall refusal.
- `confirmation_rmse`: frozen activity predictor versus latent mean on new
  conditions; `confirmation_pass_rate` uses absolute error at most0.05.

Every rate publishes numerator/denominator; zero denominators are null.
`prediction_score=exp(-(RMSE/0.05)^2)`. There is deliberately **no combined_score**:
predictive accuracy, structural correctness, supported resolution and candidate
coverage remain separate. All-abstain earns zero predictive/discovery credit.
Unresolved order cannot earn order credit but also does not enter the mechanism
denominator; `certified_component_fraction` reports how much could be verified.
**Missing order certification is not evidence that the task is hard.**

## Controls and admission limits

`verification/reference.py` provides `solve(problem, experiment)` and `POLICIES`:
reference, fixed, random, fixed_optical, fixed_orthogonal, passive, abstain,
no_query, no_query_max, always_max_order_fit. All experimental policies use48
units, including calibration. The strongest comparisons must include both a
48-reading optical grid and a16-reading orthogonal grid. The maximum-order
control always fits/claims two pools and checks whether predictive flexibility
is being mistaken for structure recovery.

Construction found and rejected an earlier scoring rule that gave count credit
to any predictive equivalent two-pool model. A strong fixed optical design also
reached approximately0.993 on12 early worlds under that provisional rule.
Neither result is a calibration of this final minimum-order contract. The
successor remains a candidate; independent frozen-source panels and GPT-6
proposals are still required. No claimed active-design advantage follows merely
from the reference having an adaptive loop.

This extends EnzymeMechanismDiscovery's dynamic protocol with loading history,
competing biological/measurement explanations, unresolved effective order and
explicit strong baselines. The older task remains protocol-only. The current
successor is still a small closed effective family and does not claim open-ended
scientific discovery, cross-simulator confirmation or expert difficulty.
