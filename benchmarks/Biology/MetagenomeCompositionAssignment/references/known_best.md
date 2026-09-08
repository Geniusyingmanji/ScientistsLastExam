# MetagenomeCompositionAssignment: withdrawal after repair — 2026-09-08

## Status and measured repairs

Replaced the four fixed abundance values with continuous simplex draws (each
component exceeds the reporting threshold), varied the number of active taxa from
2 to 4, and varied the identifiable members in alias mixtures. Alias scoring now
handles all identifiable members rather than assuming t2 is the sole member.
FDR counts every world, including supported-world false claims. Alias resolution
and library refusal have separate rates and denominators; held-out uses the same
blanket-refusal normalization rule as development.

Before repair, reference + nearest {0.35,0.45,0.55,0.65} rounding scored
0.942 development / 1.0 held-out versus reference 0.694504257. After repair,
the unchanged reference scores 0.723821438 / 0.555464463 and rounding scores
0.620526320 / 0.537500000. Thus the confirmed fixed-abundance advantage is removed
on this panel; this is not a proof against all quantization probes.

The current public alias list and zero-weight sentinel marker still make two
scientific decisions lookup operations. There are only nine worlds. Repairing
those issues requires new panel-dependent identifiability and shared-marker
library-inadequacy models, followed by calibration. This family is withdrawn,
not claimed to satisfy the September 8 scientific requirements.

## Reproduction

```sh
OPENBLAS_NUM_THREADS=1 python -m pytest -q tests/test_metagenome_composition.py
python scripts/check_task_contribution.py --task Microbiology/MetagenomeCompositionAssignment --timeout 300
```

The dedicated regression suite reproduces the repaired contract. Scientific
shortcut comparisons are reported above and in the corresponding PR discussion;
they are not frontier-model calibration draws. `verification/reference_*.py`
is the input-only comparison. For parsimony, `verification/shortcut_probe.py`
and `verification/headroom_probe.py` provide the negative and search controls.

## Remaining evidence requirements

Software validity and deterministic repeats do not establish task difficulty.
The current instance family is withdrawn; baseline/reference tests check valid,
bounded execution, **not** the former 0.5–0.8 admission band. This test change
records a failed calibration rather than relaxing admission requirements.
No blind model draws, long-horizon calibration or external domain confirmation
were performed. Seeds are repository-visible; held-out means omitted from search
feedback, not secret. A replacement must document new instances, reachable
endpoints, all shortcut/ablation measurements and independent confirmation.

## History

The original measurements and the maintainer's September 8 findings remain in
[PR #39](https://github.com/Geniusyingmanji/ScientistsLastExam/pull/39).
The branch preserves the fixes and their regression tests for a future redesign;
closing the current PR does not assert that this scientific subject is unusable.
