# Catalyst aging bounded development plan

Frozen before scientific checks. No old evaluator imports or model API calls.

Each query submits an entire ordered laboratory history. A fresh identical lab
and four fresh identical coupons start every query. Events are serial and indexed
1..24; no state persists across calls. Blank and standard events measure the
instrument without using a coupon. Reaction events specify coupon A–D,
temperature440–560K, constant replenished feed concentration0.1–1.2 normalized
units and duration2–15min. A coupon may receive up to6reactions. Selected event
indices determine output rows; all events, even unobserved preparation, cost1.
One measured signal in normalized product units; independent additive unclipped
Gaussianσ.003; scale1.5. The true standard response1.5 is known, but its measured
signal is affected by unknown instrument gain and offset. No output is assigned.
Instrument drift advances with every physical event, not elapsed reaction time;
this is an explicit reduced apparatus assumption. Coupons do not age at rest.

Scientific ambiguity: a declining series on one coupon could be declining
activity or declining instrument gain. Blank/standard interleaving and fresh
coupon reaction controls can constrain these particular accounts. Separate
coupons' activity histories are independent; instrument drift is shared by all
events. A single short exposure may not resolve one versus two decay times.
Unknown mechanisms are not scored by recovering generation labels.

Fixed check parameters: q_ref=.08 product/min at nominal500K before concentration
factor; activation60000J/mol; d_ref=.016/min; deactivation activation30000J/mol;
saturation.4; instrument gain1.02, offset.012, gain slope−.003/event,
offset slope.0008/event. Additional fixed alternatives: no deactivation;
a jump at event7 of gain+.12/offset−.03; two activity populations with
fractions.6/.4 and relative decay.22/4.5. No fitting/choosing fixtures by outcome.

Independent check: integrate ODE for activity and product with SciPy DOP853,
rtol1e−11/atol1e−13, using an independently expressed RHS. Match production exact
expm1 integral for T440/500/560,K; C.1/.6/1.2; duration2/8/15min;
starting activity1/.1; decay multipliers0/1/4.5 (162cases). Check limits,
nonnegative product, nonincreasing activity, same-condition semigroup, coupon
isolation, serial event order, jump boundary, subset readouts, full-history reset,
noise replay and invalid controls. ODE agreement is numerical verification,
not evidence for actual catalysts; replay and monotonicity are consistency checks.

Diagnostic budget: <=200independentODEsolves, <=300World.run calls,
<=10000closedform site updates, zerooptimizer fits, <=120CPU and wallseconds.
Fixed development seeds72001–72003; panel seeds82001–82003. Exclude these seeds
from future modelcohorts. Measure zero and public nearest-history baselines on
six fixed training schedules and sixteen fresh queries per instance. Keep raw
input/output/metrics outside repository. No strong inverse baseline is claimed.
Maintain prototype status until explicit shared integration and review.
