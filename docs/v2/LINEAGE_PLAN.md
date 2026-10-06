# Lineage memory candidate: frozen witness plan

Synthetic inheritance experiment; not a validated microbial, medical or evolutionary
model. We reject a bulk two-state survival-curve wrapper: that would duplicate
existing latent-state history tasks. This candidate instead measures dependence
between replicated descendant groups from a common founder.

## Competing accounts

A founder has an unobserved binary state H with probability p. After a rest g,
a descendant retains the founder's state with probability rho(g); otherwise it
redraws a state independently from Bernoulli(p). Under challenge, a state-0 cell
survives with probability a and state-1 with probability b. Given the founder,
two descendant groups are independent binomial samples of n cells. Their average
survival is identical under all rho, while covariance between sibling-group
survival fractions is p(1-p) rho(g)^2 (b-a)^2. Compare stable memory rho=1 with
relaxing memory rho=exp(-g/tau). Nonzero covariance does not prove genetics: shared
preparation can create it. Scope findings to persistent lineage-associated memory.

## Discriminating design and unresolved regime

Measure paired groups at short and long rests with equal challenge. Random-pair
controls remove shared ancestry in the synthetic model. p near 0/1, b near a,
or a rest much shorter than tau can be inconclusive; a finite rest never proves
permanent inheritance. This covariance instrument may still overlap the isotope
joint-distribution task: keep only if lineage preparation, finite sampling and
rest-dependent uncertainty add material research value.

## First bounded unit (before execution)

Implement an operator witness kernel, not a registered World or agent task.
Analytic moments plus Monte Carlo with fixed exposed seed430 and 20000 founder
pairs, group size32. At most three sampling calls (short, long, unrelated) for
this unit. Tests use analytic limits and confidence-scaled error tolerances,
not a tuned separation threshold. No fitting, model calls, hidden evaluation
panels or difficulty claim. Preserve failures. Next gate: public apparatus,
explicit finite-sampling cost and uncertainty, independent reference, then
budgeted inference. Do not substitute Gaussian readout noise for lineage sampling.

## Confounding gate frozen before execution

Extend the synthetic survival probability to mu + L(H-p) + E(C-c), where H is
founder state and C is preparation-batch state. The two sources are independent.
Choose parameters with all four probabilities strictly inside [0,1]. In a pair,
founder identity and batch identity can each be shared or independently assigned.
Covariance equals I(shared founder)L²p(1-p) + I(shared batch)E²c(1-c).
When both identities always coincide and L²p(1-p)=E²c(1-c), lineage-only and
batch-only accounts agree in pair covariance. Crossed preparation separates them.
This remains a synthetic experimental-design witness, not proof of genetics.

Bounded validation: four sampling calls with fixed seed731, 20000 pairs and
32 cells/group, one per 2x2 shared-identity condition. Check covariance against
analytic expectation with a six-standard-error threshold. No fitting, tuning or
extra samples after failure. Re-running old tests is regression only, not fresh
scientific evidence. Full apparatus admission remains deferred until feasible
sampling budgets, unit costs and uncertainty are calibrated.

## Conservative finite-sampling screen (analytic only)
For X,Y in [0,1], D=(X-Y)^2 lies in [0,1]. With identical marginal
means/variances across grouping arms, E[D]=2(Var(X)-Cov(X,Y)). Thus independent
arm samples Z=(D_control-D_treatment)/2 estimate covariance increase without
knowing the population mean. Z lies in [-.5,.5]; a fixed single-contrast
Hoeffding radius is sqrt(log(2/alpha)/(2m)). Pair draws must be independent.
At alpha=.05 and radius .01, m=18445 pairs per arm. With32individuals/group,
two groups/pair and two arms, this costs2360960simulated individuals. Radius
.005 exceeds the current20000pair per-call cap. This is a conservative bound,
not a lower bound, empirical power estimate or proof the task is infeasible.
Decision: retain as candidate only; do not promote based on earlier20k-pair
witness. Next compare justified variance-aware uncertainty and a small fixed
budget design before implementing a full World. No sampling or fitting done.

Exact-variance development unit: before reporting a budget, fix mu=.5,L=.4,E=.2,
p=c=.5,n=32; compare neither-shared versus founder-only sharing. Two exact
finite-support moment calls, no simulation, fitting or parameter search. This
uses known synthetic parameters. Report Chebyshev sufficient pair count for a
single .01 radius at95%; do not give this privileged variance to a candidate.
Result: Var(Z)=.004871923828125; Chebyshev sufficient count975pairs/arm,
124800individuals at32/group. This narrower result is specific to the fixed
known-parameter fixture, not uniform over worlds; it is not a detection-power
claim or validated empirical interval. Earlier distribution-free18445 bound
remains correct and unchanged. Candidate-accessible uncertainty remains pending.
