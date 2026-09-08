# SortingNetworkSize — bounds, methods and unresolved reference

## 1. Reference status and sources

**There is no qualifying independent reference yet.** `verification/reference_search.py`
is a standalone, deterministic search probe that reads no data files, imports no
evaluator and spawns no processes. It generates the baseline, prepends randomized
comparator prefixes, exactly deletes redundant comparators and retains improvements.
The 300-trial budget per n returns 48/53/59/63/74, for **0.016667**. This does not
satisfy the requested competent-reference standard. It must not be substituted for
a capability-complete 0.3–0.8 witness by changing the scale.

`verification/reference_reconstruction.py` is only an attributed **lookup probe**.
It reads five published gate lists, pinned to SorterHunter commit
`392762f916688756242d90febced98ad157bc6d2`. Exact URLs/hashes and the original MIT
notice remain in `reference_sources.json` and `SorterHunter-LICENSE.txt`.

The [record compilation](https://bertdobbelaere.github.io/sorting_networks.html)
reports sizes 45/51/56/60/71 and bounds 44/48/53/57/63. Its 2025-04-21 lower-bound
update credits Jelmer Firet using Van Voorhis principles; that proof is external
and has not been independently formalized here. The recorded page revision date
2025-11-07 and retrieval date 2026-09-08 are separate fields in anchors.json.

[Harder, arXiv:2012.04400](https://arxiv.org/abs/2012.04400) establishes S(11)=35
and S(12)=39 and supplies the Van Voorhis recurrence used by the conservative
cross-check. It yields 43/47/51/55/60, weaker than the scored bounds.
[Valsalam–Miikkulainen, JMLR 14 (2013)](https://jmlr.org/papers/v14/valsalam13a.html)
is the constructive n=17 source and discusses Juillé's n=13 history. The compilation
credits Green's n=16 construction to 1969. Bundala–Závodný's optimal-depth paper is
not a size-bound source and has been removed from the certification citations.

## 2. Baseline, target and aggregate validity

The baseline tries every contiguous window of real wires in a power-of-two Batcher
network, with negative sentinels before and positive sentinels after the window.
Each candidate is pruned by exact deletion to a fixed point. Choose minimum size,
then lexicographic gate sequence, deterministically. The evaluator reconstructs it;
no stored gate list defines the zero anchor.

| n | zero anchor B | published U | cited bound L | lookup score |
|---|---:|---:|---:|---:|
| 13 | 48 | 45 | 44 | 0.750000 |
| 14 | 53 | 51 | 48 | 0.400000 |
| 15 | 59 | 56 | 53 | 0.500000 |
| 16 | 63 | 60 | 57 | 0.500000 |
| 17 | 75 | 71 | 63 | 0.333333 |

The revised lookup mean is **0.496667**, not the former 0.557273. The latter used
B(17)=85. Scores across these oracle revisions are not directly comparable.

The scale remains `clip((B-size)/(B-L),0,1)`. All five networks must be valid;
otherwise combined_score is zero and raw_score is -1e18. Valid raw_score is minus
mean size. Feasibility and reasons preserve partial failures without awarding them
aggregate credit. A verified network below L additionally reports
`bound_contradiction=1` and a top-level `audit_required` diagnostic.

The target is mathematical, not an attained record. Unlike MiplibPrimalIncumbent,
whose proved optimal objective has a feasible witness, these lower bounds may be
unattainable. This distinction is explicitly disclosed; no admission exception has
been granted and no unused score interval is claimed as measured headroom.

## 3. Capability comparisons

Current deterministic method diagnostics:

| method | sizes n=13..17 | combined |
|---|---|---:|
| baseline / zero search trials | 48/53/59/63/75 | 0.000000 |
| 300-trial independent prefix search | 48/53/59/63/74 | 0.016667 |
| same search without uphill acceptance | 48/53/59/63/74 | 0.016667 |
| attributed lookup, not a search reference | 45/51/56/60/71 | 0.496667 |

Upward acceptance has no measured benefit on these instances. These results are
not a qualifying capability ladder: the large gap to lookup remains unresolved.
Candidate examples and search outputs were not substituted with published tables.
The probe is a single-file candidate suitable for the real sandbox runner.

## 4. Shortcut probes and negative results

`verification/shortcut_probes.py` recomputes these data-free families:

| family | sizes n=13..17 | current score |
|---|---|---:|
| original Batcher | 48/53/59/63/85 | 0 |
| contiguous offset grid | 48/53/59/63/81 | 0 |
| Batcher plus exact redundant-gate deletion | 48/53/59/63/79 | 0 |
| offset grid plus deletion (new baseline) | 48/53/59/63/75 | 0 |
| insertion sort | 78/91/105/120/136 | 0 |

The [maintainer's September 8 review](https://github.com/Geniusyingmanji/ScientistsLastExam/pull/57#issuecomment-5583948810)
reports Bose–Nelson 50/55/61/65/81 (also zero on the new scale) and two negative
hill-climb experiments: n=13 target 47, 150 seconds / 2,475,443 evaluations; n=17
target 78, 240 seconds / 325,807 evaluations. These are attributed reviewer results,
not independently replayed experiments. They do not prove no better search exists.

Additional local explorations on September 8 found no n=13 improvement in a
5,000,000-step valid-mutation walk, a 5,000,000-step walk from a greedily generated
network, or a 3,000,000-step counterexample-guided annealing probe. A 600-trial greedy
suffix completion stayed at 48 gates for n=13 and 63 for n=16. These unsuccessful
explorations are not frozen/model calibration evidence and do not justify admission.
The bounded executable prefix probe above is the reproducible positive search result.

A further local n=13 greedy multistart experiment used seeds 0 through 1999,
starting with adjacent comparators and repeatedly minimizing the number of distinct
Boolean output patterns with random tie-breaking, then exact deletion. Its best
result was 48 gates (first reached at seed 169), in 106.06 seconds on the development
machine. This is another negative method diagnostic, not a new reference or a
two-hour headroom measurement.

## 5. Frontier-model draw

Not run. No current calibration IDs, clean first-proposal comparison, formal freeze,
or two-hour headroom evidence are claimed. Both the competitive reference and model
calibration remain pending; the task remains candidate and admission is still blocked.

## 6. Construction errors and corrections

The revised zero anchor removes n=17's ten easily removable gates. Partial-invalid
submissions now have no aggregate credit; invalid raw scores cannot outrank valid
networks. List/tuple lengths are checked before copying. Other iterables are bounded
for direct diagnostics, while the actual RPC boundary rejects generators already.
Tests exercise a valid n=13 paired with four invalid outputs, an oversized list
that cannot be iterated, and a synthetic contradictory bound with a verified sorter.

The candidate-visible Task.md contains only the B/L table needed for scoring; the
published sizes, witness scores, names and record-page pointers are here instead.
Nearest-neighbor descriptions now refer to existing registered tasks.

## 7. Robustness and reproduction

The exact checker is cross-checked against an independent Boolean simulator.
Tests cover baseline reconstruction, licensed asset hashes, valid numeric formats,
malformed and partial submissions, target semantics and deterministic evaluation.
The evaluator itself uses only the Python standard library. Numeric abstract base
classes preserve support for NumPy integer and floating-point candidate arrays;
the format tests include float32 and float64 arrays. A separate `python -S` run
verifies that the evaluator imports and scores the baseline without site packages.

```sh
python -m pytest tests/test_sortingnetworksize.py -q
python benchmarks/ComputerScience/SortingNetworkSize/verification/diagnose.py /tmp/sorting-probes.json
python benchmarks/ComputerScience/SortingNetworkSize/frontier_eval/run_eval.py \
  --candidate benchmarks/ComputerScience/SortingNetworkSize/verification/reference_search.py \
  --metrics-out /tmp/sorting-search.json
```

Export the lookup only when explicitly testing that shortcut, retaining attribution:

```sh
python benchmarks/ComputerScience/SortingNetworkSize/verification/reference_reconstruction.py \
  --export /tmp/sorting-lookup.py
```

See `frontier_overlap.md` for the source inventories. All tasks remain candidates;
ordinary diagnostics do not replace independent algorithms review or calibration.
