# Reference and admission record — CompositeLaminateStacking

## 1. Reference method

`verification/reference.py` is standalone and uses only public inputs and charged interfaces. Ten seeded permutation starts are followed by one adjacent-exchange refinement pass; the evaluator independently runs the stronger 900-start/full-pair anchor.
It is a method witness, not independent high-fidelity verification. The new witness refines permutations rather than stopping after random screening. Paired bending moments and both-face Tsai-Hill stress now make first-ply failure depend on stacking order; the old membrane-only invariant-strength limitation was corrected. Independent anisotropic buckling review is pending.

## 2. Baseline and normalization

The shipped `solution.py` is the zero baseline. The runnable budgeted search scores `0.732584`
development / `0.724395` held-out against the reproducible stronger search anchor. Denser starts
and wider pair exchanges are the measured headroom. The scale is floored at zero and uncapped.

## 3. Capability comparisons and ablations

Run `python scripts/diagnose_pr9_engineering.py --output tmp/hardening/diagnostics.json --sweeps`.
On the current dirty macOS tree, ten starts plus one adjacent-exchange pass score `0.732584`
development and `0.724395` robustness. Replaying the historical random-screening construction on
the current bending-sensitive oracle clips to `0.000000` development, with `0.290505` robustness
and `0.599186` held-out policy score. This is a cross-version method comparison, not an isolated
ablation.

## 4. Shortcut probes

The quasi-isotropic repeating baseline scores zero, and the historical random-screening method
also clips to zero on development. The current reference-to-anchor gap is entirely additional
permutation starts and wider pair exchanges, so it is genuine finite-search headroom but not yet a
frontier-model difficulty result. Lamination-parameter rounding and deterministic block-pattern
families remain unmeasured. These values are local diagnostics, not frozen benchmark evidence.

## 5. Frontier-model calibration

Not run. This task remains `candidate`. A clean Linux model draw, frozen before exposure, must
show that the first proposal does not reach the competent reference. No calibration or external
review is implied by these local code changes. Server-held worlds and independent model review
remain required.

## 6. Construction errors and revisions

2026-09-05 hardening: The new witness refines permutations rather than stopping after random screening. Paired bending moments and both-face Tsai-Hill stress now make first-ply failure depend on stacking order; the old membrane-only invariant-strength limitation was corrected. Independent anisotropic buckling review is pending.
Standalone references no longer import the hidden evaluator. The task card records the review
lineage, licensing uncertainty and public-world contamination risk. Earlier measurements below
belong to the pre-hardening version and are retained only as history.

## 7. Robustness and reproducibility

Development and heldout metrics remain separate. The new tests cover anchor feasibility,
equivalent-parameter scoring, mass conservation, time refinement, forecast-unit invariance,
instrument error poisoning and malformed submissions as applicable. Formal Linux sandbox
replay, global evidence refresh and independent scientific replication are still pending.
See the task card citations for background; the explicitly declared reduced model is not
certified by those publications.

## Historical pre-hardening record (obsolete scores)

# Reference witness

The normalization witness performs 900 fixed-seed permutations of the public symmetric half
laminate and retains the best valid sequence under the same nominal CLT oracle. It is truth-blind,
deterministic and deliberately not a proof of global optimality. It defined score one in the
historical version and stronger sequences could exceed one. No frontier-model or
two-hour calibration has yet been run.
