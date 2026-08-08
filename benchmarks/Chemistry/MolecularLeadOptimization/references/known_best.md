# MolecularLeadOptimization — known best values

Measured 2026-08-08 on the benchmark host (Linux, Python 3.8, RDKit 2024.03.5). All values are
recomputed by the oracle at evaluation time; none is quoted from a paper.

## Reference panel

Twenty approved small-molecule drugs. Each SMILES was checked against its published average
molecular weight before admission; the largest deviation was 0.02 g/mol, consistent with
isotope-averaging rounding. The panel serves two purposes: it sets the quality anchor, and it
defines the novelty exclusion zone that stops a candidate from returning memorized drugs.

| Profile | panel members passing | reference mean QED | `n_required` | diversity ceiling |
|---|---:|---:|---:|---:|
| development `oral_lead` | 11 | **0.6998** | 120 | Tanimoto < 0.25 |
| sealed `tight_permeable` | 8 | **0.7313** | 60 | Tanimoto < 0.20 |

The panel is far smaller than `n_required` on purpose. The anchor is a *quality level* — the
average drug-likeness of structurally distinct approved drugs — not a target set to be matched
molecule for molecule.

## Calibration ladder

| Designer | development | sealed |
|---|---:|---:|
| Shipped baseline — eight trivial molecules | **0.0000** | 0.0000 |
| Reference — combinatorial enumeration over 20 cores × 20 substituents (13/120 retained) | **0.1401** | 0.1447 |
| GPT-5.6, budget one, best of five draws | **0.5211** | 0.3439 |
| Full portfolio at approved-drug quality | **1.0000** (by definition) | 1.0000 |
| Full portfolio at the QED ceiling | ≈ **1.35** | ≈ 1.30 |

## Model calibration: five GPT-5.6 budget-one draws

Run on the benchmark host through the harness sandbox, `greedy_rewrite`, normal feedback,
one proposal per seed.

| seed | development | sealed | retained | portfolio fill |
|---|---:|---:|---:|---:|
| 0 | invalid | — | — | — |
| 1 | 0.5211 | 0.3439 | 52 | 0.43 |
| 2 | 0.2873 | 0.2818 | 28 | 0.23 |
| 3 | 0.3641 | 0.3246 | 37 | 0.31 |
| 4 | 0.3300 | 0.3165 | 32 | 0.27 |

Valid 4/5; mean 0.3756, median 0.3471, range 0.2873–0.5211. Seed 0 failed by passing `None`
into an RDKit constructor — an unguarded `MolFromSmiles` in the candidate, not a task defect.

## Why the portfolio is 120 molecules

This was set by measurement. At an earlier sizing of 40 the same five draws scored
0.86 / 0.99 / 1.09 / 1.25 on the four valid runs — three above 0.95, against a theoretical
maximum of 1.35. Inspecting the best draw showed why: it submitted **53 molecules out of an
allowed 2000** and retained 52. It hand-wrote a diverse set from chemical knowledge and never
ran a search at all. Forty distinct chemotypes is inside one-shot recall; 120 is not.

## Why QED alone does not solve this

Also tested, not assumed. The reference enumerator reaches **mean QED 0.9454** on the molecules
it retains — essentially the QED ceiling, above every drug in the panel — and still scores
0.1401, because it fields only **13 of the 120** required mutually dissimilar scaffolds. The
measured decay for its 2540-molecule pool:

| diversity ceiling | mutually dissimilar pool |
|---|---:|
| Tanimoto < 0.40 | 69 |
| Tanimoto < 0.30 | 27 |
| Tanimoto < 0.25 | 14 |
| Tanimoto < 0.20 | 8 |

Drug-likeness saturates; scaffold diversity does not. The number of distinct developable
chemotypes above approved-drug quality is not known, hence the uncapped score.

## Interpretation limits

QED, the SA score and PAINS are computational proxies. No target activity, selectivity,
pharmacokinetics or toxicity is modelled. A score above 1.0 is a cheminformatics result about
diversity-constrained generation, **not** evidence of a drug candidate.

## Reproduce

```bash
python -m frontier_science eval --allow-uncertified --task MedicinalChemistry/MolecularLeadOptimization
```
