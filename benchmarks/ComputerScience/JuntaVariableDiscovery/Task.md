# JuntaVariableDiscovery: which variables does this function depend on, and is it even a small junta?

## 关系与区别 / How this differs from the nearest tasks in this repository

- **`Algorithm/GraphFromDistances`** sits in the same domain and is also a structure-recovery
  task run through queries. There the object is a graph and the queries return distances; the
  recovered structure is a set of edges. Here the object is a Boolean function, the queries return
  its noisy value at points you choose, and the recovered structure is the set of variables the
  function depends on. A distance query is informative on its own; a single value query is not,
  because a relevant variable can be invisible until it is flipped against a fixed background.
- **`CausalDiscovery/InterventionalSCM`** also asks which variables matter and lets you intervene.
  There the mechanism is a causal graph over continuous variables and the answer is its edges.
  Here there is no graph, only a function, and a variable can matter through a parity that leaves
  its marginal effect exactly zero, so an interventional correlation never reveals it.
- **`SignalProcessing/SparseRecovery`** recovers a sparse support too. There the map is linear and
  the support shows in the measurements directly. Here the map is a Boolean function and the
  support hides behind parities and gates that no linear read can see.

No other task in this repository concerns Boolean functions, juntas or membership queries.

## The question

A function of many inputs often depends on only a few of them. Finding which few, from queries to
the function, is the junta problem of computational learning theory. It is easy when every relevant
variable leaves a footprint in the output on its own. It is hard when a variable matters only
together with others. The parity of three bits depends on all three, yet flipping any one of them,
averaged over the rest, changes the answer exactly half the time whatever the others do, so the
variable's correlation with the output is zero. Only a query that flips it against an otherwise
fixed background reveals it.

You are given an unknown Boolean function of `n` variables. You may query its value at points you
choose, under a budget, and every answer is flipped independently with a published noise rate. Name
the variables the function depends on, or decline. Declining is the right answer when no junta of
the published size can explain the answers.

## What makes it hard

- **Relevant variables hide behind interaction.** Some relevant variables act only through a parity
  or a gate. Their single-variable correlation with the output is zero, so a method that reads
  correlations recovers none of them.
- **Some variables barely matter.** Seven of the twelve relevant variables are pivotal on about an
  eighth of the inputs, so their influence is near 0.12, and at this budget and noise rate they sit
  right at the edge of what the family-wise margin can certify above the noise.
- **Noise hides the signal.** Every answer is flipped with the published rate, so a variable's
  influence is read through a binomial haze. Naming an irrelevant variable is a false discovery and
  costs a world, so the margin must control the whole family of `n` candidates at once.
- **It may not be a junta.** In some worlds the function depends on more variables than any junta
  of the published size, and the right answer is to decline. The excess is spread over many
  variables and shows only when enough of them are tested.

There are twelve development worlds. In seven the function is a junta of the published size and in
five it is not. Nothing in the public problem says which worlds are which.

## What you implement

```python
def identify(problem, query):
    ...
    return {"verdict": "junta",
            "relevant": [2, 7, 9, 13, 18, 21, 22, 24, 25, 26, 4, 11],
            "confidence": 0.7}
```

### `problem`: every key you are given

| key | meaning |
|---|---|
| `n` | the number of variables, 28; they are indexed 0 to n-1 |
| `max_junta_size` | the largest junta you may name, 12; decline if no junta this small explains the answers |
| `noise_rate` | 0.10; every answer is flipped independently with this probability |
| `budget` | 20000; the number of answers you may draw in this world |
| `function_model`, `query_model`, `answer_format` | prose: the model and the contract below |

### The model

- **The function.** An unknown Boolean function f of the n variables. It depends on an unknown
  subset of them, its relevant set. A variable is relevant when flipping it changes f on a positive
  fraction of inputs.
- **The queries.** `query(points)` returns f at each row of `points`, and flips each answer
  independently with probability `noise_rate`.

### `query(points)`

`query(points)` takes a `k x n` array of 0/1 bits, one point per row, and returns a length-k array
of labels in `{0, 1}`, each the function's value at that point flipped independently with
probability `noise_rate`. It charges `k` against the budget. A call that would draw past `budget`
answers in all raises, and the world scores zero, so count what you spend. `k` must be at least one
and every entry must be 0 or 1.

### What you return

| key | meaning |
|---|---|
| `verdict` | `"junta"` or `"no_junta"` |
| `relevant` | required for a junta: the variables the function depends on, integers in 0..n-1, at most `max_junta_size` of them, each named once |
| `confidence` | in `[0, 1]`; clipped |
| `abstain` | `True` is accepted as a synonym for the no_junta verdict |

Anything malformed scores that world zero, and so does a malformed call to `query`. It is never an
infrastructure failure.

## How you are scored

The oracle knows the function and its true relevant set R. A variable is relevant exactly when
flipping it changes the function on a positive fraction of inputs, so R and each variable's
influence are functions of the world alone.

- **A world that is a junta of the published size.** A named set that is a subset of R scores the
  fraction of R it recovers, its recall. Declining scores 0. If it names any variable outside R,
  the answer is a false discovery and scores -1.
- **A world that is not a junta of the published size.** Declining scores 1 and is a correct
  refusal. Any named set is a false discovery and scores 0.

A false discovery therefore costs one world wherever it is made. `combined_score` is the mean over
the development worlds, renormalised so that **declining every world scores exactly 0.0**. Negative
values clip to 0. `confidence` feeds only the calibration axis and cannot turn a false discovery
into anything else.

Reported separately, never averaged into one number:

`development_interval_sharpness` (the mean recall over the junta worlds) ·
`development_false_discovery_rate` · `development_correct_refusal_rate` ·
`development_discovery_coverage` · `development_confidence_calibration` ·
`development_mean_probes_used` · `development_raw_mechanism`

A sealed held-out set of six further worlds, four juntas and two not, is scored too, under the same
keys with the `heldout_` prefix, and is not visible to a searcher. `per_instance` carries one row
per world.

## Where the scale sits

The reference scores 0.548 on the development split and 0.604 held out. It declines every world
that is not a junta of the published size and makes no false discovery. Over twelve seeds for the
label noise, this one and eleven re-drawn, it averages 0.545 on the development split and 0.573
held out and makes no false discovery in 216 world-runs. It recovers 0.42 to 0.75 of the relevant
variables in the junta worlds; the weakest of them sit at the edge of what the budget can certify
at a family-wise error rate.

The baseline in `solution.py` scores 0.000. It is degree-one correlation: one random point per
query, each variable's correlation with the answer, a family-wise margin from zero. It recovers no
variable that acts through a parity or a gate, and it never declines a big parity, so it makes a
false discovery in seven of the eighteen worlds. Declining everything scores 0.000, and so does
naming all twelve variables everywhere or a random twelve everywhere.

A probe of ten low-effort strategies was scored on the same worlds. They answer blind, read
degree-one correlations at several margins, run the pivotal test without the refusal, or run it with
a hand-set floor margin or with correlation for the claims and a pivotal pass only for the refusal.
The best of them reaches 0.333 on the development split, 61 per cent of the reference, and it makes
false discoveries; every strategy that makes none scores zero by declining everything.

## Rules

- Only edit `solution.py`; keep `identify(problem, query)`.
- NumPy, SciPy and the standard library only. Deterministic CPU code.
- `sle.contract_lint` is importable and free to call for shape checks. It costs no query.
- Do not read `verification/` or `frontier_eval/`.
