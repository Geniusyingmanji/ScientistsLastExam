# SuperconductorTcRecord — beat the published record by computing where Allen-Dynes says to look

## Scientific setting

Five real conventional (phonon-mediated, BCS/Eliashberg) superconductor families, plus one real
theoretical prediction that was never experimentally realized. Critical temperature is computed
directly from the public **Allen-Dynes formula**:

```
Tc_kelvin = (omega_log_k / 1.2) * exp(-1.04*(1+lambda) / (lambda - mu_star*(1+0.62*lambda)))
```

with `mu_star = 0.10`. This is not a fitted curve you have to trust — it is the same formula you
can run yourself, and this task's own ground truth is built by solving, not guessing, the `lambda`
that makes this formula reproduce every cited (pressure, Tc) record below exactly (see
`references/known_best.md` for the derivation, fully re-runnable).

| family | literal citation(s) | citation |
|---|---|---|
| `MgB2boride`   | 39 K, ambient | Nagamatsu et al. 2001, *Nature* 410, 63 |
| `H3Shydride`   | 203 K at 155 GPa | Drozdov et al. 2015, *Nature* 525, 73 |
| `LaH10hydride` | 246 K at 136 GPa; 250 K at 170 GPa | Errea et al. 2020, *Nature* 578, 66; Drozdov et al. 2019, *Nature* 569, 528 |
| `YH6hydride`   | 227 K at 237 GPa | Kong et al. 2021, *Nat. Commun.* 12, 5075 |
| `YH9hydride`   | 243 K at 201 GPa | Kong et al. 2021, *Nat. Commun.* 12, 5075 |
| `YH10fcc`      | 305–326 K at 250 GPa (never realized) | Liu et al. 2017, *PNAS* 114, 6990 |

**Feasibility is a computable criterion, not a record of laboratory history.** A `(family,
pressure)` point is dynamically implausible — and its Allen-Dynes Tc is not achievable — if it
falls outside a family's disclosed pressure window, or if the `lambda` the formula would need
exceeds **3.5**, the highest electron-phonon coupling established anywhere in this literature
(Errea et al. 2020's own anharmonic-corrected value for LaH10). Reaching `YH10fcc`'s proxy claim
of 305–326 K would require `lambda ≈ 3.95` at a comparable phonon energy scale — above that ceiling
— which is exactly why it was never realized, and you can verify this yourself from the same
formula rather than taking it on faith.

Your apparatus has a maximum pressure it can reach (`apparatus_pressure_ceiling_gpa`), a real,
disclosed engineering constraint. `problem["families"]` lists only the families whose window
comes into reach at all.

## Your task

Implement:

```python
def design_superconductor(problem, probe):
    """Return {"family": ..., "pressure_gpa": ..., "predicted_tc_k": ..., "confidence": ...}."""
```

`problem` contains:

- `families`: the families in reach at this apparatus ceiling;
- `historical_proxy`: a real, pre-experimental (or independently sourced) Tc estimate per family
  — public information, **not** what `combined_score` is computed from;
- `apparatus_pressure_ceiling_gpa`, `probe_budget_calls`;
- `allen_dynes_formula`, `lambda_max_plausible` (3.5), `known_record_tc_k` (250.0 — the actual
  best confirmed Tc in this literature, Drozdov et al. 2019);
- `measurement_model`, `scope_note`: prose context.

### `probe(family, pressure_gpa)`

`family` must be one of `problem["families"]`; `pressure_gpa` any finite value in
`[0, apparatus_pressure_ceiling_gpa]` — not restricted to a pressure a paper happens to report.
Each call charges one unit of `probe_budget_calls`. It returns:

```python
{"lambda_hat": ..., "omega_log_k_hat": ..., "dynamically_stable": ...}
```

Apply `allen_dynes_formula` yourself to `lambda_hat`/`omega_log_k_hat` to estimate Tc — the same
computation the oracle itself does on the true values. `dynamically_stable` is exact (no noise):
false outside a family's window, and false wherever the implied `lambda` exceeds
`lambda_max_plausible`. Repeating the same `(family, pressure_gpa)` is a fresh, independently
noisy draw and costs another unit. Calling past the budget raises and the world scores zero.

### What you return

`family` must be in `problem["families"]`. `pressure_gpa` must be finite and in
`[0, apparatus_pressure_ceiling_gpa]`. `predicted_tc_k` must be a finite number `>= 0` — a
diagnostic only, not part of the score. `confidence` must be finite and in `[0, 1]`. Anything
malformed scores that world zero.

## Evaluation

`combined_score` is the scored (development) apparatus instance:

```
combined_score = true_Tc_at_your_submission_K / 250.0
```

`true_Tc` is computed from the true `lambda`/`omega_log` at your submitted point via the same
Allen-Dynes formula — `0` if not dynamically stable. **250.0 is `known_record_tc_k`: the actual
headline confirmed Tc these papers report (Drozdov et al. 2019), not a search algorithm's own
achieved value.** This is a plain ratio: match the published record and score 1.0; find a
pressure this literature's own formula says does better — which the record-setting papers
themselves did not test — and score above 1.0. A held-out apparatus scenario is scored too and not
fed back to search.

## Available tools and resources

NumPy and SciPy are available. Domain knowledge about Eliashberg/Allen-Dynes theory, why harmonic
DFT can over- or under-shoot an eventual confirmed value, why electron-phonon coupling has a
physically plausible ceiling, and continuous optimization under a noisy, budgeted oracle
(replicate-averaging against noise, local climbing/refinement) can all inform the policy.
Candidate execution is networkless and cannot look anything up.

## Rules and scope

- Only edit `solution.py`; keep `design_superconductor(problem, probe)`.
- Return exactly one `(family, pressure_gpa)` pair.
- Use at most `probe_budget_calls` probes.
- Deterministic CPU code only; no network or process creation.
- Do not read `verification/` or `frontier_eval/`.

This task scores a real, public formula evaluated at true parameters solved to exactly reproduce
six cited (family, pressure, Tc) records; it does not perform a live electronic-structure
calculation and does not predict a new material. `sle.contract_lint` is importable inside the
sandbox and costs no oracle call.

References: Nagamatsu et al., *Nature* 410, 63 (2001), DOI `10.1038/35065039`; Duan et al.,
*Sci. Rep.* 4, 6968 (2014), DOI `10.1038/srep06968`; Drozdov et al., *Nature* 525, 73 (2015), DOI
`10.1038/nature14964`; Liu et al., *PNAS* 114, 6990 (2017), DOI `10.1073/pnas.1704505114`; Drozdov
et al., *Nature* 569, 528 (2019), DOI `10.1038/s41586-019-1201-8`; Somayazulu et al., *Phys. Rev.
Lett.* 122, 027001 (2019), DOI `10.1103/PhysRevLett.122.027001`; Errea et al., *Nature* 578, 66
(2020), DOI `10.1038/s41586-020-1955-z`; Troyan et al., *Adv. Mater.* 33, 2006832 (2021), DOI
`10.1002/adma.202006832`; Kong et al., *Nat. Commun.* 12, 5075 (2021), DOI
`10.1038/s41467-021-25372-2`; Allen and Dynes, *Phys. Rev. B* 12, 905 (1975), DOI
`10.1103/PhysRevB.12.905`.

## Inputs the candidate receives

Every key the task passes to the candidate, taken from the baseline's reads and from the
evaluator's own construction of the input mapping. Names are part of the contract: a candidate
that reaches for one of these quantities under a different name raises at runtime and scores
nothing, and that zero cannot be told apart from a zero earned on the science.

| key | |
|---|---|
| `allen_dynes_formula` | read by the baseline |
| `apparatus_pressure_ceiling_gpa` | read by the baseline |
| `families` | read by the baseline |
| `historical_proxy` | read by the baseline |
| `known_record_tc_k` | read by the baseline |
| `lambda_max_plausible` | read by the baseline |
| `measurement_model` | read by the baseline |
| `probe_budget_calls` | read by the baseline |
| `scope_note` | read by the baseline |
