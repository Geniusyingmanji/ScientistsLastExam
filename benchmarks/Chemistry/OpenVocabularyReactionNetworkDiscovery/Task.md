# OpenVocabularyReactionNetworkDiscovery

## Scientific question

Starting from a small heavy-atom inventory and one seed molecule, can an active policy construct
previously unlisted molecular graphs and directed elementary-reaction edges, recover the supported
network and its activation energies, and decline when the public mechanism class has no supported
edge or is inadequate?

The oracle is a deterministic analytic graph-reaction benchmark. Its energies are not quantum
chemistry, its atoms omit hydrogens and charge, and a high score is not evidence for a real
reaction mechanism.

## Relationship to neighbouring repository tasks

- `ReactionMechanismFitting` fits parameters on a supplied reaction network; this task must create
  species and edges with no candidate catalogue.
- `CatalystDeactivationLab` identifies and mitigates time-dependent loss on a known catalytic
  process; this task discovers a static graph network and includes explicit null/inadequate cases.
- `MolecularLeadOptimization` optimizes molecular candidates against property objectives; this
  task scores recovery and false discoveries of directed reaction edges.
- `ForceFieldCalibration` estimates continuous interaction parameters from observations; this
  task searches discrete graph topology and exact reduced barriers.
- `DistillationColumnDesign` optimizes a known process flowsheet; it neither creates chemical
  species nor discovers reaction connectivity.

The current cell uses a small graph grammar so that its oracle is exact and fast. Later waves can
enlarge the inventory and grammar, but this wave is not a relabelled instance of those neighbours.

## What to implement

```python
def discover_reaction_network(problem, probe):
    ...
```

Return either a network:

```python
{
    "species": [
        {"atoms": ["C", "C", "N", "O"], "bonds": [[0, 1, 1], ...]},
        ...,
    ],
    "reactions": [
        {"reactant": 0, "product": 1, "activation_energy": 54.2},
        ...,
    ],
    "abstain": False,
    "confidence": 0.8,
}
```

or `{"abstain": True, "confidence": 0.0}`.

`confidence` is the expected mechanism-recovery score of the network submitted in this world.
An abstention submits no network and therefore has recovery target zero. `confidence` must be a
finite number in `[0, 1]`; `abstain` must be a Boolean. `sle.contract_lint` is available as a free
shape checker and consumes no probe budget.

### Species and canonical identity

Each species has exactly two fields:

- `atoms`: two to six heavy-atom symbols. In this frozen cell every species must have exactly the
  multiset in `atom_inventory`.
- `bonds`: undirected `[left_atom_index, right_atom_index, order]` triples. Only order 1 is allowed.
  The graph must be connected, have no duplicate bond, and obey `element_valence_bounds`.

Atom indices are not chemical identities. The evaluator canonicalizes a coloured graph over all
element-preserving atom permutations. Two isomorphic graphs are one species, and submitting both
fails closed rather than earning duplicate credit. Directed edges are canonicalized by their
canonical reactant and product graphs; duplicate edges also fail closed. When repeated elements
admit several valid one-delete/one-add atom maps for the same canonical graph pair, the edge has
the minimum activation barrier across those channels. The output does not select a hidden atom map.

Every claimed reaction indexes two different submitted species. It must obey the public
`elementary_edge_rule`: delete one single heavy-atom bond and form one different single bond while
preserving connectedness. `activation_energy` must be finite and in `[0, 250]` reduced kJ/mol.

## Active probe

One charged query has this form:

```python
probe({"reactant": species_graph, "product": species_graph})
```

The proposed graphs need not have appeared before. A valid response contains:

- `status`: `supported`, `unsupported`, or `model_inadequate`;
- `activation_energy`: the exact value for a supported edge, otherwise `None`;
- `budget_cost`: 1;
- `remaining_budget`: calls left.

Malformed graphs, non-elementary edges, caught callback violations, and calls after `probe_budget`
invalidate that world. Repeating an edge costs another call.

## Every public `problem` key

| key | meaning |
|---|---|
| `atom_inventory` | conserved heavy-atom multiset; currently `C, C, N, O` |
| `seed_species` | a one-element list containing the valid starting graph; it is not a catalogue of all possible species |
| `probe_budget` | maximum charged calls, currently 24 |
| `max_claimed_species` | maximum number of submitted canonical species |
| `max_claimed_reactions` | maximum number of submitted directed edges |
| `allowed_bond_orders` | bond orders supported by this cell, currently `[1]` |
| `element_valence_bounds` | graph-validity degree bounds by element |
| `elementary_edge_rule` | the allowed one-bond-exchange grammar |
| `probe_response` | meanings of the three response statuses |
| `abstain_when` | the two scientifically correct refusal cases |

There are deliberately no `candidate_species` or `candidate_reactions` keys.

The container shape is intentional. Read the starting graph as
`problem["seed_species"][0]`, not as `problem["seed_species"]`:

```python
{
    "seed_species": [{"atoms": ["C", "C", "N", "O"], "bonds": [[0, 1, 1], ...]}],
    "atom_inventory": ["C", "C", "N", "O"],
    # the remaining keys are exactly those in the table above
}
```

The list has length one in this wave so a later immutable wave may provide several admissible
starting species without changing the public type. It does not expose any unobserved product.

## Evaluation

Supported worlds score a mechanism recovery value made from canonical reaction F1 (65%), species
F1 (20%), and activation-energy accuracy on correctly recovered edges (15%). Null and
model-inadequate worlds score one only for refusal. The public `combined_score` averages those
world outcomes and subtracts the credit earned by declining every world. Consequently an
always-abstaining policy is valid and scores exactly `0.0`; the independent 24-query active-frontier
witness defines `1.0`.

The independent reference prioritizes unseen product graphs, then uses a fixed qualitative
bond-strength rank as a low-barrier surrogate and public grammar branching as an information-gain
tie-break. It depends only on the public problem, its explicit chemical prior, and at most 24
charged probes. Its development raw score is the normalization anchor at `1.0`; an
always-abstaining policy and the shipped confidently wrong legal edge both score `0.0`. The score
is uncapped, so complete oracle recovery can exceed the budgeted reference rather than being hidden
by clipping.

The executable deterministic ladder is fixed wrong edge = blanket refusal = `0.0`, a 1024-ordering
BFS sweep `0.9578902692868527`, budgeted reference `1.0`, and complete evaluator-only recovery
`1.0421807272444035`. Removing novelty priority, the qualitative barrier surrogate, or public
branching priority gives `0.9645472862744551`, `0.9257058383039174`, and
`0.996111761955115`. These are algorithmic ablations inside a four-heavy-atom synthetic grammar;
they do not certify chemical realism or long-horizon difficulty.

The evaluator reports the four discovery axes separately:

- `development_mechanism_recovery` and `heldout_mechanism_recovery`;
- `development_false_discovery_rate` and `heldout_false_discovery_rate`;
- `development_calibrated_refusal_score` and `heldout_calibrated_refusal_score`, which require
  both a correct refusal and low confidence in a supported network; raw
  `development_correct_refusal_rate` and `heldout_correct_refusal_rate` remain visible;
- `development_attempted_discovery_rate` and `heldout_attempted_discovery_rate` (also exposed as
  `development_discovery_coverage` and `heldout_discovery_coverage`).

It also reports general confidence calibration, mean charged probes, `development_mechanism_score`,
`heldout_mechanism_score`, feasibility, and evaluator-only per-instance rows. A high recovery
score cannot erase false edges, blanket refusal, or failure to attempt discovery.

## Rules

- Edit only `solution.py`; keep `discover_reaction_network(problem, probe)`.
- Use at most `probe_budget` calls and submit no more than the public size bounds.
- Deterministic CPU code only; standard library/NumPy/SciPy, no network or process creation.
- Do not read `verification/` or `frontier_eval/`.
- Treat this cell as a synthetic algorithmic test. Real-mechanism claims require electronic
  structure, kinetic validation, experimental products, uncertainty analysis and independent
  confirmation outside this benchmark.

The references below motivate automated reaction-network exploration, graph transformations,
barrier--reaction-energy relations and transition-state kinetics. The graph grammar, barrier
formula and weights, world parameters, thresholds and probe budget are benchmark-chosen rather
than literature-calibrated. Taking the minimum barrier over repeated-element mapping channels is a
deterministic graph-pair convention; physical parallel-channel rate models would generally combine
rates and degeneracies instead.

References: Unsleber and Reiher, *J. Chem. Theory Comput.* (2022), SCINE Chemoton 2.0,
DOI `10.1021/acs.jctc.2c00193`; Martínez-Núñez et al., *J. Comput. Chem.* (2021), AutoMeKin2021,
DOI `10.1002/jcc.26734`; Rosselló and Valiente, *Electronic Notes in Theoretical Computer Science*
(2005), chemical graph transformation, DOI `10.1016/j.entcs.2004.12.033`; Evans and Polanyi,
*Transactions of the Faraday Society* (1938), barrier--reaction-energy relation, DOI
`10.1039/TF9383400011`; Eyring, *J. Chem. Phys.* (1935), transition-state kinetics, DOI
`10.1063/1.1749604`.
