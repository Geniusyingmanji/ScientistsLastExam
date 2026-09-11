# ClockSyncInversion: known best

## Numerical repair (2026-09-11, after the admission HOLD)

The HOLD of 2026-09-11 rested on a solver problem, not on the science. The complete
fixed ten-call plan at `56778e87` returned two valid baseline scores of zero and eight
`candidate_runtime_error` results for the reference, the detection-only probe and the
two ablations; those records keep score `-1e18` and are not rewritten
(`.research/pr83_numerical_hold_2026-09-11.md`).

The cause, reproduced in `.research/clock_sync/solver_check.py`:

- **HiGHS starts worker threads.** One `linprog(method="highs")` call takes this
  process from 1 native thread to 5 under SciPy 1.10.1, whatever the thread options.
  The candidate sandbox denies `clone` and `clone3` (`sle/secure_eval.py`), so the
  original reference died there with `candidate_worker_exit`.
- **The interior-point fallback stops short.** With every `linprog` redirected to the
  legacy interior-point method, two of the eighteen worlds (dev-10 and held-06 on the
  graded run seed) end at the solver's iteration limit and the reference raises. That is
  the failing property test and the eight invalid sandbox results.

The reference and its three declared candidates now solve the same LPs, in the same
centred and scaled coordinates and after the same exact lower-hull row reduction, with
SciPy's revised simplex under Bland's rule, which runs in the calling thread. On eight
run seeds it agrees with HiGHS on the same rows world by world: seven seeds identical,
one seed differing by 9.4e-5 in one world's mechanism score, every verdict the same,
no world raising under either solver. An evaluation takes about 3.5 seconds in process
against 0.9 with HiGHS. The property and runtime tests pass locally (20 tests, the real
sandbox test deselected on the build machine); the ladder, the probe and the robustness
check below were re-run on this source and `summary.py` recomputes every number.

Not run here, because the build machine has no Bubblewrap and no model endpoint: the
Linux sandbox gate that measures the `shortcut_probe` declarations (they stay `null`),
the wrapper double run, and the independent first-proposal calibration.

Maintainer revision, 2026-09-11: the original sandbox reference exited twice under
SciPy 1.10.1; baseline was valid and zero twice. The fixed detection-only probe and two
ablations are carried as standalone candidates. An independent check also found a
negative one-way propagation in the original frozen worlds. Midpoint delays now
range from 150 us to 1.9 ms so both directions remain within the stated 50 us to
2 ms physical range, without changing the random draw order or selecting on scores.
The FDR denominator is now interval claims, with the former per-world rate retained
under a separate name and all denominators explicit.

## Reference (truth-blind): an envelope LP with empty-queue rows

`verification/reference_envelope_lp.py`. It reads only the public problem and what `exchange`
returns, and it works in five stages.

- **Rounds.** The budget is split evenly over the links and over twelve rounds spread across the
  horizon, so every link is sampled early and late. Between rounds it waits.
- **Rough clocks.** Per round and link, half the difference of the minimum forward and backward
  delays gives an offset difference. Least squares over the network gives rough offsets and
  rates. They serve only to convert every sender timestamp to approximate true time.
- **Upper rows.** A delay is never below its propagation delay, so every probe gives
  x_b(t) - x_a(t) + p_ab <= y plus jitter. The three lowest residuals of every round and direction
  are kept with a margin of z pair sigmas, where z is the normal quantile of delta/4 over every
  probe (about 5.7). The fifth lowest residual of every round and direction is kept with the
  margin of the fifth order statistic of the round's jitter, a Beta quantile at delta/4 over all
  of them (about 3.1).
- **Empty-queue rows.** A lower-envelope LP in the manner of Moon, Skelly and Towsley (1999) fits
  the kept rows and picks, per direction and per third of the horizon, the probe with the lowest
  residual. With probability 1 - delta/4 that third holds at least a_min empty-queue probes, a_min
  the binomial quantile at the published floor of 0.05. The least of their jitters is then below
  a normal quantile q. So the picked probe gives x_b(t*) - x_a(t*) + p_ab >= y* - q - sigma/2, the
  half sigma allowing for the tilt of the envelope within a third.
- **Answer.** With p_ab >= L_ab and the calibrated asymmetry bounds, the LP's minimum and maximum
  of x_j at each epoch are the intervals. An infeasible LP means no affine clocks and constant
  delays within the bounds explain the exchanges, and it declines.

delta is 10^-3 per world. The three families of rows each take a quarter of it, so by the union
bound the chance that any row excludes the truth is at most three quarters of delta. The tilt
allowance is outside that bound.

| split | score | sharpness | false discovery | refusal | coverage | exchanges per world |
|---|---|---|---|---|---|---|
| development | 0.569 | 0.569 | 0.00 | 1.00 | 1.00 | 19960 |
| held out | 0.503 | 0.503 | 0.00 | 1.00 | 1.00 | - |

World by world on the development split, the sharpness runs from 0.351 in the eight-node world
with four calibrated links to 0.829 in the world with none. On a calibrated link the identifiable
width is 1 to 2 us, and the reference's statistical margins, a few pair jitters each side, are
most of its width. Elsewhere the identifiable widths run from 3.4 to 54 us, and the margins
matter less. All five unsupported worlds are declined. Held out it scores
0.462, 0.527, 0.387 and 0.635 in the supported worlds and declines both unsupported ones.

What it leaves on the table, by design:

- **Its margins are union bounds.** Every upper row holds with a family-wise guarantee over tens
  of thousands of probes. The truth rarely sits near any single row, so tighter margins lose
  little safety.

The recoverable headroom is the same LP with the lowest residuals' margin at three pair sigmas
instead of about 5.7, `.research/clock_sync/ladder.py headroom_z3`. It scores 0.652 on the
development split and 0.594 held out, with no false discovery over eight run seeds. The cliff is
close: at 2.5 sigmas it scores 0.704 and 0.658 on the graded seed but misses a held-out offset on
four of the eight seeds. At 2 sigmas it loses held out on the graded seed and declines
supported worlds as the rows start to contradict each other.

## Model draws

None. The task was built on a machine without a model endpoint. The card records
`calibration_evidence_status: missing`; the frontier draw and the global evidence refresh are owed
before certification.

## Baseline: NTP with a rate, never declining

`solution.py`. Twelve rounds of exchanges on every link, spread over the horizon. In each round,
half the difference between the minimum forward and the minimum backward delay. A line through
the rounds for every link, offsets carried out from node 0 along a breadth-first tree, and five
microseconds either side.

| split | score | raw | sharpness | false discovery | refusal | coverage |
|---|---|---|---|---|---|---|
| development | 0.000 | -0.583 | 0.00 | 1.00 | 0.00 | 1.00 |
| held out | 0.000 | - | 0.00 | 1.00 | 0.00 | 1.00 |

It misses a true offset in every supported world and claims every unsupported one. Half the
difference of the two minima is an offset only when the two directions have equal propagation
delays. And the minimum over a round of probes drifts with the clocks within the round.

## Difficulty ladder

`.research/clock_sync/ladder.py`, one reference choice changed at a time. The graded seeds are the
evaluator's own. The mean re-draws every world's run seed eight times, so the queueing and the
jitter change and the worlds do not. False discoveries count misses in supported worlds and claims
in unsupported ones.

| strategy | development | held out | mean over re-drawn seeds (dev / held) | false discoveries (dev / held) |
|---|---|---|---|---|
| reference | **0.569** | 0.503 | 0.567 / 0.502 | 0 / 0 |
| without the order-statistic rows | 0.507 | 0.445 | 0.507 / 0.443 | 0 / 0 |
| empty-queue rows at the upper margin z instead of their quantile | 0.499 | 0.422 | 0.499 / 0.420 | 0 / 0 |
| empty-queue rows used only as a test | 0.348 | 0.257 | 0.349 / 0.256 | 0 / 0 |
| one empty-queue row per direction instead of three | 0.116 | 0.228 | 0.113 / 0.222 | 24 / 8 |
| two per direction | 0.427 | 0.255 | 0.390 / 0.251 | 10 / 8 |
| six per direction | 0.545 | 0.471 | 0.545 / 0.472 | 0 / 0 |
| no empty-queue rows | 0.000 | 0.000 | 0.000 / 0.000 | 32 / 16 |
| one round instead of twelve | 0.000 | 0.000 | 0.000 / 0.000 | 37 / 17 |
| 4 or 24 rounds | 0.554, 0.559 | 0.497, 0.492 | 0.557 / 0.496, 0.562 / 0.494 | 0 / 0 |
| keep 1 or 10 lowest residuals | 0.569, 0.569 | 0.503, 0.503 | 0.567 / 0.502, 0.567 / 0.502 | 0 / 0 |
| third or eighth lowest residual for the order-statistic rows | 0.556, 0.574 | 0.492, 0.507 | 0.555 / 0.490, 0.571 / 0.506 | 0 / 0 |
| no tilt allowance | 0.580 | 0.516 | 0.578 / 0.515 | 0 / 0 |
| empty-queue rows at a hand-set 1 or 2 pair sigmas | 0.563, 0.545 | 0.497, 0.475 | 0.561 / 0.496, 0.543 / 0.474 | 0 / 0 |
| upper margin 3.5 sigmas | 0.614 | 0.553 | 0.614 / 0.550 | 0 / 0 |
| **headroom**: upper margin 3 sigmas | 0.652 | 0.594 | 0.652 / 0.592 | 0 / 0 |
| upper margin 2.5 sigmas | 0.704 | 0.658 | 0.685 / 0.436 | 0 / 4 |
| upper margin 2 sigmas | 0.648 | 0.000 | 0.525 / 0.263 | 5 / 5 |

The empty-queue rows do two jobs. As a test they are what catch the faults. Without them the LP
absorbs a rate step, a jump or a miscalibrated link into queueing, claims six of the seven
unsupported worlds and scores zero. With one row per direction over the whole horizon a rate step
or a jump bends the floor too little to leave the LP infeasible, and four unsupported worlds are
claimed. As constraints they also sharpen the intervals: used only as a test, they leave intervals
that score 0.348 and 0.257. One round cannot see a rate at all. The number of rounds and of kept
residuals matters little once the budget is spread over the horizon. The order-statistic rows earn
about a tenth of the score. The margins decide the rest, and tightening them trades a little
sharpness for a false discovery rate that climbs fast below three sigmas.

## Shortcut probe

`.research/clock_sync/ladder.py probe`, 29 strategies that do not contain the reference's full
pipeline, in five families:

| family | strategies | best development | held out | best strategy |
|---|---|---|---|---|
| blind: decline everything, or one second either side of zero everywhere | 2 | 0.000 | 0.000 | either |
| NTP midpoints on all the data at 1, 5, 20, 100 and 1000 us, and NTP with a rate at 1, 5 (the baseline), 20, 100 and 1000 us | 10 | 0.000 | 0.000 | any |
| Cristian boxes per round from the minimum delays and the lower bounds, at margins of 3 and 5.45 pair sigmas, with and without a rate | 4 | 0.000 | 0.000 | any |
| the reference's LP without empty-queue rows, with no model check or a line test on per-round NTP differences at 2, 5 and 10 us | 4 | 0.000 | 0.000 | any |
| the reference's LP answering without empty-queue rows after a model check: the reference's rows at three upper margins, or a hand-set floor test at 2, 3 and 5 pair sigmas over thirds or rounds | 9 | **0.385** | 0.298 | the reference's rows as a test, upper margin 3 sigmas |

The best strategy reaches 0.385 on the development split, 68 per cent of the reference, and 0.298
held out, 59 per cent. Over eight re-drawn seeds it averages 0.385 and 0.296 with no false
discovery. Everything that does not check the model scores zero. Claiming all five unsupported
development worlds caps a strategy at 2/7 even with perfect intervals, and these strategies'
intervals are wide or miss. NTP answers miss true offsets in every world. Cristian boxes built from the minimum over a round
contradict each other, because the clocks drift within the round, and so they decline everything.
The line test on per-round NTP differences fails for the same reason.

## Construction errors caught on the way

- The oracle's identifiable-width LP was first run on the unsupported worlds too, where the true
  delays violate the published bounds and the LP is infeasible. Widths are computed for
  supported worlds only.
- Fault sizes were first judged by the smallest uniform relaxation in seconds. A fault on a
  software-stamped node, under 2 us jitter, was invisible although it looked large. Detectability is
  now measured in pair jitters, kappa*, and every unsupported world sits between 13.0 and 23.2.
- With an empty-queue floor of 0.01 the detection-only shortcut reached 91 per cent of the
  reference held out. The floor is now 0.05, the calibrated asymmetries sit at 0.6 to 1.0 of their
  bound, and the held-out worlds carry more calibrated links.
- That change re-drew every world, and three unsupported worlds fell to a kappa* of 0 to 2.7. Their
  faults were moved and resized: the development rate step to node 1 at 3 ppb, and the two
  miscalibrations of 40 us to 60 us on other links.
- A reference with upper margins at the family-wise z on the lowest residuals alone was beaten by
  27 and 31 per cent by the same LP at z = 3, with no false discovery. The order-statistic rows cut
  that to 15 and 18 per cent, which is documented above as the headroom.
- The first robustness runs shifted the world seeds and so re-drew whole worlds. They now shift
  only the run seed.

## Robustness

`.research/clock_sync/pkg_eval.py reference 0 1 ... 15` re-runs the reference with every world's
run seed shifted. Over sixteen shifts it averages 0.567 on the development split, from 0.562 to
0.571, and 0.502 held out, from 0.495 to 0.507, with no false discovery in 288 world-runs and every
unsupported world declined. The headroom averages 0.652 and 0.592 over eight shifts with none.

`tests/test_clock_sync_inversion.py` checks that a campaign's delays follow the published model
against the true clocks. It checks the recorded identifiable widths and kappa*, zero in every
supported world and at least 12 in every unsupported one. It checks that the empty-queue rows are
what catch the faults, that a missed interval costs a world, and that two evaluations of the
reference agree key for key. It checks that declining everything scores 0.000 in both forms and a
blind wide claim scores 0.000. It checks 33 malformed candidate shapes, including overspending,
waiting past the horizon, a patched budget, malformed intervals and malformed calls. All of them
score valid 0, combined 0 and feasibility 0 without raising. A reference evaluation takes about 3.5
seconds in process with the revised simplex solver. It makes 1860 calls to `exchange` and 198 to `wait` in one evaluation, which the
sandboxed evaluation carries as RPC calls. `.research/clock_sync/summary.py` recomputes every
number on this page.

Not done: the sandbox half of `scripts/check_task_contribution.py` (no Bubblewrap on the build
machine), so the `shortcut_probe` declarations stay `null`; a frontier-model draw; the global
evidence refresh.
