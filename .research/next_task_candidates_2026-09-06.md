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
