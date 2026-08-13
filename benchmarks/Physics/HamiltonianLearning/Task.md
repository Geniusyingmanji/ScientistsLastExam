# Hamiltonian learning from spin-chain dynamics

Recover the Hamiltonian of a closed quantum spin chain from the dynamics it generates.

## Why this is inverse

An experiment does not record a Hamiltonian. It records expectation values of a few observables
as a function of time, and the map from parameters to those traces is strongly non-linear: two
different chains can produce identical single-site magnetisations, and once the evolution has
dephased the traces stop carrying information about the couplings at all. Reading the fields and
couplings back out is Hamiltonian learning, an active problem in quantum simulation and device
characterisation.

## Your function

```python
def learn_hamiltonian(observation) -> dict:
    ...
```

`observation` gives `spins`, the sampled `times`, the single-site `magnetisation` traces, and the
resolution below which a coupling cannot be distinguished from zero. Return

```python
{"fields": [...], "couplings": [[...], ...]}     # n fields, n x n symmetric
{"abstain": True}                                 # when the traces do not determine the chain
```

## Oracle

Dynamics come from **QuTiP**, the standard library for quantum dynamics, so the traces are
produced by its Schrodinger solver rather than a reimplementation. QuTiP is available to you:
simulate your own candidate Hamiltonians and compare, which is what device characterisation does.

## Three axes, reported separately

- **mechanism** — fields recovered within 0.1 and resolvable couplings within the larger of 0.1
  and 15%. This is what `combined_score` carries.
- **false discovery rate** — couplings claimed between spins that are in fact uncoupled. Every
  chain has at least one genuinely zero coupling.
- **calibrated refusal** — some chains carry an exchange symmetry: two spins with the same field,
  no direct coupling, and identical coupling to everyone else. The measured traces are identical
  under the swap, so those parameters are not identifiable and abstaining is the only correct
  answer. Abstaining elsewhere scores zero for that chain.

Parameters that differ only under the symmetry are excluded from scoring rather than counted as
misses, because no method can determine them.

## Rules

- Only edit `solution.py`; keep `learn_hamiltonian(observation)`.
- Deterministic CPU code. The standard library, NumPy, SciPy and QuTiP are available.
- `sle.contract_lint` is importable and free to call for shape checks.
- Do not read `verification/` or `frontier_eval/`.

## Difficulty

Chains are generated from a seeded draw over fields, couplings and sparsity. Harder levels add
spins, leave more couplings at zero and cut the number of time samples. Read the spin count and
sample times from the observation.
