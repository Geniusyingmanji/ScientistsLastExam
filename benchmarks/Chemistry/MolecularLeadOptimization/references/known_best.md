# MolecularLeadOptimization — known best values

Measured 2026-08-07 with RDKit 2025.09.3. All values are recomputed by the oracle at evaluation
time; none is quoted from a paper.

## Reference panel

Twenty approved small-molecule drugs. Each SMILES was checked against its published average
molecular weight before admission; the largest deviation was 0.02 g/mol, consistent with
isotope-averaging rounding. The panel serves two purposes: it sets the quality anchor, and it
defines the novelty exclusion zone that stops a candidate from returning memorized drugs.

| Profile | panel members passing the filter | reference mean QED | `n_required` | diversity ceiling |
|---|---:|---:|---:|---:|
| development `oral_lead` | 11 | **0.6998** | 40 | Tanimoto < 0.25 |
| sealed `tight_permeable` | 8 | **0.7313** | 30 | Tanimoto < 0.20 |

The panel is far smaller than `n_required` on purpose. The anchor is a *quality level* — the
average drug-likeness of structurally distinct approved drugs — not a target set to be matched
molecule for molecule.

## Calibration ladder

| Designer | development | sealed |
|---|---:|---:|
| Shipped baseline — eight trivial molecules | **0.0000** | 0.0000 |
| Reference — combinatorial enumeration over 20 privileged cores × 20 substituents | **0.4202** | 0.2893 |
| Full portfolio at approved-drug quality | **1.0000** (by definition) | 1.0000 |
| Full portfolio above approved-drug quality | **> 1.0** | > 1.0 |

## Why QED alone does not solve this

This was tested, not assumed. The reference enumerator reaches **mean QED 0.9454** on the
molecules it retains — essentially the QED ceiling, and well above every drug in the panel. It
still scores only 0.4202, because it can field just **13 of the 40** required mutually
dissimilar scaffolds.

The measured decay makes the binding constraint explicit. For the same 2540-molecule enumerated
pool:

| diversity ceiling | mutually dissimilar pool |
|---|---:|
| Tanimoto < 0.40 | 69 |
| Tanimoto < 0.30 | 27 |
| Tanimoto < 0.25 | 14 |
| Tanimoto < 0.20 | 8 |

Drug-likeness saturates; scaffold diversity does not. Reaching 1.0 requires exploring chemical
space broadly enough to find forty unrelated chemotypes that simultaneously clear the
physicochemical window, the synthetic-accessibility ceiling, the PAINS catalogue and the
novelty filter. No enumeration over a fixed core list does that, and the number of such
chemotypes is not known — hence the uncapped score.

The sealed profile is harder than the development profile for the reference designer (0.2893
versus 0.4202), which is the intended generalization gap: it tightens the diversity ceiling to
0.20 and narrows the physicochemical window, so a search tuned to the development scaffold
space loses ground.

## Interpretation limits

QED, the SA score and PAINS are computational proxies. No target activity, selectivity,
pharmacokinetics or toxicity is modelled. A score above 1.0 is a cheminformatics result about
diversity-constrained generation, **not** evidence of a drug candidate.

## Reproduce

```bash
python -m frontier_science eval --allow-uncertified --task MedicinalChemistry/MolecularLeadOptimization
```

Runtime is dominated by the candidate's own search; the oracle's filtering of 2000 submissions
takes a few seconds per profile.
