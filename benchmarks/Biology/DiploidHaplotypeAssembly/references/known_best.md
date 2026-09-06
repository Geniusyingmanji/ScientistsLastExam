# Internal reference evidence — 2026-09-05

## 1. Scoring anchor and baseline

The exact public model and normalization are in Task.md. The legal solution.py
baseline has development score 0.00000000, valid=1.
Scores are clipped; reference=1 is an anchor, not a record or frontier claim.
Discovery tasks instead normalize above the no-discovery floor toward perfect
scientific recovery; their classical reference need not reach one.

## 2. Input-only executable reference

`references/reference.py` is standalone and accepts only the same public input
and charged observation callback as a candidate. It contains no world generator,
truth table, evaluator import, or lookup by world identity. Run it through
`sle eval --allow-uncertified --task Genomics/DiploidHaplotypeAssembly --candidate benchmarks/Biology/DiploidHaplotypeAssembly/references/reference.py`.
Measured development score: **1.00000000**; separate held-out
score/quality: **1.00000000**; validity: 1.0.
Full internal payloads are in `.research/biology_wave2_measurements_2026-09-05.json`.
These measurements are not frontier-model draws.

## 3. Ablations and shortcut probes

256 random phases achieved at most 0.106985; independent per-site majority voting scored 0.138633 on development world 0. Eight random starts gained 0.0 log-likelihood over the spectral reference on that world.

## 4. Frontier calibration and missing headroom

Read-level linkage matters, but the current spectral/local-search reference may already saturate this reduced panel. HapCUT2 comparison, correlated-error technologies and harder coverage shifts remain unimplemented.
No frontier draw, paired open-loop experiment, two-hour search or independent
expert sign-off has run. This package remains **candidate**. A high reference
score is not evidence that certification difficulty gates have passed.

## 5. Construction errors and corrections

Strict nested output types, numeric ranges, invalid query handling and permanent
budget-violation flags were implemented before registration. In geometry,
linear normalization against a very poor straight line rewarded poor shapes;
it was replaced by inverse-loss quality normalization before the recorded run.
Reference seeds are algorithm constants; truth is never supplied to the solver.
No data-dependent sample count or public world-type identifier is exposed by
the two discovery tasks. Internal checks do not replace external oracle review.

## 6. Robustness and held-out scope

`tests/test_biology_wave2.py` covers at least twelve malformed artifacts per
task, model invariants and cross-process baseline determinism. Discovery tests
also cover correct refusal and caught budget overruns. Held-out panels shift
instance size or parameters and are excluded from search feedback, but are
repository-visible procedural examples, not an untouched server-side split.

## 7. Provenance, novelty and review

Scientific motivation: HapCUT2: robust and accurate haplotype assembly for diverse sequencing technologies, doi:10.1101/gr.213462.116.
All implementation and synthetic instances are original to this contribution;
no third-party implementation or dataset is redistributed. Model reductions
and omissions are explicit in Task.md. Nearest existing tasks are listed there.
The second-wave implementation report records the fixed paper/repository
catalog comparison. External domain review, contamination-resistant server-held
worlds, overlap adjudication and strong-solver calibration remain open.
