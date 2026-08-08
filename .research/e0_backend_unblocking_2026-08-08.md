# E0 — why the evolutionary backends had never produced a data point

Date: 2026-08-08. Host: benchmark machine (Linux, bwrap 0.4.0, host Python 3.8.10).

`plan_gap_audit.md` lists "run nonzero-budget/checkpoint integration and multi-seed study" as
unchecked for all three optional backends, and the trust record shows only baseline smokes. A
scan of every report in `experiments/` confirms the scale of it: across 2822 recorded algorithm
invocations, **the only search algorithm ever run is `greedy_rewrite`**. OpenEvolve, ShinkaEvolve
and AB-MCTS appear zero times.

That is not merely an unrun experiment. Four independent blockers made these backends unable to
produce a valid result, and they are recorded here because each one is invisible from the host
default configuration. Two are fixed; two remain open and are backend-side.

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

## Blocker 2 — wire and parameter mismatch (harness side)

OpenEvolve 0.2.26 and ShinkaEvolve both reject anything but the OpenAI-compatible chat wire,
while the available GPT-5.6 proxy speaks the Responses wire. A chat-completions endpoint does
exist on this host on a different port, but the harness hardcoded `max_tokens`, which reasoning
models reject in favour of `max_completion_tokens`.

Fixed by making the chat max-tokens parameter name a declared config field, plus a chat-wire
config pointing at the chat endpoint.

## Blocker 3 — ShinkaEvolve builds its own request body (not fixed)

Fixing the harness's chat wire is not sufficient for ShinkaEvolve, because it does not use the
harness's LLM client. It constructs its own OpenAI request and hardcodes `max_tokens`, so against
a reasoning model it enters an unbounded retry loop:

```text
Local OpenAI - Retry 19 due to error: Error code: 400 -
  Unsupported parameter: 'max_tokens' is not supported with this model.
  Use 'max_completion_tokens' instead.  Waiting 16.7s...
```

The run was killed after 1772 s having made no progress. OpenEvolve is unaffected: it reaches the
same endpoint through a path that produces an acceptable body.

The clean remedy is a small translating proxy in front of the endpoint that rewrites
`max_tokens` to `max_completion_tokens` and drops unsupported `temperature` values. That would
also be the general fix for any external framework pinned to the older chat schema. It is
deliberately not done here: inserting a rewriting proxy into the experimental path is a
provenance change and should be declared rather than slipped in.

## Blocker 4 — AB-MCTS adapter bug (not fixed)

With the wire and package issues resolved, AB-MCTS still fails. It evaluates the baseline
successfully (`combined_score=0.000000 valid=True` on CirclePacking) and then raises inside
TreeQuest:

```text
self.action_probas[action].tell_observation(reward)
KeyError: 'baseline'
```

The adapter registers the baseline evaluation as an observation against an action key that the
bandit's action table does not contain. This is a genuine adapter defect and remains open.

## First nonzero-budget result — and what it says about the certified core

With blockers 1 and 2 resolved, OpenEvolve runs. Complete trajectory on
`Optimization/CirclePacking`, budget 20, seed 0, GPT-5.6 over the chat wire, 21 oracle calls in
1224 s, every step valid:

| step | 0 | 1 | 2 | 3 | 7 | 14 | 20 |
|---|---:|---:|---:|---:|---:|---:|---:|
| best-so-far | 0.0000 | 0.4606 | **0.9906** | 0.9978 | 0.9997 | 0.9999 | 0.9999 |

Island statistics appear in its log, so the population machinery is genuinely active rather than
degenerating to a single incumbent.

**The task is solved in three oracle calls.** The remaining seventeen evaluations buy 0.002. For
comparison, a GPT-5.6 budget-one draw scores 0.727 and the shipped baseline scores 0.

This is the most important thing E0 has produced so far, and it is a verdict on the inventory
rather than on the backend. `Optimization/CirclePacking` is one of the seven certified tasks, and
its instances are `N = 7, 10, 13` — sizes where the Packomania values are long settled and easy
to approach. Against a one-shot draw it looked like a discriminating task at 0.727; against an
actual population search it has no measurable difficulty at all.

Two consequences follow directly:

1. `CirclePacking` must move to larger `N`, where the best-known packings are still contested,
   before it is used to measure anything. The same applies to any task whose instances were sized
   against one-shot draws.
2. **No certified task has ever been exposed to a population-based search.** Every difficulty and
   discrimination claim in the current record was calibrated against `greedy_rewrite` at budget
   one to three. This result shows that calibration can be off by the entire scoring range.

## Claim boundary

This note records infrastructure repair and one smoke-scale observation. It is not a backend
comparison, not a multi-seed study, and not evidence about any model. The matched-seed
`greedy_rewrite` control at the same budget is required before any statement about which search
algorithm is better.
