# DistillationColumnDesign — robust mixed-integer equilibrium-stage design

## Scientific background

A distillation design must meet both product specifications and recovery targets while trading
capital against reboiler/condenser duty.  Adding equilibrium stages can reduce the reflux needed
for a separation, but increases column cost.  Feed location is discrete and interacts strongly
with feed composition and quality.  A nominally inexpensive design can also fail when relative
volatility, feed state, composition or attainable reflux changes.

This task uses a deterministic binary equilibrium-stage model with constant molar overflow, a
total condenser and a partial reboiler.  Feed flow is one mole per unit time.  For liquid light-
component mole fraction `x` and public relative volatility `alpha`, every equilibrium stage obeys

```text
y(x) = alpha*x / (1 + (alpha - 1)*x).
```

With distillate fraction `D`, bottoms flow `B=1-D`, reflux ratio `R` and liquid feed fraction
`q`, the section flows are

```text
L_rect = R*D                 V_rect = (R+1)*D
L_strip = L_rect + q         V_strip = V_rect - (1-q).
```

The trusted solver closes the light-component balance on every tray, the feed tray and the
partial reboiler.  For example, an internal rectifying tray has

```text
L_rect*x[j-1] + V_rect*y[j+1]
  = L_rect*x[j] + V_rect*y[j],
```

and the feed stage adds the public feed composition.  The total condenser returns liquid of the
top-vapour composition; the partial reboiler satisfies

```text
L_strip*x[last_tray] = B*x_bottoms + V_strip*y_bottoms.
```

The oracle verifies every stage residual and the overall component balance rather than assigning
product purity from the requested target.

## Your task

Implement one policy that handles varying volatility, feed, specifications and cost regimes:

```python
def design_column(problem):
    """Return a mapping with five finite design variables."""
```

The required fields are

```text
tray_count           exact integer; excludes the partial reboiler
feed_stage           exact integer from 1 (top tray) through tray_count
reflux_ratio         external liquid reflux / distillate flow
distillate_fraction  distillate flow / unit feed flow
feed_split_gain      feed-forward change in distillate fraction per change in feed composition
```

All bounds are supplied in `problem`.  The mapping also contains the feed composition and liquid
fraction, relative volatility, top and bottom specifications, minimum light/heavy recoveries,
and annualized fixed, per-stage and vapour-duty cost coefficients.  Values outside the contract
are rejected rather than clipped.

For a sealed feed-composition change from `z_nominal` to `z_actual`, the trusted operating
model uses

```text
D_actual = D_nominal + feed_split_gain*(z_actual - z_nominal).
```

This is a documented feed-forward operating policy, not access to the sealed shift outcome.

## Evaluation

The same policy is called on four development and two interleaved held-out separations.  A design
is process-feasible only when the stage solver converges, all stage and overall balances close,
both product purities pass and both component recoveries exceed their public minima.  Its nominal
annualized reduced-order cost is

```text
fixed_cost + tray_cost*tray_count
           + vapour_cost*max(V_rect, V_strip).
```

`combined_score` is the mean development cost improvement above a conservative valid weak
baseline, normalized by separately calibrated fixed-seed mixed-integer witnesses.  The witnesses
are reproducible feasible designs, not proofs of global optimality.  Better feasible designs are
allowed and clip at one.

The trusted evaluator separately retains:

- nominal product purities, recoveries, flows, balance residuals and annualized cost;
- interleaved held-out transfer; and
- sealed robustness under lower relative volatility, richer and leaner feeds, changed feed
  quality, reflux derating, and a combined operating shift.

Nominal development cost controls search.  Held-out instances and all shifted conditions remain
outside proposal and selection state.

## Scope and rules

- Only edit `solution.py`; keep `design_column(problem)`.
- Use deterministic Python/NumPy/SciPy CPU code only.
- Handle the supplied problem rather than hard-coding one mixture or target.
- No network or process creation.  Do not read `verification/` or `frontier_eval/`.

This is a reduced-order binary equilibrium-stage model.  It omits multicomponent/non-ideal
thermodynamics, pressure drop, tray efficiency, flooding/weeping, heat integration, detailed
equipment sizing and closed-loop control.  Engineering claims require an independently
configured process simulator and experimental or plant data.

References: McCabe & Thiele, *Industrial & Engineering Chemistry* 17, 605--611 (1925),
doi:10.1021/ie50186a023; Naphtali & Sandholm, *AIChE Journal* 17, 148--153 (1971),
doi:10.1002/aic.690170130; Boston & Sullivan, *Canadian Journal of Chemical Engineering* 52,
52--63 (1974), doi:10.1002/cjce.5450520108; Yeomans & Grossmann, *Industrial & Engineering
Chemistry Research* 39, 4326--4335 (2000), doi:10.1021/ie0001974.


## Inputs the candidate receives

Every key the baseline reads off the input mapping. Names are part of the contract: a candidate
that reaches for one of these quantities under a different name raises at runtime and scores
nothing, and that zero cannot be told apart from a zero earned on the science.

| key | |
|---|---|
| `distillate_fraction_bounds` | previously undocumented |
| `feed_light_mole_fraction` | previously undocumented |
| `maximum_bottoms_light_mole_fraction` | previously undocumented |
| `minimum_distillate_light_mole_fraction` | previously undocumented |
| `minimum_heavy_recovery` | previously undocumented |
| `minimum_light_recovery` | previously undocumented |
| `reflux_ratio_bounds` | previously undocumented |
| `relative_volatility` | previously undocumented |
| `tray_count_bounds` | previously undocumented |

A key not listed here may still exist; this table is what the shipped baseline uses.
