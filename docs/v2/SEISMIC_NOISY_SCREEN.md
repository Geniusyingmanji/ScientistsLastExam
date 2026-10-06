# Seismic noisy transfer screen — frozen 2026-10-07

Exposed layered fixture unchanged: h=[.5,1.5],v=[1,3]. This is development,
not held-out geology. Synthetic independent additive Gaussian noise SD=.001,
no clipping. Source offsets[0,.1,.25,.5], target offsets[1,2,4]. Seed12007.
One source acquisition(4readouts), one target acquisition(3readouts); each calls
the exact layered kernel once. Fit one homogeneous hyperbola sqrt(a+b*x²)
by bounded least_squares, a in[.01,100],b in[.01,100], start[4,.2],max_nfev100.
Hard cap500model function calls, count all calls including numerical derivatives;
no restarts, retries or tuning. Freeze fitted coefficients before target noise.
Empirical baseline: constant mean source time; author reference: exact fixed
layered parameters (privileged, no inference). Compare source residual and target
RMSE against fresh noisy measurements; no significance/power or discovery claim.
Maximum2kernel calls/7readouts,500analytic fit calls, no model API calls.

## Observed result
Two kernel calls/7readouts,9fit calls; no retries. Source fit RMSE .0003411.
Fresh-target RMSE: constant source mean .3777632, fitted homogeneous .0583725,
known-parameter layered reference .0009679. Fit was saved before target noise.
This one fixture demonstrates a near-aperture fit with poor farther-aperture
prediction. It does not isolate structural mismatch from source-noise parameter
uncertainty, establish universal identifiability, or measure agent discovery.
Author reference knows true parameters; its near-noise error is not learned
mechanism recovery. Candidate remains operator witness, not registered World.
Next test source-fit uncertainty and multiple predeclared development fixtures
before increasing implementation scope. Preserve this run, no retuning.
