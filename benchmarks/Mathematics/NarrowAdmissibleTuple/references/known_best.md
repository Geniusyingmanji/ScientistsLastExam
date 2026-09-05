# NarrowAdmissibleTuple — reference results and anchor confidence

Every score below is produced by running code in this directory.

## Reproducing

```
python3 frontier_eval/run_eval.py --candidate solution.py --metrics-out /tmp/baseline.json
python3 frontier_eval/run_eval.py --candidate verification/reference_construction.py --metrics-out /tmp/reference.json
```

## The k=50 anchor (high confidence, primary source)

Polymath8b's own retrospective paper states directly: "the bound on H₁ had been lowered
unconditionally to 246" (D.H.J. Polymath, "The 'bounded gaps between primes' Polymath project — a
retrospective," arXiv:1409.8361, fetched and quoted directly during this task's construction).
246 is the diameter of the admissible 50-tuple used to establish this. This is the number this
task uses for `k=50`.

**A caveat, disclosed rather than hidden**: some secondary tracking sources (search-engine
summaries of the narrow-admissible-tuples project, which continued past 2014) reported an
improved value of 242 for k=50. This task could not independently confirm 242 against a primary
source during construction, and the two search attempts made returned inconsistent numbers (one
said 242 was optimal, another repeated 246 as the minimal diameter). Rather than picking one on
uncertain grounds, this task anchors `k=50` on the number directly quoted from Polymath8b's own
paper (246), which is unambiguous. If 242 (or better) is in fact achievable, a candidate is free
to find and submit it — the oracle checks the literal submitted integers, not a recalled number,
so this task is not broken by that possibility either way.

## The k=54 anchor (moderate confidence, not independently primary-source verified)

Multiple secondary search results consistently reported `H(54) = 270`, but this task's
construction did not manage to fetch a primary source that states it directly (the way the k=50
figure was confirmed from arXiv:1409.8361's own text). This is disclosed rather than asserted with
unearned confidence. If 270 is wrong, the practical effect is limited: the oracle only uses it as
the `score = 1.0` witness for `k=54`, and `combined_score` is a mean over `k=50` (well-confirmed)
and `k=54` — a wrong `k=54` anchor would shift how generous or strict that one term is, not
invalidate the admissibility check itself, which is exact regardless of which diameter is used as
the reference point.

## Baseline — `solution.py`

Avoids residue 0 mod every prime `p <= k`, takes the first such non-negative integers.

| k | diameter | score |
|---|---|---|
| 50 | 310 | 0.0000 |
| 54 | 346 | 0.0000 |

Always admissible by construction (residue 0 is never used for any prime, so no prime's residues
can cover all its classes), but wasteful: diameter is roughly 25-30% larger than the published
records.

## Reference — `verification/reference_construction.py`

Sieves a symmetric window, greedily removing the least-populated residue class per prime, with 25
randomized restarts (tie-breaking and prime order) keeping the tightest surviving window.

| k | diameter | score |
|---|---|---|
| 50 | 284 | 0.4063 |
| 54 | 312 | 0.4474 |

`combined_score = 0.4268`. This is a real, standard sieve construction — not an exhaustive search
— and it does not reach the true optimum: real headroom is left for better tie-breaking, a
different prime processing order, or a local-search pass that swaps individual elements after the
greedy construction to shrink the diameter further. Runtime for both sizes together is well under
one second, so a "hard"/flagship-tier CPU budget leaves enormous room for a more thorough search
than this reference attempts.

## What this task is not

This task scores the exact, finite, self-contained combinatorial object (an admissible k-tuple and
its diameter). It does not ask for, and does not check, the analytic sieve-theoretic argument
(Bombieri-Vinogradov-type level of distribution, Maynard-Tao sieve weights) that turns "there is
an admissible k-tuple of diameter D" into a proved theorem about prime gaps — that chain of
reasoning is a fixed, already-published mathematical fact this task takes as given, not something
a candidate re-derives or that this oracle re-checks.
