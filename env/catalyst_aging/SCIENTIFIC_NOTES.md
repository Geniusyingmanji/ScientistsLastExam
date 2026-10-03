# Operator assumptions and limits

This synthetic laboratory models irreversible loss of catalytic activity and an
instrument with shared event-index drift. It is not a validated physical
reactor or evidence about a named catalyst. Constant feed is replenished; product
is accumulated within an event and collected/reset between events. Substrate
conservation in a closed batch is outside this apparatus. Coupons are identical
at preparation and do not age while idle. Instrument drift is per event, not per
elapsed physical minute; this simplified convention is part of the public
apparatus, not a hidden timing rule.

Production uses an Arrhenius-scaled saturating production rate and one or two
exponentially decaying activity populations. The stable `expm1` integral includes
its exact zero-decay limit. Independent adaptive integration of activity/product
ODEs checks the integration; semigroup, positivity, state isolation, prefix and
noise-replay checks establish consistency. They do not validate the physical
model. Raw scientific diagnostics live in operator artifacts.

Private variation includes single-population decay with gradual instrument
drift, an instrument step, or two activity populations. Labels support balanced
cohort construction and are not required model answers. The apparatus description,
noise, controls, budgets and panels do not depend on these labels. Parameters are
fixed within an instance; every query resets the lab and preserves those same
parameters. Consequently, identical prefixes yield identical clean outcomes;
new measurement keys change only independent readout noise.

A declining series on a reused coupon is ambiguous between activity loss and
instrument change. Fresh coupon controls plus interleaved blanks/standards can
constrain this ambiguity. Because blank and standard events occur at different
instrument indices, simply subtracting adjacent readings assumes something about
drift between them. Abrupt changes can violate that assumption. A single short
reaction cannot identify a general distribution of decay times. One versus two
activity populations may remain practically indistinguishable over a limited
exposure range. Successful prediction of a finite history does not uniquely
identify a microscopic mechanism.

The public-record baseline uses event type, index, current controls and prior
same-coupon exposure features. It does not use hidden family/parameters or a
known reaction equation. Its error is a weak empirical comparison; no strong
inverse-model baseline or difficulty calibration is claimed. Package tests do
not constitute model evaluation, discovery depth or contamination resistance.
