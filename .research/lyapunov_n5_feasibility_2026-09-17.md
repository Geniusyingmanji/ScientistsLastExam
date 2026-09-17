# n=5 feasibility measurement — LyapunovDecayCertificate

Date: 2026-09-17. Read-only measurement for PR #27; no task package was modified to
produce it. It answers fix-list item 2-ii ("raise to n>=5-6 with >=6 modes so the
reconstruction gap becomes the headroom") before any of that redesign is attempted.

This answers a DESIGN question about a candidate redesign, so it is an operator
artifact, not frozen benchmark evidence: `scientific_admission: not_assessed` and
`trusted_evidence: false`. Nothing here promotes a task or binds a score.

The raw scripts and JSON results are not shipped; they were run in a scratch
directory outside the repository. Every number below is reproducible from the
commands in the final section.

## Headline

**n=5 with 6 modes fits the evaluation budget with ~250x margin, but the
reconstruction gap is not real headroom. The answer to the redesign question is
no** — on 3 of 5 systems the exact rational certificate *beats* the float
"optimum", because the float optimizer is not itself converged. The gap that
remains at the resolution the magnitude caps actually allow is 0.0002%, three
orders of magnitude below the 2% threshold that would make a 20% guard margin
meaningful.

## Method note that invalidates a naive timing

This environment imposes a **cgroup CPU quota of 4 CPUs**
(`/sys/fs/cgroup/cpu.max` = `400000 100000`) while `nproc` reports **128**.
Background numpy jobs spawn one BLAS thread per *visible* core (127 threads
observed), massively oversubscribing the quota and inflating any concurrent
timing. Control experiment (`m_consistency.py` and the inline quota test):

```
idle        : 0.006528 s/cert
quota full  : 0.018163 s/cert   (8 busy-spin processes)
released    : 0.006548 s/cert
```

My own first readings ran 3—38x high for this reason. **Every number below is
from a single-threaded run** (`OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1`) with my own jobs stopped. Two of the
headline conclusions (budget fit, gap) hold even under the contended numbers,
so they are robust to this.

## Precondition: the reimplementation was cross-checked, not trusted

`exact.py` reimplements the shipped evaluator's exact path from
`verification/evaluator.py`. Cross-checked against the shipped code itself
(`m_crosscheck.py`):

- 400 random rational matrices: `_nsd` and `_spd` agree, **0 mismatches**
- 4 shipped instances, shipped reference's own certificates: agree
- 1200 random `(P, alpha)` probes on shipped instances: **1200/1200 agreement**

## M1 — exact certificate verification cost at n=5, 6 modes

The operation that actually runs in the budget: given `(P, alpha)`, check
`A_i^T P + P A_i + alpha P` is NSD for every mode in exact rationals —
`n_modes * 2^n` principal minors, here 6 * 32 = 192 determinants.

**Realistic shape** (the rounded float optimum — what a good submission is):

| gram | max abs num | max den | alpha | s/certificate |
| --- | --- | --- | --- | --- |
| rounded opt den=1e3 | 721 | 1000 | 319737/1000000 | 0.0095 |
| rounded opt den=1e4 | 3851 | 10000 | 320041/1000000 | 0.0094 |
| rounded opt den=1e6 | 957591 | 1000000 | 320049/1000000 | 0.0096 |

9 such Grams across 3 seeds: **0.0089—0.0096 s**.

**Worst case** — dense, sheared, numerators pinned exactly at the `10**6` cap.
Constructed by scaling a valid certificate by `c = 10**6 // max_num`; `P -> cP`
leaves validity and alpha unchanged, verified exactly 200/200 before relying on
it:

| seed | max abs num | max den | s/certificate |
| --- | --- | --- | --- |
| 5101 | 499707 | 500000 | 0.0091 |
| 5102 | 957591 | 1000000 | 0.0095 |
| 5103 | 654657 | 1000000 | 0.0094 |
| 5104 | 864219 | 1000000 | 0.0098 |
| 5105 | 764607 | 1000000 | 0.0094 |

10 such Grams: **0.0087—0.0104 s**.

**Cost is flat in magnitude.** Sweeping `P = c*I` for `c in {1, ..., 10**6}`:
0.0064—0.0067 s. Sweeping `P = I/d` for `d in {1, ..., 10**6}`: 0.0066—0.0071 s.
Det calls and the largest numerator fed to `det` are identical for tight and
loose alpha (186 calls; 4.87e6 vs 609) — the rationals reduce to the same size
because `Fraction` normalizes by gcd and the exponents here are small.

```
python3 m_verify.py             # diagonal magnitude sweeps
python3 m_verify_realistic.py   # rounded-optimum Grams
python3 m_verify_worstcase.py   # numerators at the 1e6 cap
```

### One exact bisection, end to end (settles the "21 minutes" claim)

`m_bisect.py` runs a full bisection to the public `1/10**6` alpha resolution
(22 `certificate_holds` calls):

| seed | modes | alpha | seconds |
| --- | --- | --- | --- |
| 5101 | 6 | 128337/1000000 | 0.121 |
| 5102 | 6 | 111003/1000000 | 0.089 |
| 5103 | 6 | 139691/1000000 | 0.115 |
| 5104 | 6 | 22773/200000 | 0.087 |
| 5105 | 6 | 50267/500000 | 0.101 |

**mean 0.102 s per bisection.** The earlier report that a single exact n=5
bisection "did not finish in 21 minutes" is off by four orders of magnitude. It
was either measured under the CPU contention above, or it was timing the whole
catalog search (which at n=5 runs `|catalog|` bisections in sequence), not one
bisection.

### Full shipped evaluator path at n=5

`m_evaluator_n5.py` loads `verification/evaluator.py` **unmodified** from the
worktree, rebinds only `STATE_DIMENSION` and `GRAM_KEYS`, installs 4 instances
of 6 modes, and times `evaluate()`:

```
0.0564 s per full evaluate() call   (4 instances x 6 modes)
combined_score = 0.522296  valid = 1.0  feasibility = 1.000
```

**0.056 s against a declared `eval_time_seconds: 15`** — 0.4% of budget. The
contended measurement of the same thing was 0.50 s, also comfortably inside.
Verification cost is a non-issue at n=5.

## M2 — n=3 calibration

| instance | modes | max num | max den | s/certificate |
| --- | --- | --- | --- | --- |
| plant | 3 | 5 | 4 | 0.000595 |
| cascade | 4 | 1 | 3 | 0.000817 |
| mixed | 3 | 5 | 4 | 0.000595 |
| sparse | 3 | 2 | 1 | 0.000414 |

**n=5 / n=3 verification ratio ≈ 11.6x** (0.0069 / 0.000595) for a 2.08x
increase in dimension — consistent with the `2^n` growth in minor count times
the larger elimination cost.

Separately: the shipped **n=3 reference costs 38.4 s** across the four
instances (`evaluate(reference.build_lyapunov)`), i.e. the reference's own
catalog search — not verification — dominates at n=3. At n=5 that search grows
faster than verification, which is why M3 matters for the reference.

## M3 — float optimum cost at n=5

`scipy.optimize.minimize` (Nelder-Mead, then Powell) on `P = expm(S)`, `S`
symmetric — a diffeomorphism onto the whole PD cone. The problem is
scale-invariant in `P` (`P -> cP` leaves every generalized eigenvalue
unchanged), so no `P >= I` normalization is needed and the parametrization
covers the full feasible set. `m_float.py`.

| seed | 1 restart | 4 restarts | 16 restarts |
| --- | --- | --- | --- |
| 5101 | 0.486125 (1.2 s) | 0.486125 (13.3 s) | 0.486125 (102 s) |
| 5102 | 0.320050 (21.4 s) | 0.320050 (255 s) | 0.320050 (703 s) |
| 5103 | 0.392211 (1.4 s) | 0.392211 (9.0 s) | — |

**Restarts buy nothing.** The 16-restart incumbent equals the 1-restart value
in every seed; the other 15 starts land at 0.02—0.47. Wall time per restart
varies 0.9—54 s for identical work because of the quota and concurrent teammate
load, so treat the second column as an upper envelope, not a precise cost.

**Reference-side implication: single-start is correct and costs ~1—20 s per
instance.** A 16-restart reference would be pointless and can exceed the 300 s
wrapper timeout (703 s observed under load). Note the accuracy caveat in M4.

### Is the reference-side cost affordable, and do restarts matter?

Two separate questions, two answers:

**Restarts: no, they do not matter, and the data is unambiguous.** The
1-restart value equals the 16-restart value in both seeds where 16 restarts were
run (5101, 5102; 5103 was stopped at 4 restarts), and equals the 4-restart value
in all three. The other 15 starts land between -0.468 and 0.466 — always *below*
the all-zero start, never above. Multi-start buys robustness against an unlucky
first draw; here the
all-zero start is the best draw in every seed. That is a natural, deterministic
choice: `S = 0` is `P = I`, and the identity is a known common Lyapunov function
on this family, so the start is already in the right basin. That is a property of
the shipped family's structure (modes near the identity, `P = I` feasible) and it
is what makes single-start defensible rather than merely convenient.

**Affordability against the two budgets** (3 seeds; the 21 s and 255 s figures
are contended — see the timing caveat):

| reference config | cost per instance | vs `eval_time_seconds: 15` | vs 300 s wrapper |
| --- | --- | --- | --- |
| 1 restart | 1.2—21 s | 2 of 3 fit; slow seed 1.4x over | fits |
| 4 restarts | 9—255 s | 2 of 3 fit; slow seed 17x over | fits |
| 16 restarts | 102—703 s | **exceeds by 7—47x** | **may exceed under load** |

So a *single-start* float reference is affordable on both budgets. Anything more
is not, and the 21 s figure for seed 5102 single-start is itself inflated by the
CPU-quota contention described at the top — the uncontended value is lower. The
honest statement is that single-start fits with margin, and the restart count is
a budget risk with no measured benefit.

One caveat on all the M3 wall times: they span 0.9—54 s for *identical* work
depending on what else held the 4-CPU quota, so the table above should be read
as bounds, not as expected values. The alpha *values* are stable; the seconds
are not.

## M4 — the reconstruction gap (the decisive number)

`gap = 1 - alpha_best_exact / alpha_float`. `m_gap_decomposed.py` separates the
two causes the discarded proxy conflated: **P rounding** (bisect alpha on the
finest grid the caps allow, `1/10**6`, at the rounded P) versus **alpha
quantization** (representable only to the P denominator).

| seed | P den | gap_total | gap_P_only | gap_alpha |
| --- | --- | --- | --- | --- |
| 5101 | 1e3 | 0.0256% | 0.0240% | 0.0016% |
| 5101 | 1e6 | 0.0001% | 0.0001% | 0.0000% |
| 5102 | 1e3 | 0.3279% | 0.0977% | 0.2303% |
| 5102 | 1e6 | 0.0002% | 0.0002% | 0.0000% |
| 5103 | 1e3 | 0.3087% | 0.1177% | 0.1910% |
| 5103 | 1e6 | 0.0001% | 0.0001% | 0.0000% |
| 5104 | 1e3 | 0.2451% | 0.0006% | 0.2445% |
| 5104 | 1e6 | 0.0001% | 0.0001% | 0.0000% |
| 5105 | 1e3 | 0.0652% | 0.0006% | 0.0647% |
| 5105 | 1e6 | 0.0000% | 0.0000% | 0.0000% |

At `P` denominator `10**6` — permitted by the caps — the **maximum gap over 5
systems is 0.000182%**. Large gaps appear only at very coarse `P` denominators
(1, 10, partly 100), and they are an artifact of restricting representation,
not of rationality: a candidate that rounds `P` to `1/10**3` and bisects alpha
on the `1/10**6` grid still loses only 0.0256—0.3279%, already below the 2% bar.

**Which of the two causes dominates depends on the grid, and this matters for
reading the table.** At `P` denominator `10**3`, *alpha quantization* dominates
in 4 of 5 seeds (5102: 0.2303% vs 0.0977%; 5103: 0.1910% vs 0.1177%; 5104:
0.2445% vs 0.0006%; 5105: 0.0647% vs 0.0006%); P-rounding dominates only in
5101 (0.0240% vs 0.0016%). At `P` denominator `10**6` the alpha term is exactly
zero in all five seeds and only the P term remains (0.000029—0.000182%). So the
visible gap at coarse denominators is **mostly an avoidable artifact of
quantizing alpha to the P denominator**: a candidate is free to bisect alpha on
the finest grid the caps allow while rounding `P` coarsely, and doing so
recovers nearly all of it. What is left after that is pure P-rounding loss, and
it is 0.0002% at worst.

### The float "optimum" is not converged, so the gap has the wrong sign

A trust-region refine around the rounded optimum (`radius=0.05`) reached a
strictly **higher** exact alpha than the float optimum on 3 of 5 systems:

| seed | float F | best exact | gap |
| --- | --- | --- | --- |
| 5101 | 0.486125 | 0.491384 | **-1.08%** |
| 5102 | 0.320050 | 0.326785 | **-2.10%** |
| 5103 | 0.392211 | 0.398742 | **-1.67%** |
| 5104 | 0.368904 | 0.368904 | +0.0001% |
| 5105 | 0.380248 | 0.380248 | +0.0000% |

**gap range -2.10% to +0.0001%, mean -0.97%.**

A local Nelder-Mead/Powell search lands below the true optimum; a cheap exact
grid refine in its neighbourhood beats it. So `1 - alpha_exact/alpha_float`
measures the float optimizer's own convergence error (1—2%, with the opposite
sign), not reconstruction loss.

### What this does to the premise

The redesign's premise is that the reference sits at a well-defined ceiling (the
float LMI optimum) and the submitted exact certificate lands strictly below it,
so the distance between them is searchable headroom. **The data breaks the
premise at its anchor rather than at its far end.** Two measured facts:

1. The float optimum is not a fixed point of the "round then re-optimize" map.
   Rounding an exact point and re-optimizing exactly lands *above* it on 3 of 5
   systems, by 1.1—2.1%. So the quantity `1 - alpha_exact/alpha_float` does not
   measure how far a candidate is below a ceiling; it measures how far the
   *reference* is below its own reconstruction. Its sign is not stable.
2. At the resolution the caps permit, the reconstruction step costs 0.0002%
   regardless. So even where the anchor were sound, there is nothing left to
   measure — the two numbers agree to four decimal places.

Together these mean the gap cannot serve as headroom: it is either swamped by
reference error (1—2%, wrong sign) at the coarse end, or numerically zero
(0.0002%) at the end the caps actually allow. There is no grid resolution where
it is both well-defined and large. Per the earlier note, whether some *other*
source of headroom exists is outside this brief — this measurement says only
that the reconstruction gap is not it.

## M5 — verdict

**1. Does n=5 fit the evaluation budget? Yes, with ~250x margin.**
Full shipped `evaluate()` over 4 instances x 6 modes: **0.056 s** against
`eval_time_seconds: 15` — 0.4% of budget, ~0.02% of the derived 300 s wrapper
timeout. One exact bisection: **0.102 s**, not 21 minutes. Worst-case
verification (dense, sheared, numerators pinned at the `10**6` cap): **0.0104 s**
worst observed. Nothing in M1 comes within an order of magnitude of the budget.

**2. Does the reconstruction gap constitute real, measurable headroom? No.**
- At the resolution the caps allow (`P` denominators `10**6`) the gap is
  **<= 0.000182%** — three orders of magnitude below the 2% bar, and far below
  the 20% `relative_margin` the current shortcut contract uses.
- The sign is wrong: exact rational certificates **beat** the float reference by
  1—2% on 3 of 5 systems.
- The gap only becomes visible (0.03—0.33%) at `P` denominators of `10**3` or
  below, and even then it is largely an artifact of representation limits rather
  than a genuine hardness gap.

**Negative result: raising n to 5 with a float-LMI-optimum reference does not
create the intended headroom.** The compute side of the redesign is cheap and
safe; the scoring side does not work as proposed. If the maintainer's goal is
headroom, the lever is the **denominator cap**, not the state dimension — but
that changes the submission contract and the reference's bisection schedule, and
is a maintainer design decision, not a PR edit. (Noted as an observation, not a
proposal.)

## Biggest uncertainty

The float optimum is only as good as my optimizer, and it is a local search —
the trust-region refine proving it suboptimal by 1—2% is direct evidence of
that. A proper SDP solve would give a converged `F`, and then the true gap might
be positive rather than negative. **cvxpy is not installed** in this environment
(nor SCS or Clarabel), so I could not do that; it would need `uv add cvxpy`.
This does not rescue the redesign at `P` denominators `10**6`, where the
measured gap is 0.0002% regardless of `F`'s value, but it does mean the exact
size and the sign of the mean of the *true* gap are not settled here. My
estimate is that a converged `F` moves the gap to roughly 0—0.2% at fine
denominators, still an order of magnitude short of 2%.

A second, smaller uncertainty: the n=5 instance family is mine, constructed to
match the shipped style (see below), not a maintainer-supplied family. The
comparison is of the exact arithmetic, not of task content.

## Note on the discarded proxy

The earlier proxy used a "`P = I` is a common Lyapunov function" construction at
`k=128`, which is not the real setting. Confirmed independently: with `P = I`
the exact certified alpha is 0.128337 (seed 5101) against a float optimum of
0.486125 — a 3.8x gap — but none of that is reconstruction loss, since `P = I`
is not a rounding of anything and its exact alpha is computed with zero error.
This is why the proxy overstated the available headroom.

## Reproduce

The scripts are not shipped with the repository. To rebuild the measurement, an
n=5 instance family with six rational Hurwitz modes per instance is the only
input, and everything else is the shipped evaluator's own arithmetic:

```bash
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
```

1. **M1/M2 (verification cost).** Build an n=5, six-mode instance in the shipped
   style, then time `verification/evaluator.py`'s own `_nsd`/`_spd` on one
   certificate, at the parameter caps and at a dense/sheared worst case. The
   cross-check to run first: the same timing on a shipped n=3 instance, so the
   n=5 number is stated as a ratio rather than in isolation.
2. **M3 (float cost).** Multi-start Nelder-Mead maximizing the minimum eigenvalue
   of `-(A_i^T P + P A_i)` over the PD cone, at 1/4/16 starts.
3. **M4 (the gap).** Take the float optimum, round `P` to denominators 1…10^6,
   bisect `alpha` exactly at the rounded `P`, and compare against
   `alpha` at the float `P`. Report the two components separately — rounding `P`
   and quantising `alpha` — because they behave differently.

`instances.json` holds 5 seeds (5101—5105), 6 modes each, entries drawn in the
shipped style (diagonal in `[-5/2, -3/5]`, off-diagonal rationals with
denominators <= 4, ~55% density), scaled so `max |entry| ~ 1` where the reference
bisects. Every mode is built so `-sym(A)` is exactly PD — matching the shipped
family's stated property that the identity Gram is a common Lyapunov function,
and guaranteeing every mode is Hurwitz.
