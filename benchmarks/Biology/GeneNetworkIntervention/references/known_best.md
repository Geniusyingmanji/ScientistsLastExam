# Known best — GeneNetworkIntervention

## Anchor

`verification/reference_network.py` is a truth-blind identification, run through the task's own
evaluator. It uses only what a candidate receives — the gene names, the perturbation callback,
the published objective and the budget — and never reads the hidden world.

Reproduce with:

```bash
python scripts/measure_reference.py --task Biology/GeneNetworkIntervention \
    --reference verification/reference_network.py --entry discover_gene_network
```

| | every recorded model proposal | reference |
|---|---:|---:|
| `combined_score` | 0.0000 | **0.3926** |
| `development_supported_claim_coverage` | 0.0 | 1.0 |
| `development_false_discovery_rate` | 0.0 | 0.0 |
| `development_unsupported_refusal_rate` | 1.0 | 1.0 |
| `development_mechanism_score` | 0.0 | **0.8255** |
| `heldout_mechanism_score` | — | 0.9279 |

The reference is perfect on all three discovery axes and adds mechanism recovery on top. The model
column reaches the same refusal and false-discovery numbers only because declining every world
cannot misfire.

`combined_score` stays at 0.39 because it is a geometric joint of mechanism, sealed trajectory
prediction and phenotype-intervention utility. Recovering the network is not the whole task, and
the gap between 0.93 mechanism and 0.39 joint is the headroom the task still has.

## What the reference does

1. **Design** — seven experiments, 13 of 24 budget units: one unperturbed run to see the resting
   state, then each of the three actionable regulators repressed and activated in turn. Single-gene
   perturbations are what make the weight matrix separable; spending the budget on combinations
   first would confound the columns.
2. **Fit** — least squares over the published dynamics, integrated the way the evaluator
   integrates them, for weights, biases and decay rates together. The diagonal is excluded from
   the parameter vector rather than zeroed afterwards, because the public model has no
   self-regulation and a fit allowed to use the diagonal absorbs real off-diagonal signal into it.
3. **Select** — backward elimination on the edges, by BIC. Thresholding magnitudes is not enough:
   least squares puts a little of the noise into every edge, so on a null world several entries
   clear any fixed threshold and the world gets claimed.
4. **Refuse** — by cross-validation, not residual size. The callback declares no noise level, so a
   raw residual has no scale to be judged against; a model that fits what it saw and then fails to
   predict a held-out experiment is misspecified, which is what a hidden regulator looks like from
   inside the observed genes. Abstain also when no edge survives selection, which is the null
   world.
5. **Intervene** — grid search over the allowed one- and two-gene doses, scored on the published
   objective under the fitted model.

## Measured separation

Held-out prediction error divided by fit error, by world kind:

| kind | ratio |
|---|---|
| `in_library` | 1.09 – 2.25 |
| `null` | 1.07 – 1.11 |
| `hidden_regulator` | 3.17 – 3.28 |

The threshold sits at 2.7, between the groups rather than on either edge.

## Three corrections, and what each showed

| attempt | change | combined | mechanism (dev) | refusal (dev) |
|---|---|---:|---:|---:|
| 1 | fit all weights, threshold at 0.15 | invalid | — | — |
| 2 | exclude the diagonal from the fit | 0.1572 | 0.5432 | 0.5 |
| 3 | BIC backward elimination, noise-scaled | **0.3926** | **0.8255** | **1.0** |

Attempt 1 was rejected outright: the evaluator refuses a weight matrix with a non-zero diagonal,
and a fit free to use the diagonal will. Attempt 3 needed the BIC scaled by an estimated noise
variance — comparing a sum of squares in expression units against a per-parameter penalty of
log N makes the penalty win every time, and an unscaled version pruned every edge on every world
and abstained everywhere. Estimating the variance once from the full model is what made the
criterion comparable across the nested fits.
