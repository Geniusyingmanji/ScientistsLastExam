# DistributionNetworkTopology — noisy Boolean route tomography

A supplied graph has hidden broken pipes. A route fails if any pipe on it is
broken; each report flips independently with a published probability. Recover the
broken set, or refuse when a unique sparse break explanation is unsupported.
Some failures lie on two service pipes with identical route signatures. Other
worlds have independent fair-coin telemetry failures, outside the sparse-break model.

```python
def recover_network(problem, probe, budget_units):
    # Return a mapping with these fields:
    return {"broken_pipes": ["pipe id"], "abstain": False, "confidence": 0.8}
```

`problem` contains every public input:

| Key | Meaning |
|---|---|
| `pipe_ids` | Available pipe identifiers |
| `parallel_service_pipes` | Two indistinguishable service-pipe identifiers |
| `routes` | Route identifier to ordered pipe list; 4x4 grid plus service corridor |
| `probe_cost` | One unit per call |
| `budget_units` | Total budget, 26 units including the initial reports |
| `initial_reports` | Three already paid reports on the service corridor |
| `flip_probability` | Supported/alias report flip probability, 0.07 at the default |
| `max_broken` | Maximum supported break-set cardinality, 3 at the default |
| `route_note` | Description of the Boolean observation law |
| `claim_note` | Explanation of structural service-pipe ambiguity |

`probe(route_id)` returns `{route_id, arrived, budget_cost}` and charges one unit.
The function argument `budget_units` is **23 remaining units**. The initial reports
consume three units of the same 26-unit budget. Repeat measurements draw fresh
noise; they are not free. Unknown identifiers, malformed calls and overspending
invalidate that world even if the exception is caught.

A claim lists one to six distinct known pipes. `abstain` must be boolean and
`confidence` finite in [0,1]. For abstention, omit `broken_pipes` or use `None`
or an empty list. Nonempty pipes and abstention are contradictory and invalid.

## Evaluation

The development cohort contains 24 supported worlds, equally stratified across
one, two and three breaks, six structural aliases and six telemetry-fault worlds.
Heldout uses independent seeds with 18 supported, six alias and six fault worlds.
For a supported world, recovery is squared Jaccard:
`(|claim ∩ truth| / |claim ∪ truth|)**2`. Abstention earns zero there. Unsupported
worlds earn one for abstention and zero for a claim. The raw mean is normalized
above the always-abstain baseline and clipped to [0,1], so full abstention scores
exactly zero. `combined_score` uses development; `robustness_score` uses heldout.

Set F1 remains a diagnostic. Mechanism quality, confidence calibration, false
discovery, correct refusal and discovery coverage are reported separately, with
counts and denominators. Confidence predicts the quality of the response, including
refusal, and is evaluated as one minus squared error. Invalid rows score zero and
do not count as discovery attempts. `valid=1` means at least one valid development
world; `feasibility_rate` reports the valid fraction. One bad world does not erase
other worlds' scores. All-invalid returned artifacts return `valid=0, combined_score=0`.

Use `sle.contract_lint` for free local submission-shape checks.
Only edit `solution.py`. Use deterministic Python/NumPy/SciPy/stdlib, without
network or process creation. Do not read `verification/` or `frontier_eval/`.

## Model sources and nearby tasks

This is a synthetic Boolean model, not a hydraulic, pressure or tracer simulator.
The OR-failure/identifiability model is supported by
[Ma et al., IMC 2014](https://doi.org/10.1145/2663716.2663723).
[Ostfeld et al., 2008](https://doi.org/10.1061/(ASCE)0733-9496(2008)134:6(556))
is water-sensor application context only.

GraphFromDistances reconstructs weighted edges from distances;
HiddenCouplingNetwork infers dynamical interactions; ModalDamageAttribution recovers
stiffness damage from modal shifts. Here the unknown is a sparse Boolean failure
set, with both structural ambiguity and observation-model inadequacy.

The Frontier-Eng comparison is in
`.research/distribution_network_topology_frontier_eng_overlap_2026-09-07.md`.
The pinned available catalog has 78 rows / 84 expanded entries; the documented
95-entry source remains unresolved. This package remains **candidate**. Review
replays and capability ablations are in `references/known_best.md`; they do not
establish expert difficulty or replace fresh worlds. A frozen current-source
gpt-5.6-sol first-proposal campaign also failed the D16 admission check because one
fully valid proposal scored 1.000000 development against the 0.927083 reference.

Each sandbox world starts a fresh candidate session. Module globals and temporary
files cannot carry a world index or previous answers across worlds.

The per-world validity rule applies to decoded artifacts and caught oracle-call
errors. Worker crashes, uncaught runtime errors, sandbox violations and the overall
timeout fail the run through the trusted harness.

Measured capability comparisons (development / heldout):

| Variant | Scores |
|---|---|
| Full witness | 0.927083 / 0.802469 |
| Without adaptive route choice | 0.416667 / 0.396605 |
| Without the cardinality prior | 0.875000 / 0.847222 |
| At most two-pipe hypotheses | 0.722222 / 0.685185 |
| Without telemetry model checking | 0.843750 / 0.635802 |
| Without structural ambiguity refusal | 0.635417 / 0.469136 |

These are diagnostic capability comparisons, not model calibration.
In particular, the no-cardinality-prior variant is better on heldout, so that prior
is not claimed as a split-robust necessary capability.

The external `frontier_eval/run_eval.py` writes only search-visible metrics. Full
diagnostics can be saved with `--full-metrics-dir` to an explicitly private
directory outside both the candidate and public output directories. Infrastructure
failures exit 2 with no public score file, following the shared trusted entrypoint.
