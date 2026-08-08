# E0 — why the evolutionary backends had never produced a data point

Date: 2026-08-08. Host: benchmark machine (Linux, bwrap 0.4.0, host Python 3.8.10).

`plan_gap_audit.md` lists "run nonzero-budget/checkpoint integration and multi-seed study" as
unchecked for all three optional backends, and the trust record shows only baseline smokes. A
scan of every report in `experiments/` confirms the scale of it: across 2822 recorded algorithm
invocations, **the only search algorithm ever run is `greedy_rewrite`**. OpenEvolve, ShinkaEvolve
and AB-MCTS appear zero times.

That is not merely an unrun experiment. Three independent blockers made these backends unable to
produce a valid result, and they are recorded here because each one is invisible from the host
default configuration.

## Blocker 1 — the sandbox mounted no packages under any backend interpreter

Each backend runs the whole harness inside its own virtualenv. `_site_package_roots()` resolved
site-packages from `sys.version_info` of the *parent* process, while the sandbox execs a
`/usr/bin` interpreter chosen separately. On this host there is no `/usr/bin/python3.10` or
`/usr/bin/python3.12`, so the two disagreed:

| harness parent | candidate interpreter | site roots scanned | numpy/scipy mounted |
|---|---|---|---|
| host 3.8.10 | `/usr/bin/python3.8` | 3.8 roots | yes |
| OpenEvolve venv 3.10.20 | `/usr/bin/python3` (3.8) | 3.10 roots | **none** |
| AB-MCTS venv 3.12.13 | `/usr/bin/python3` (3.8) | 3.12 roots (absent) | **none** |

So under any backend, every candidate importing numpy failed as `blocked_or_missing_import`.
Even a correctly populated 3.10 tree would not have helped: mounting 3.10 C extensions into a
3.8 interpreter cannot work.

This also explains why the baseline smokes passed and hid the problem. The smoke evaluates each
task's shipped baseline, and the baselines it passed on need no third-party import at all —
`Mathematics/CirclePacking`'s baseline imports only `math`.

Fixed by resolving site-packages for the interpreter that will actually import them.

## Blocker 2 — wire and parameter mismatch

OpenEvolve 0.2.26 and ShinkaEvolve both reject anything but the OpenAI-compatible chat wire,
while the available GPT-5.6 proxy speaks the Responses wire. A chat-completions endpoint does
exist on this host on a different port, but the harness hardcoded `max_tokens`, which reasoning
models reject in favour of `max_completion_tokens`.

Fixed by making the chat max-tokens parameter name a declared config field, plus a chat-wire
config pointing at the chat endpoint.

## Blocker 3 — AB-MCTS adapter bug (not fixed)

With the wire and package issues resolved, AB-MCTS still fails. It evaluates the baseline
successfully (`combined_score=0.000000 valid=True` on CirclePacking) and then raises inside
TreeQuest:

```text
self.action_probas[action].tell_observation(reward)
KeyError: 'baseline'
```

The adapter registers the baseline evaluation as an observation against an action key that the
bandit's action table does not contain. This is a genuine adapter defect and remains open.

## First nonzero-budget result

With blockers 1 and 2 resolved, OpenEvolve runs. On `Optimization/CirclePacking` at budget 20 it
reaches `combined_score=0.9978` by its fourth checkpoint, against a shipped baseline of 0.0 and a
GPT-5.6 budget-one census score of 0.727. Island statistics appear in its log, so the population
machinery is genuinely active rather than degenerating to a single incumbent.

That single number carries a warning for the inventory. A certified task that a one-shot draw
leaves at 0.727 is essentially solved by a real evolutionary searcher in twenty evaluations. The
instances are too small: `CirclePacking` should move to larger `N`, where the Packomania records
are contested, before it is used to measure anything. The same question should be asked of every
certified task, because none of them has ever been exposed to a population-based search.

## Claim boundary

This note records infrastructure repair and one smoke-scale observation. It is not a backend
comparison, not a multi-seed study, and not evidence about any model. The matched-seed
`greedy_rewrite` control at the same budget is required before any statement about which search
algorithm is better.
