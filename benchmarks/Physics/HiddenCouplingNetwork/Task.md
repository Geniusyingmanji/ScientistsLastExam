# HiddenCouplingNetwork

## The question

A network of `units` observed units relaxes to a steady state under constant drive. Each unit
decays at its own rate and receives saturating input from the units coupled into it:

```text
gamma_i * x_i  =  sum_j A_ij * tanh(x_j)  +  u_i        (steady state)
```

You choose the drive vector `u` for each experiment - any pattern over the observed units within
the amplitude bound - and read the noisy steady state of every observed unit. The budget is
**fewer experiments than there are units**. Which units are directly coupled to which, with what
sign - or is the direct graph among the observed units not identifiable from these units at all?

## Three traps

- **Indirect paths look like edges.** A drive at `j` moves every unit downstream of `j`. Reading
  "responds to `j`" as "coupled to `j`" books the whole transitive closure. The direct structure
  is the sparse solution of the steady-state equation, not the pattern of responses.
- **The equation is linear in `tanh(x_j)`, not in `x_j`.** Regressing on `x_j` is fine at small
  amplitude and biased at the amplitude a good signal-to-noise ratio wants; the bias shows up as
  weak extra edges.
- **A hidden unit looks like a dense graph.** Some networks contain one unit that is never
  measured and never driven, weakly coupled into and out of the observed ones. Its effect is a
  dense, low-rank coupling that no sparse direct graph explains. A dense regression fits it
  perfectly and produces a confident, wrong graph. The tell: several observed units leave a
  sparse-fit residual above the noise floor at once. One unit that does is a hard fit, not
  evidence. The honest answer, when enough of them do, is to decline.

A network with **no couplings at all is not the hidden case**: its steady state is diagonal and
"no edges" is a claim the evidence supports. Declining there is a missed discovery.

## Where the budget actually goes

With `experiment_budget` at two thirds of `units`, driving one unit per experiment cannot even touch most of them.
But every experiment yields one equation per unit - the row `x_i = sum_j (A_ij/gamma_i) tanh(x_j)
+ u_i/gamma_i` holds for all `i` simultaneously - so the real question is which drive patterns make
those equations identify a sparse row of at most `max_in_degree` couplings plus the unit's own
decay. Multi-unit drives buy identifiability and excite hidden paths; single-unit drives buy
clean regressions and hide them. The design is the decision.

## What you implement

```python
def discover_couplings(problem, run_experiment):
    ...
    return {"edges": [[source, target, sign], ...], "confidence": ..., "abstain": False}
```

### `problem` - every key you are given

| key | meaning |
|---|---|
| `units` | number of observed units, indexed `0..units-1` (12 in development) |
| `experiment_budget` | how many experiments you may run on this network (8 in development) |
| `drive_bound` | every drive entry must lie in `[-drive_bound, drive_bound]` (1.0) |
| `noise_sigma` | Gaussian noise on each reported steady-state value (0.02) |
| `max_in_degree` | no observed unit has more than this many direct inputs from other units (4) |
| `coupling_weight_range` | `[0.35, 0.8]`: magnitude range of every nonzero `A_ij` |
| `decay_rate_range` | `[0.9, 1.4]`: range of every `gamma_i` |
| `max_claimed_edges_per_unit` | at most this many edges per unit may be claimed in total (4) |
| `dynamics` | prose: the steady-state relation above |
| `hidden_unit_model` | prose: how unmeasured units enter |
| `abstain_when` | prose: when the direct graph is not identifiable |

### `run_experiment(drive)`

Charges one experiment. `drive` must have one finite entry per observed unit inside
`[-drive_bound, drive_bound]`; the call returns a list of `units` floats, the noisy steady state.
Calling past the budget raises and the network scores zero, so count your calls. Noise is
re-drawn per call, so repeating a drive averages noise and costs budget.

### What you return

| key | meaning |
|---|---|
| `edges` | list of `[source, target, sign]`: unit `source` is coupled into unit `target` with `sign` in `{-1, +1}`; `[]` claims there are no couplings |
| `confidence` | in `[0, 1]`; clipped |
| `abstain` | `True` to decline: the direct graph among the observed units is not identifiable |

Endpoints must be distinct observed indices, no `(source, target)` pair may repeat, and at most
`max_claimed_edges_per_unit * units` edges may be claimed. Anything malformed scores that network
zero. It is never an infrastructure failure. `sle.contract_lint` is importable and free to call
for shape checks; it costs no experiment.

## How you are scored

Each network contributes a mechanism score:

- **fully observed, coupled**: the signed-edge F1 of your claim against the true direct graph
  (an edge counts only with the right sign). Declining scores 0.
- **fully observed, uncoupled**: `[]` scores 1; any claimed edge scores 0 and is a false
  discovery; declining scores 0.
- **hidden units present**: declining scores 1; publishing a graph scores 0 and is a false
  discovery.

`combined_score` is the mean of those over the development networks, renormalised so that
**declining every network scores exactly 0.0**. Publishing the empty graph everywhere also scores
0.0.

Reported separately, never averaged into one number:

`edge_f1` · `false_edge_rate` (claimed edges that do not exist or have the wrong sign) ·
`false_discovery_rate` · `null_false_discovery_rate` · `correct_refusal_rate` ·
`discovery_coverage` · `confidence_calibration`

A sealed held-out set of eight larger networks (16 units, 10 experiments) is scored too and is
not visible to a searcher.

## What each competence is worth

Ablating the reference - one choice changed at a time:

| strategy | score | edge F1 | false edges | false discovery | refusal | coverage | held out |
|---|---|---|---|---|---|---|---|
| Rademacher multi-unit design + sparse regression on tanh(x) + noise-floor refusal | **0.445** | 0.22 | 0.47 | 0.00 | 1.00 | 0.57 | 0.358 |
| same, never declining | 0.258 | 0.56 | 0.45 | 1.00 | 0.00 | 1.00 | 0.224 |
| same, regressing on x instead of tanh(x) | 0.303 | 0.22 | 0.47 | 0.33 | 0.67 | 0.57 | 0.200 |
| same regression, single-unit drives | 0.227 | 0.72 | 0.25 | 1.00 | 0.00 | 1.00 | 0.000 |
| dense least squares on the raw states, never declining | 0.000 | 0.39 | 0.77 | 1.00 | 0.00 | 1.00 | 0.000 |
| declining everything | 0.000 | - | 0.00 | 0.00 | 1.00 | 0.00 | 0.000 |
| empty graph everywhere | 0.000 | - | 0.00 | 1.00 | 0.00 | 1.00 | 0.000 |

Read the rows together. Single-unit drives give the cleanest regressions (F1 0.72) and never see a
hidden unit, so every hidden world is published and the score is worse than declining. The
multi-unit design refuses every hidden world and books no false discovery, and pays for it with an
F1 of 0.22 - it declines three of the five solvable networks as well. Coverage 0.57 is the number
to beat: a design that keeps the refusals and answers the solvable networks has the score.

## Rules

## Rules

- Only edit `solution.py`; keep `discover_couplings(problem, run_experiment)`.
- `sle.contract_lint` is importable and free to call for shape checks. It costs no experiment.
- Do not read `verification/` or `frontier_eval/`.
