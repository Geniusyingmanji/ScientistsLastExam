# Next task candidates, after 74 (2026-09-06)

Empty discipline × cell pairs, and what could fill them. Written after three tasks landed in one
sitting so the next one starts from a decision rather than from a survey.

## What is already spoken for

Seven open PRs propose 44 tasks. #9 alone covers Chemistry × formula/structure/evidence,
EarthScience × structure, and several Engineering cells; #13 covers most of Biology. Building into
those cells now would duplicate contributor work and violate the non-overlap standard this
repository asks of contributors. The cells below are the ones no open PR touches.

## Ranked candidates

| cell | candidate | why it stays hard | verifier | risk |
|---|---|---|---|---|
| Engineering × formula | discover a turbulence wall-closure from budgeted flow data, refusing when no closure in the family fits | data-driven closure discovery is an active field and the refusal case - no closure of the assumed form - is the honest outcome nobody publishes | frozen 1-D boundary-layer solver, symbolic form scored on held-out Reynolds numbers | needs a solver; medium build |
| Mathematics × evidence | decide what a body of *computational* evidence supports about an open conjecture, given verified ranges and heuristic counts | this is the actual epistemics of experimental mathematics, and the refusal world - evidence consistent with both outcomes - is real | exact, since the verified ranges are given | scoring the decision rather than the number needs care |
| ComputerScience × evidence | given profiling data across input sizes, decide which complexity class is supported and when the data cannot distinguish two adjacent classes | adjacent classes are genuinely indistinguishable over a bounded range of n; this is why empirical complexity claims are contested | exact: the generator knows the class | close to #9's Algorithm/ScalingLawIdentification - check overlap first |
| Engineering × combinatorial | MIPLIB open instances, scored by the official solution checker | 217 instances are open; the checker is authoritative | official checker | needs external instance files, and instance selection must avoid ones that are seconds-solvable |
| Physics × molecular_design | the only cell Physics lacks | — | — | low priority; molecular_design already has 5 |

## Recommendation

**Engineering × formula** first. Engineering has 16 tasks and every one of them is
`engineering_design`; it is the most lopsided discipline in the inventory, and a discovery task
there changes what the benchmark can say about that discipline rather than adding to a pile.

**Mathematics × evidence** second, and it is the more interesting of the two: this repository has
fourteen Mathematics tasks that are all record-chasing constructions plus two certificate tasks, and
nothing that asks what a body of evidence *supports*. The refusal axis is the whole point - the
honest answer to most computational evidence about an open conjecture is that it is consistent with
both outcomes.

## Standing constraints, learned the hard way

- Build the package **outside** `benchmarks/` until it is complete: `sle.registry` discovers any
  directory there and a missing `frontier_eval/metadata.yaml` makes `list_tasks` raise, which
  turned into 37 failures and 60 errors across tests unrelated to the new task.
- `review.domain` must hold the pending marker (`pending_external_<field>`), not a real field name;
  `scripts/audit_benchmark_standards.py` reads it to count external sign-offs.
- Chinese briefs in `scripts/report_task_inventory.py` are markdown table cells and cannot contain
  a pipe.
- Never seed randomness from `hash()`. Python randomises string hashing per process, and the same
  reference scored 0.4231 and 0.2092 in two interpreters before this was caught.
- Discovery tasks must report `mechanism_score`, `false_discovery_rate`, `correct_refusal_rate` and
  `discovery_coverage` under exactly those names, with denominators; the cross-task tooling looks
  for them.

## Design sketch for Mathematics × evidence

The phenomenon: a conjecture can hold for hundreds of millions of cases and then fail. Pólya's
conjecture is the canonical instance — least counterexample 906,150,257 — and Mertens' is worse.
The scientific point is that **absence of a counterexample in a searched range is not evidence of
truth** when the family is known to admit late failures, and the honest verdict is usually neither
"holds" nor "fails".

A first design made the task degenerate: if the only ways to answer are "found a counterexample" or
"searched and found none", then "undecided" is always right in the absence of a find, and the task
collapses to a search. The fix is to make **"holds" earn its keep**: some instances carry a
checkable algebraic reason why the predicate holds for all `n`, and the searcher must produce it.
Three verdicts then correspond to three genuinely different epistemic states:

| verdict | what the searcher must supply | when it is correct |
|---|---|---|
| `holds` | a certificate the frozen checker verifies | the identity really does imply it |
| `fails` | an explicit `n` the checker evaluates | a counterexample exists within reach |
| `undecided` | nothing | no certificate exists and the least counterexample is out of budget |

Scored on the usual triple, with naming a counterexample that does not check, or asserting `holds`
without a valid certificate, both counting as false discoveries. Verification is exact and cheap
in every branch, which is what makes the refusal axis trustworthy rather than a matter of taste.

Build order: this one before the turbulence closure, because it needs no solver and its verifier is
exact in all three branches.
