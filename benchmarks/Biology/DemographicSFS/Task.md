# DemographicSFS-v2 — infer population history with a finite sequencing budget

## Scientific problem

The unfolded site-frequency spectrum (SFS) counts polymorphic loci carried by exactly
`i = 1, ..., n-1` chromosomes in a sample of size `n`. Under a neutral Kingman coalescent,
its expectation depends on population size backward through time. You allocate a fixed
sequencing budget across sample sizes, then recover a supported constant or three-epoch history,
or abstain when the data do not support any informative history in the public family.

The public family fixes ancestral size to one (otherwise time, size and mutation scale are not
jointly identifiable) and uses four shape parameters:

```text
N(t) / N_anc = recent_size_ratio          for 0 <= t < recent_epoch_end
             = middle_size_ratio          for recent_epoch_end <= t < middle_epoch_end
             = 1                          for t >= middle_epoch_end
```

Time is measured backward in `2*N_anc` generations. Public bounds are supplied to your code.
When both reported size ratios equal one, the mechanism is constant population size and the two
epoch boundaries are not identifiable; evaluation therefore ignores those boundary values for
that nested special case.
For sample size `n`, the lineage-count CTMC transitions from `k` to `k-1` at
`choose(k,2)/N(t)`. Conditional on `k` ancestral lineages, the expected number subtending `i`
sampled chromosomes is

```text
k * C(n-i-1, k-2) / C(n-1, k-1).
```

Integrating transient-state occupancy gives the expected unfolded SFS; for constant size it
reduces exactly to `theta/i`. Recent growth (large current relative to ancestral size) enriches
rare variants, while a recent bottleneck tends to deplete them. The direction is intentionally
stated correctly here; SFS shape alone does not identify arbitrary unrestricted histories.

## Artifact and sequencing API

Implement:

```python
def infer_demography(
    parameter_names, parameter_bounds, allowed_sample_sizes, sequence,
    budget_units,
):
    """Return a dict with:
      parameters: four finite values in parameter_names order
      confidence: scalar in [0,1] for the returned claim or refusal
      abstain: bool; True means the public three-epoch family is unsupported

    sequence(n_sample, replicates=1) returns:
      n_sample
      replicates
      unfolded_sfs_counts       # length n_sample-1 Poisson counts
      theta_per_panel             # aggregate mutation opportunity, not a per-base rate
      expected_count_scale
      budget_cost
      budget_used
    """
```

Allowed sample sizes are `(12, 20, 32, 48, 64)`. Replicates must be integers from one to four.
A call costs `ceil(n_sample * replicates / 48)` units, and the total per-world budget is eight.
Invalid or over-budget calls invalidate the world even if candidate code catches the exception.
Repeated calls are independent locus panels with deterministic but distinct Poisson draws.

## Evaluation

- `combined_score` measures development-world demographic mechanism recovery, normalized so
  always abstaining scores zero. Evaluator-only sample-size prediction never enters selection.
- Observed-menu SFS fit, held-out sample-size prediction, demographic mechanism recovery,
  confidence calibration and experiment usage are reported separately.
- Supported-world claim coverage, unsupported-world refusal and false discovery are separate.
- Development and held-out worlds include supported contraction/expansion histories, exact
  constant size and panels with resolvable ancestral-state polarization error. World kind is
  never supplied. Separate calibration
  counterexamples show that finite SFS data may not distinguish some four-epoch or population-
  mixture histories from a three-epoch projection; those are reported as limits, not used as
  impossible forced-refusal labels.

This is a controlled finite-panel coalescent inference benchmark. It does not infer any real
population's history, model linkage/recombination or population structure, or establish a
biological discovery.

## Rules

- Only edit `solution.py`; keep the `infer_demography` signature.
- Deterministic CPU code using Python, NumPy, SciPy and the standard library only.
- Do not assume world order, hidden parameters, Poisson realization or response kind.
- No network or process creation. Do not read `verification/` or `frontier_eval/`.
- `sle.contract_lint` is importable and free to call for shape checks.

## References

- Gutenkunst et al., *Inferring the Joint Demographic History of Multiple Populations from
  Multidimensional SNP Frequency Data*, PLoS Genetics 5(10), e1000695 (2009), DOI
  `10.1371/journal.pgen.1000695`.
- Jouganous et al., *Inferring the Joint Demographic History of Multiple Populations: Beyond the
  Diffusion Approximation*, Genetics 206(3), 1549–1567 (2017), DOI
  `10.1534/genetics.117.200493`.
- Myers, Fefferman and Patterson, *Can one learn history from the allelic spectrum?*,
  Theoretical Population Biology 73(3), 342–348 (2008), DOI
  `10.1016/j.tpb.2008.01.001`.
- Bhaskar and Song, *Descartes' rule of signs and the identifiability of population demographic
  models from genomic variation data*, Annals of Statistics 42(6), 2469–2493 (2014), DOI
  `10.1214/14-AOS1264`.
- Terhorst and Song, *Fundamental limits on the accuracy of demographic inference based on the
  sample frequency spectrum*, PNAS 112(25), 7677–7682 (2015), DOI
  `10.1073/pnas.1503717112`.
