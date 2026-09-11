# PR #72 candidate admission review

Task: `ParticlePhysics/DarkMatterRecoilAttribution`. Original PR head
`8497bd455d3090087e6a15e99fb85f5fae75e5cd`; integration base
`3069479717c2d0db0b040babb42390bdcbb60cb1`. Merge `561d9b1` preserves the
submitted head as an ancestor. The frozen task/check source is
`9516d4b0fc9ddcb6d2853ee7a39448fc851e549b`.

This review follows current `CONTRIBUTING.md` A–F and
`docs/task_admission_workflows.md`. It does not certify the task, establish
independent domain review, or substitute model-free checks for a frontier draw.
The registry remains `candidate`, external domain review is pending, and both
instance splits were used during construction. They are not fresh confirmation.

## A: scientific question and non-isomorphic scope

A1 disposition from this integration's maintainer coordination: taxonomy cells can
contain distinct questions; each task must map to one cell, but a cell need not
contain only one task. This is **a new scientific question in an existing cell**,
not a claim to have filled an empty Physics/discovery cell. Classification remains
`discovery/evidence`, with the `shared_halo_multi_target_recoil_law_not_resonance_scan`
note. No reclassification was made to pass a gate.

The local comparison below reads the actual `Task.md` contracts at base `3069479`,
not only catalog names. PR #72 has no free observed signal spectrum: the candidate
buys exposures from three nuclear targets, receives science/background/calibration
counts, and returns a common recoil law plus mass, `none`, or model-family refusal.

| Neighbour | Observations and artifact in the existing task | Substantive distinction in #72 |
|---|---|---|
| `Gravitation/PTAHellingsDowns` | Public angular correlations; optional paid parametric replicate tables; report an angular kernel or refuse | Paid target spectra and gain/background controls determine a shared nonlinear law **and continuous mass**. Unsupported target marginals each have an exactly supported twin; inconsistency appears jointly across targets. |
| `ParticlePhysics/LookElsewhereAnomaly` | Public mass histogram; paid background-prior toys; decide a global-significance resonance claim and peak location | No trials-factor scan or prior-only toys. Counts come from the hidden signal-bearing world; the law's target-dependent recoil kinematics and mass/halo degeneracy determine recovery. |
| `ParticlePhysics/DiscrepantMeasurements` | Eight published estimates and up to five group split tests; report evidence diagnosis, corrected value/uncertainty and culprit or refuse | Does not diagnose groups' error bars or data halves. It profiles one common recoil law/mass against three physical responses and separately measured detector nuisances. |
| `Exoplanets/TransmissionSpectrumSpecies` | Allocate transits over wavelength bands; infer a species set or refuse because of template degeneracy/cloud/noise | Single-target marginal compatibility is deliberately insufficient here; refusal concerns cross-target shared-mass model failure, with law-gated continuous parameter recovery. |

A2 therefore passes the non-isomorphism check at the contract level. This is a
bounded simulator for known inference methods; it is not a newly discovered
physical theory or a claim to solve cosmological dark matter.

A3 re-read the [paper Appendix A, 47 tasks](https://arxiv.org/html/2604.12290v1#A1)
and all rows of the [pinned repository catalog](https://github.com/Einsia/Frontier-Engineering/blob/e3fa29c193356af2ce1ec8b3d23ab1a2e2410071/TASK_DETAILS.md).
The fetched catalog SHA-256 is
`11be782992273d8131b077c6d7f30e78c0389e8db1d2af6494388621b043bbf5`:
78 task rows, or 84 identifiers after expanding the seven-task EngDesign row.
It does not contain 95 rows; the checklist's historical count is not represented
as a verified count. The full catalog screening found no matching recoil inference
question. The closest observation-design and particle-physics entries were also
checked against their actual source contracts:

- [MuonTomography](https://github.com/Einsia/Frontier-Engineering/blob/e3fa29c193356af2ce1ec8b3d23ab1a2e2410071/benchmarks/ParticlePhysics/MuonTomography/Task.md)
  outputs up to 15 detector positions/orientations for a known region of interest,
  maximizing modeled received signal minus installation/excavation cost. It does
  not infer competing recoil laws, mass or an outside-family world.
- [ProtonTherapyPlanning](https://github.com/Einsia/Frontier-Engineering/blob/e3fa29c193356af2ce1ec8b3d23ab1a2e2410071/benchmarks/ParticlePhysics/ProtonTherapyPlanning/Task.md)
  outputs beam spots and weights under a stated dose kernel; dose coverage,
  organ exposure and beam cost determine the objective. The unknown mechanism
  and scientific refusal decisions of #72 are absent.
- [CarAerodynamicsSensing](https://github.com/Einsia/Frontier-Engineering/blob/e3fa29c193356af2ce1ec8b3d23ab1a2e2410071/benchmarks/Aerodynamics/CarAerodynamicsSensing/Task.md)
  outputs 30 surface indices; a frozen reconstruction model scores pressure error.
  This is sensor placement, rather than a program that purchases noisy spectra
  and reports law/mass/null/refusal. The paper's reaction entries similarly optimize
  yield or Pareto hypervolume rather than make this inference.

A4: [Cherry, Frandsen and Shoemaker, equations 1–3 and 5–7](https://arxiv.org/html/1405.1420v4)
support coherent elastic target dependence, the inverse-speed factor, recoil
kinematics and momentum-dependent rate factors. The oracle's 34–50 lines use
those structures. Its three unboosted Maxwell components, Gaussian form factor,
midpoint bins and benchmark rate units are expressly approximations. Isotopes,
lab boost, escape truncation and detector smearing are omitted. The independent
speed-integral unit test checks the stated kernel, not experimental validity.
The paper does not validate the synthetic world mixture or normalized score.
The published paper's DOI is [10.1088/1475-7516/2014/10/022](https://doi.org/10.1088/1475-7516/2014/10/022);
the existing registration uses its arXiv identifier `arxiv:1405.1420`.

## B and F: repairs and executable acceptance

- Replaced the PR's old wrapper with the standard-library launcher for
  `sle/frontier_eval_entrypoint.py`, explicit logical ID, 300-second timeout,
  public metric filtering and trusted private sidecars. The task card declares
  the same timeout and 12 experiment units per world.
- Added explicit correct-refusal, supported-claim, null-correct, valid-world and
  exposure-unit counts. All rates can now be recomputed from scalar numerators
  and denominators. The original score, class mixture, world seeds and reference
  algorithm are unchanged. Correct law with inaccurate mass still loses continuous
  recovery credit without being mislabeled as a false law discovery.
- Task tests cover 14 malformed answer classes, caught budget overspend, public
  budget mutation, split/order-equivalent charged samples, zero blanket `none` and
  `abstain`, global RNG independence, independent physical kernels and actual
  process/tmpfs isolation at every world boundary. Four new count regressions
  independently recompute published diagnostics from per-world records.
- Local non-sandbox checks: 36 passed; the real task wrapper's non-300 timeout
  forwarding and metric-filtering regression also passed. Linux at `e1503ca6`:
  **39 passed in 36.62 seconds**, including all task tests. The sole subsequent
  source change was reviewer-driver `Path(__file__).resolve()` compatibility.
  The initial contribution recorder failed before any sandbox evaluation; its
  log and empty private directory are retained as a zero-call preflight failure.
- The standard contribution gate runs unchanged through a recorder at `9516d4b0`:
  two baseline runs, two degenerate candidates, three malformed candidates, and
  two runs each of reference and the two declared probes (13 calls). Full metrics
  stay in an external 0700 directory; only aggregate scalars and hashes are public.
  In the secure wrapper, a raised candidate is valid=0 with the runtime invalid
  sentinel, while malformed return values receive score 0; this is distinct from
  an infrastructure failure and is accepted by the current contribution contract.

## C: fixed shortcuts, reference completeness and ablations

The machine contract uses the original reference plus two exactly pinned candidate
files. Their hashes and the source-bound historical eight-run replay are in
`references/shortcut_replay_provenance.json`. The fixed 57.8 mass derivative retains
all reference measurements and model decisions, so it is an ability-removal probe,
not a claim of reduced computation. The four-way candidate uses the author's
previously development-selected configuration; it imports no author/oracle driver.
The contract preserves the existing 30% relative separation requirement rather
than adopting a weaker generic default. Historical measurements are not relabeled
as current whole-package evidence after the added diagnostic keys.

C12 has two distinct checks: the six fixed reference/probe gate replays, and the
pre-existing 233280-configuration builder grid plus exact continuous constant-mass
bound in the task tests. The latter were recomputed by the 39-test run; no grid
dimension was expanded, and no current result was used to change candidate
parameters. The fixed machine guard by itself cannot establish grid optimality
or exclude arbitrary learned/multi-target shortcuts.

The truth-blind reference profiles joint Poisson deviance for science, background
and calibration data, optimizes mass/coupling/speed weights and detector nuisances,
and compares laws with null and residual refusal checks. Its limitations are equal
allocation, a small deterministic multi-start fit and point estimates; adaptive
allocation and better uncertainty treatment remain possible. No forced optimizer
failure, hidden-answer access or artificial normalization ceiling was added.

The three **previously declared** ability ablations (`one_unit`, `ignore_gain`,
`fixed_halo`) are replayed twice each in an independent six-call plan at the same
clean `9516d4b0` source. Only the reference's `ablation=None` default is replaced
with the named value; source hashes and the one-expression derivation are recorded.
Comparison with reference uses the separately planned contribution run in the same
source/environment, not a reference rerun or parameter search. The historical
fixed-halo heldout improvement remains disclosed; instances are not customized
to force every ablation to lose on both splits.

## D and E: remaining integration decisions

**D16 fails; hold PR #72.** The root completed the clean-source, selection-blind
budget-1 plan at `9516d4b0` with fixed seed labels 0/1/2. Model `gpt-5.6-sol`,
reasoning high, max output 16384, evaluator timeout 300 seconds. First proposal
0 was valid in all 56 worlds and scored 0.5855425654/0.5953141420, exceeding the
predeclared reference on both splits. Proposal 1 timed out after 49 valid worlds;
proposal 2 was fully valid at 0.2802699453/0.3347217998. No oracle, prompt, instance,
reference, scoring threshold or budget changed in response. All three scheduled
draws remain recorded; an invalid draw or its zero incumbent is not difficulty.

Plan SHA-256 `ee8ef9532fd223a8a2ab653a0619985537935ef94d4ddcb1cb524673bc6a90ec`;
model condition `967fb197a1603c8c9bd881997ba02cfde1336f0cbb2e1c3a369c3cec24d50d07`.
The public review in `experiments/dark_matter_recoil_first_draw_review_2026-09-11.json`
independently verifies all six requests/receipts, complete metrics, retained
candidate source, expected-world validity, original source bindings and 44 private
artifact hashes/permissions. It records 44696 provider-reported tokens; pricing
was unavailable. The campaign returns incomplete because one replicate has no
valid proposal; the raw-event review separately establishes the decisive D16
failure. An initial read-only reviewer invocation failed on the CLI's extra replay
metadata, before producing any review result; the comparison was corrected and
no model/evaluator call was repeated. Original source and run files were unchanged.

The card now records these outcomes as source-bound historical calibration after
the documentation-only package update, with `frozen_before_eval: false`. Full
metrics, candidate artifacts and the immutable plan remain under the private
operator root `sle-operator-evidence/2026-09-11/task-admission/pr72` on g450. The
reviewer is `.research/summarize_first_draws_2026-09-11.py` on the root integration
branch; it makes no oracle or model calls. This task is not admitted/certified.

Registration, Chinese inventory source entries, seven-section reference notes and
task invariants are present. The integration deliberately retains main's global
README/TASKS/evidence snapshots; their joint regeneration and whole-suite acceptance
belong to the root integration. Historical task-specific scientific JSON remains
explicitly historical; obsolete PR-wide check directories were removed. Pending
domain review, server-held confirmation and long-horizon headroom remain visible.

## Completed current-source measurements

The contribution recorder completed **13/13** evaluations, exit 0:
`structural=passed`, `runtime=passed`, `shortcut_guard=passed`,
`difficulty=unassessed`, `scientific_admission=not_assessed`. All three declared
candidate pairs have identical complete metrics and match the task-card numbers
within the declared 1e-6 tolerance. The separate ablation recorder completed
**6/6**, exit 0, with all worlds valid and complete metrics identical within pairs.
Both recorders verified their frozen task/runtime sources were unchanged. These
19 calls are the two reviewer-driver plans; the 39-test run separately includes
one sandbox isolation regression and trusted-oracle unit/construction checks.

| Candidate | Development | Heldout | Development loss vs reference |
|---|---:|---:|---:|
| baseline | 0 | 0 | 0.5486397428 |
| reference | 0.5486397428 | 0.5000127063 | 0 |
| fixed mass 57.8 | 0.2903389817 | 0.2439422043 | 0.2583007611 |
| published four-way probe | 0.2495350510 | 0.1306702190 | 0.2991046918 |
| one-unit ablation | 0.3660627180 | 0.2355724270 | 0.1825770248 |
| ignored-gain ablation | 0.3413388479 | 0.2234434075 | 0.2073008949 |
| fixed-halo ablation | 0.4382206292 | 0.5400792904 | 0.1104191136 |

Reference/ablations are compared across the two independent plans with identical
source and numerical environment. C13 shows a loss for each ablation on the
development selection axis. The fixed-halo restriction improves heldout by
**0.0400665841** and changes its false claims from 1/21 to 0/20 and correct refusal
from 3/4 to 4/4. This confirms the earlier limitation: free halo fitting is not
uniformly necessary on these finite worlds. It is not a reason to choose new worlds
or hide the heldout result. At 300 seconds per evaluation, both current reference
runs took about 43 seconds; the largest ablation was about 50 seconds on this host.

Each split has 28 worlds: 20 supported, 4 null, 4 outside-family. The public JSON
retains all scalar numerators and denominators. In particular:

| Candidate | False claims / positive claims (dev; heldout) | Correct refusals / outside-family (dev; heldout) | Supported claims / supported worlds (dev; heldout) |
|---|---|---|---|
| reference | 0/20; 1/21 | 4/4; 3/4 | 20/20; 20/20 |
| fixed mass 57.8 | 0/20; 1/21 | 4/4; 3/4 | 20/20; 20/20 |
| published four-way | 1/10; 2/8 | 3/4; 2/4 | 9/20; 6/20 |
| one unit | 2/18; 1/15 | 2/4; 3/4 | 16/20; 14/20 |
| ignored gain | 0/12; 0/5 | 4/4; 4/4 | 12/20; 5/20 |
| fixed halo | 0/20; 0/20 | 4/4; 4/4 | 20/20; 20/20 |

An independent read-only check verified all 19 original files' bytes/canonical/
per-instance hashes, public scalar projection, filesystem permissions and 36
split-level score/count/rate recomputations. The deliberate raising candidate
correctly has `valid=0` and no per-instance payload; it is the remaining
one of 19, rather than a missing successful-world record. See
`pr72_admission_validation_2026-09-11.json`.

Public artifacts in this directory:

- `pr72_admission_contribution_2026-09-11.json`: complete gate result and 13 scalar/hash receipts.
- `pr72_admission_ablations_2026-09-11.json`: fixed six-call plan, candidate derivation hashes and scalar/hash receipts.
- `run_pr72_admission_checks_2026-09-11.py` and `run_pr72_reference_ablations_2026-09-11.py`: executed reviewer recorders.

The full metrics remain exclusively on g450 in
`/home/azureuser/workspace-gzy/zyf/sle-pr72-admission-private-20260911-v2` and
`/home/azureuser/workspace-gzy/zyf/sle-pr72-ablations-private-20260911`, each directory
0700 and each full metrics file 0600. Public aggregates contain no world rows,
world-kind ordering or candidate answers. Logs are
`/tmp/sle-pr72-admission-contribution-20260911-v2.log`,
`/tmp/sle-pr72-ablations-20260911.log`, and
`/tmp/sle-pr72-admission-tests-20260911.log`. The original zero-call preflight is
`/tmp/sle-pr72-admission-contribution-20260911.log`; no completed scientific run
was overwritten or retried.

The engineering and shortcut checks pass, but the subsequent D16 comparison
fails. Root-wide evidence refresh/full-suite integration and external domain
review remain outstanding, and this task is held from merging. Repairs and all
outcomes are retained for further review; no status was promoted.
