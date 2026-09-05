# BellBoundCertificate — prove an upper bound, do not just compute one

## Scientific setting

Two parties measure a shared quantum system. Each picks one of a few settings and reads out a
`+1`/`-1` outcome. A **Bell functional** is a fixed linear combination of the resulting
correlators, and the question is how large it can be made over *all* quantum states and *all*
measurements — not just the ones anyone has thought of.

For CHSH the answer has been known since 1980: `2*sqrt(2)`. For `I3322`, the next inequality up and
the simplest one beyond CHSH, it is not known. The Navascués–Pironio–Acín hierarchy gives a
decreasing sequence of upper bounds — level 1 gives `0.375`, level 2 gives `0.25102173`, and the
best value anyone has reached, at level 4 or higher, is `0.25087538` — but the sequence is not
known to terminate, and the supremum is now known not to be attained in any finite dimension
(arXiv:2608.29734). Every level costs combinatorially more than the last.

## What is scored

Not a number. **An argument.**

A certificate for the bound `beta` is a sum-of-squares decomposition of the operator `beta*I - B`:

```
beta * I - B  =  sum_k  w_k * (v_k . u)^dagger (v_k . u),      w_k >= 0
```

where `u` is a vector of words in the observables that you choose. Any such object proves
`<B> <= beta` for every state and every measurement, because the right-hand side is a sum of
squares and its expectation cannot be negative. Nothing about how you found it matters. What is
scored is `beta`.

Three things make this a research problem rather than a solver call.

**The certificate must be exact.** Weights and vector entries are integers or `[numerator,
denominator]` pairs. The operator identity is checked in exact rational arithmetic, with no
tolerance anywhere. A floating-point SDP solution is *not* a certificate: submitting floats is
rejected rather than rounded, because rounding a boundary point out of the positive-semidefinite
cone is precisely the difficulty being measured. Turning a numerical solution into a proof — and
repairing the feasibility that rounding destroys, without paying for it in the bound — is the work.

**The basis is yours to choose.** Each instance caps how many words the certificate may use.
Which words to spend the budget on is open: arXiv:2607.14755 enumerates all `2^21` subsets of the
level-2 moments for `I3322` and reports a non-monotone landscape with real synergy between
moments, so the greedy "take the shortest words" basis is known not to be optimal.

**The relaxation is not tight.** That is why this cell exists. A sibling task in this repository
was cut after measurement showed the standard relaxation already equalled the published bounds —
for binary codes the Delsarte linear program essentially *is* the upper bound, so a certificate
task there would have measured whether a candidate can call `scipy.optimize.linprog`. Here the
gap between what a small exact certificate proves and what is true is the whole scale of the task.

## Instances

| instance | scenario | budget | free bound (level 1) | published target | best known value |
|---|---|---|---|---|---|
| `chsh` | 2 settings each | 24 words | 4 (algebraic) | `2*sqrt(2)` | `2*sqrt(2)`, exactly |
| `i3322_k12` | 3 settings each | 12 words | 0.37500001 | 0.25102173 | 0.25087538 |
| `i3322_k24` | 3 settings each | 24 words | 0.37500001 | 0.25102173 | 0.25087538 |
| `i3322_k40` | 3 settings each | 40 words | 0.37500001 | 0.25102173 | 0.25087538 |

`chsh` is the rung that guarantees a competent submission has somewhere to stand. Its optimum is
irrational, so no rational certificate attains it and the score is how closely you come.

## Scoring

Uncapped, and logarithmic in the distance to the best known quantum value:

```
score = ( log10(free_gap) - log10(your_gap) ) / ( log10(free_gap) - log10(target_gap) )
```

clipped below at zero. The free level-1 bound scores 0, the published target scores 1, and beating
it scores more. The log is not decoration: on a linear scale the level-1 relaxation for `I3322`
would already score 0.93 and level 2 would score 1.00, with the entire open region between them
indistinguishable. Halving the remaining gap is worth the same wherever it happens.

A certificate proving a bound *below* the best known quantum value would contradict an explicit
published strategy. That case is reported as `below_best_known_quantum_value` and scored zero
rather than rewarded: it is either a defect in this checker or a result, and neither is a number to
average into a mean.

## Contract

Implement `build_certificate(instance)`. It is called once per instance and must return

```python
{"basis":   [[[a_letters], [b_letters]], ...],
 "squares": [{"weight": [num, den], "vector": [[num, den], ...]}, ...]}
```

`instance` carries these keys, all public:

| key | meaning |
|---|---|
| `name` | which instance this is |
| `settings` | how many measurement settings each party has |
| `functional` | the Bell functional, as `{word: integer coefficient}` |
| `scale`, `offset` | the reported bound is `(identity coefficient + offset) / scale` |
| `max_basis` | the budget: how many basis words the certificate may use |
| `max_squares` | how many squares the certificate may contain |
| `max_word_letters` | the letter cap per side of a word |
| `max_numerator`, `max_denominator` | magnitude caps on every rational entry |
| `free_bound` | what the level-1 relaxation proves; the zero of the scale |
| `published_target_bound` | the best published bound; worth 1 |
| `best_known_quantum_value` | the value the score measures distance to |

Words must be reduced (`A_x A_x` is the identity, so it is not a word), distinct,
and within the letter cap; weights must be non-negative; every vector has one entry per basis word.
Submission shape is checked by `sle.contract_lint` before scoring, and a submission that raises,
returns the wrong shape, or returns a certificate whose identity fails scores zero on that instance
without disturbing the others.

## Relation to the rest of this benchmark

`Mathematics/NonlinearCodeRecords`, `Mathematics/CapSet` and `Mathematics/KissingNumber` are
open-record *constructions*: the product is an object and the verifier counts it. This is the first
task here whose product is a verifiable argument and whose score is the strength of what the
argument proves. No task in the Frontier-Eng catalogue (47 tasks in the paper appendix, 95 entries
in its `TASK_DETAILS`) concerns Bell inequalities, semidefinite relaxations or certificate
extraction; its quantum cell is circuit and control design.
