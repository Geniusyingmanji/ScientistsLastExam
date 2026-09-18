# IsolationLevelAudit: which isolation level does this store implement, and can you tell yet?

## 关系与区别 / How this differs from the nearest tasks in this repository

- **`DataPrivacy/SparseVectorAudit`** is also a black-box audit of an implementation under a
  budget, with a refusal when the evidence does not reach. There the object is a differential
  privacy mechanism, the evidence is a statistical loss estimated from independent runs, and the
  budget buys samples. Here the object is a concurrency control, the evidence is a cycle in a
  dependency graph recovered from an observed history, and a run is a *schedule* the caller cannot
  control: the same batch is a real experiment only on the rare occasions when two transactions
  actually race, so the budget buys opportunities rather than samples.
- **`Algorithm/JuntaVariableDiscovery`** is also budgeted active querying with a calibrated
  refusal. There every query is an independent draw and the power of a negative result is a
  binomial margin the solver can compute in advance. Here the solver cannot compute its power in
  advance at all: whether a round was an experiment is only visible after the fact, in the
  operation clocks, and how many rounds it takes is a property of the world.
- **`ComputerArchitecture/CacheReplacementPolicyID`** also identifies which member of a fixed
  family a black box implements, from traces the solver designs. There every access returns a hit
  or a miss, so each probe is informative and the difficulty is the hidden state your own queries
  move and the noise on the channel. Here a probe that is built to separate two levels usually
  returns nothing at all, because the behaviour that separates them is a race that mostly does not
  happen, and the work is in deciding what nothing means.

No other task in this repository concerns transactions, isolation levels or concurrency anomalies.

## The question

A transactional store promises an isolation level. The promise is a claim about what it will never
do: a store at snapshot isolation will never lose an update, but it will allow write skew, and a
store at serializable will allow neither while still answering a read-only transaction from a
replica that has fallen behind real time. Deciding which promise a store actually keeps, from the
outside, is what Jepsen-style verification does, and the reason it is hard in practice is that a
production store takes its weak path rarely: the anomaly that separates two levels may not appear
at all in an afternoon of traffic.

You are given a black-box store and an operation budget. Run batches of concurrent transactions
against it, read the histories it returns, and name its isolation level, or decline. Declining is
the right answer when the budget did not buy enough real contention to rule out the level below
the one your evidence reaches.

## What makes it hard

- **An anomaly needs a race, and races are rare.** Most transactions take a global lock and run
  atomically. With a hidden probability, at least `min_weak_rate`, one takes the store's own
  concurrency control instead. The lock is not granted while any transaction is in flight, so a
  transaction on the weak path is never interrupted by one on the lock path: an anomaly needs
  *two* weak transactions at once, and its rate is quadratic in a number you cannot change.
- **Each class needs its own shape.** Write skew only appears between two writers whose write sets
  are disjoint and whose reads cross. A long fork only appears between two writes with no causal
  relation, observed by two sessions that each already hold one of them. A dirty write only
  appears between two writers touching the same keys in opposite orders. Traffic that does not
  build the shape never sees the class, and the level it would have named stays out of reach.
- **The history has to be reconstructed.** A read returns the whole list at a key, and the version
  order is whatever the longest list anyone saw says it is. Dependency edges, and the cycles that
  witness each class, come out of that reconstruction, not out of the store.
- **A quiet probe means two different things.** A round in which two weak transactions raced and
  nothing went wrong is evidence. A round in which no two weak transactions ever overlapped is
  not, and the anomaly counts look the same in both. The operation clocks tell them apart: a
  transaction on the lock path is never interrupted, so operations that interleave prove both
  transactions took the weak path.
- **Some worlds cannot be settled.** In six of the twelve development worlds the weak rate is low
  enough that the budget buys only a handful of real races, and the level below the one the
  evidence reaches cannot be ruled out. Naming a level there is usually a wrong answer, worth −1
  where declining is worth 0. Nothing in the public problem says which worlds are which, and a
  starved world is not a quiet one: classes stronger than the truth still fire there, so the
  evidence points somewhere, just not far enough down the ladder.

## What you implement

```python
def audit(problem, run):
    ...
    return {"level": "snapshot_isolation", "confidence": 0.8}
```

### `problem`: every key you are given

| key | meaning |
|---|---|
| `budget` | 9000; the number of operations you may run in this world |
| `levels` | the six levels, weakest first: `read_uncommitted`, `read_committed`, `parallel_snapshot`, `snapshot_isolation`, `serializable`, `strict_serializable` |
| `min_weak_rate` | 0.04; a lower bound on the hidden probability that a transaction takes the weak path |
| `max_sessions` | 4; the most sessions one batch may run |
| `max_ops_per_txn` | 8; the most operations one transaction may run |
| `max_ops_per_batch` | 400; the most operations one batch may run |
| `store_model`, `batch_model`, `answer_format` | prose: the model and the contract below |

### The model

- **The store.** Keys hold lists. `["a", k]` appends a globally unique element to key `k`;
  `["r", k]` returns the whole list at key `k`. The store implements exactly one of `levels`.
- **The two paths.** Most transactions take a global lock: they read the authoritative state, run
  with no other operation falling inside theirs, and the lock is not granted while anything is in
  flight. With a hidden probability, at least `min_weak_rate` and drawn afresh per transaction, a
  transaction takes the store's own concurrency control for its level instead.
- **Aborts.** Every transaction on either path may abort on its own at a fixed rate, so an abort
  does not say which path it took. A transaction on the weak path may also abort because its
  level's certification rejected it.

### `run(batch)`

`batch` is a list of sessions, each a list of transactions, each a list of operations, where an
operation is `["r", key]` or `["a", key]` and `key` is a non-negative integer. A session runs its
transactions in order; the engine picks the interleaving, so you choose the contention and never
the schedule. An empty session is allowed, so a batch can put its sessions at the indices you
want. A batch runs at most `max_sessions` sessions, each transaction between one and
`max_ops_per_txn` operations, and at most `max_ops_per_batch` operations in all.

It returns `{"transactions": [...]}`, one record per transaction that ran, in commit order:

| field | meaning |
|---|---|
| `tid` | a unique transaction id |
| `session` | the session index it ran in |
| `start`, `end` | the clock at which it began and at which it committed or aborted |
| `status` | `"committed"` or `"aborted"` |
| `ops` | what it did: `["r", key, [elements seen]]` or `["a", key, element]` |
| `at` | the clock of each operation, in order, aligned with `ops` |

Every clock is a distinct instant on one global timeline, so real time is a total order over
operations, begins and commits. A call that would run past `budget` operations in all raises and
the world scores −1, so count what you spend. A malformed batch raises.

### What you return

| key | meaning |
|---|---|
| `level` | one of `levels` |
| `confidence` | in `[0, 1]`; clipped |
| `abstain` | `True` declines; `level` may then be omitted |

Anything malformed scores that world −1, and so does a malformed call to `run`. It is never an
infrastructure failure.

## How you are scored

The oracle knows the level, which is fixed before you run and does not depend on what you do.

- Naming the level scores **+1**.
- Naming a different level scores **−1**.
- Declining scores **0**.

`combined_score` is the mean over the twelve development worlds, clipped below at zero, so
**declining every world scores exactly 0.0** and a fixed guess scores less than that. `confidence`
feeds only the calibration axis and cannot turn a wrong level into anything else.

Reported separately, never averaged into one number:

`development_identification_rate` · `development_misidentification_rate` ·
`development_refusal_rate` · `development_false_discovery_rate` ·
`development_correct_refusal_rate` · `development_discovery_coverage` ·
`development_confidence_calibration` · `development_mean_probes_used` ·
`development_raw_mechanism`

The false-discovery rate counts wrong levels against the worlds you actually named, not against
all of them, so declining costs you nothing there. The other two are read against what each world
could have supported: a refusal counts as correct only where the budget could not have settled the
world, and coverage is how much of what was settleable you went on to settle.

Each of those three travels with the count it is a rate of, under
`development_false_discovery_count` and `development_false_discovery_denominator` and the matching
pair for the other two. A rate on its own cannot be read, because a refusal rate of 1.0 is one
world out of one or six out of six.

A sealed held-out set of eight further worlds is scored too, under the same keys with the
`heldout_` prefix, and is not visible to a searcher. `per_instance` carries one row per world.

## Where the scale sits

The reference scores 0.500 on the development split and 0.625 held out. It names six of the twelve
development worlds correctly, declines six, and names no world wrongly. Over four seed shifts,
this draw and three re-drawn, it averages 0.542 on the development split and 0.656 held out and
makes no wrong call in 80 world-runs. It is not the ceiling: its refusal threshold is a fixed
per-level opportunity count read off measured exposure rates, not a posterior over the level given
the whole history, and it allocates its budget greedily by pattern cost rather than by
information. A solver that spends its whole budget on the one shape that separates the level it
actually suspects buys several times the opportunities a balanced sweep does, and can settle
worlds the reference declines.

The baseline in `solution.py` scores 0.000. It runs contention at two sessions and scans for the
two symptoms a reader can see without a dependency graph, a read of an element whose writer went
on to abort and a key whose list came back shorter than before. It never declines, and it gets ten
of the twelve development worlds wrong.

A probe of twelve low-effort strategies was scored on the same worlds. They answer blind, guess a
fixed level, read anomalies per key, read only the abort rates, spend the budget on undesigned
traffic, run the reference on a tenth of the budget, or run the full design and the full anomaly
analysis with the refusal replaced by something cheaper: never declining, declining only when
nothing fired at all, or measuring power in rounds instead of in races. The best of them reaches
0.167 on the development split, **33 per cent of the reference**, and it names four wrong levels
where the reference names none; every strategy that never makes a wrong call scores 0.000 by
declining everything.

## Rules

- Only edit `solution.py`; keep `audit(problem, run)`.
- NumPy, SciPy and the standard library only. Deterministic CPU code.
- `sle.contract_lint` is importable and free to call for shape checks. It costs no operation.
- Do not read `verification/` or `frontier_eval/`.
