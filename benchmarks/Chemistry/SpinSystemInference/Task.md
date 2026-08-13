# Spin system inference

Given a high-resolution proton NMR spectrum, recover the spin system that produced it: the
chemical shift of every spin and the scalar coupling between every pair.

## Why this is inverse and not arithmetic

A first-order reading — count the lines, halve the splittings — works only when the shifts are far
apart relative to the couplings. When they are not, the system is second order: peak positions stop
being sums of shifts and couplings, intensities redistribute across transitions (the roof effect),
and lines can overlap or vanish. The spectrum is the eigenspectrum of a Zeeman-plus-coupling
Hamiltonian, and reading the Hamiltonian back out of it is the daily work of spectral assignment.

## Your function

```python
def infer_spin_system(observation) -> dict:
    ...
```

`observation` gives you `peaks` (a list of `[frequency_hz, intensity]`), `spins` (how many),
`linewidth_hz`, and `resolvable_coupling_hz`. Return

```python
{"shifts": [...], "couplings": [[...], ...]}     # n shifts, n x n symmetric
{"abstain": True}                                 # when the spectrum does not determine the system
```

Shift ordering is not observable, so any permutation of a correct answer scores the same.

## Oracle

Spectra come from **nmrsim**, which builds and diagonalises the full Hamiltonian rather than
applying first-order multiplet rules. A score here measures agreement with the quantum mechanics,
not with a reimplementation of it. nmrsim is available to you as well: simulate your own candidate
spin systems and compare, which is what spectral-fitting programs do.

## Three axes, reported separately

This is a discovery task, and one number cannot express whether a discovery was right.

- **mechanism** — how many shifts land within two linewidths, and how many resolvable couplings
  land within the larger of 0.5 Hz and 10%. This is what `combined_score` carries.
- **false discovery rate** — how often a coupling is claimed where the truth has none. Some pairs
  in every world are genuinely uncoupled.
- **calibrated refusal** — some worlds contain two magnetically equivalent spins, whose mutual
  coupling has no effect on the spectrum at all. No method can recover it, and the only correct
  answer is `{"abstain": True}`. Abstaining anywhere else scores zero for that world, so refusing
  everything buys nothing.

The three are printed side by side in the metrics and must not be averaged. A fitter can look
respectable on mechanism while inventing couplings a quarter of the time, and the combined number
would hide exactly that.

## Rules

- Only edit `solution.py`; keep `infer_spin_system(observation)`.
- Deterministic CPU code. The standard library, NumPy, SciPy and nmrsim are available.
- `sle.contract_lint` is importable and free to call for shape checks.
- Do not read `verification/` or `frontier_eval/`.

## Difficulty

Worlds are generated from a seeded draw over shift spacing, coupling strength and coupling
sparsity, not written by hand. Harder levels add spins and push the shifts closer together, which
is what makes a system second order. Read the spin count from the observation rather than assuming
it.
