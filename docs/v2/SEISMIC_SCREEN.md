# Seismic candidate screen — 2026-10-07

## Reject the simple two-parameter task

A homogeneous medium with a horizontal reflector gives the synthetic travel-time
instrument t(x)=sqrt(4h²+x²)/v, where x is source–receiver separation. Zero offset
only fixes h/v; changing offset distinguishes that ambiguity. But t² is linear
in x²: two exact distinct offsets recover slope1/v² and intercept4h²/v².
This is a useful apparatus test, not sufficient evidence for a high-difficulty
open-discovery environment. Do not implement/register this as a standalone world.

Source context: UCL lecture notes on reflection travel-time curves:
https://www.ucl.ac.uk/~uccghlv/GEOL2014/Revised%20Course/Detailed%20Lecture%20Notes/LECTURE4.PDF
The rejection above is our task-design inference from the equation, not a claim
made by the source. Dimensionless synthetic development below is not a realistic
field seismic simulator (no amplitudes, multiples, picking errors or attenuation).

## Next bounded witness: model validity under changing aperture

Compare a homogeneous reflector to a two-layer reflected ray. Keep horizontal
layers, isotropic positive velocities and exact picked bottom-reflection times.
For ray parameter p in [0,1/max(v)), define
x(p)=2 sum h_i p v_i /sqrt(1-p²v_i²),
t(p)=2 sum h_i /(v_i sqrt(1-p²v_i²)).
Solve x(p)=requested x monotonically with a bounded root solver. No branch or
arrival-selection ambiguity will be introduced as artificial difficulty.

Exposed fixture fixed before numerical work:
- layered h=[.5,1.5],v=[1,3]; homogeneous h=v=sqrt(5).
- Both have normal-incidence time2 and the same small-offset quadratic coefficient
  (RMS velocity sqrt5). They need not agree exactly at finite small offsets.
- Offsets[0,.1,.5,1,2,4], one evaluation per model,6readouts each.
- At most100root iterations per nonzero layered offset, absolute tolerance1e-10.
- Validate homogeneous limit, even symmetry, positive time and independent
  minimum-path calculation. No noise draws, fitting, seeds or model calls yet.
- Report residuals and solver work, including failures. Do not infer unique layer
  recovery: even exact bottom-reflection travel times can leave structural
  equivalences. Layer permutation is an explicit potential unresolved regime.

Proposed legal action is changing acquisition aperture, not changing underground
parameters. Candidate could test the validity range of a fitted hyperbola. Gate:
large-offset model rejection must exceed a declared measurement precision while
small-offset agreement is quantified, not asserted. Next implement only this
operator witness. Full World remains deferred until a distinct multilayer task,
finite experimental budget and non-unique interpretations are specified.
