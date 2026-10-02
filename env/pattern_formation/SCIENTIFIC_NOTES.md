# Operator scientific specification

This is a one-dimensional, deterministic, phenomenological adaptation of the finite-wave-number instability model associated with J. Swift and P. C. Hohenberg, *Hydrodynamic fluctuations at the convective instability*, Physical Review A **15**, 319 (1977), [DOI and original publication](https://journals.aps.org/pra/abstract/10.1103/PhysRevA.15.319); [author-paper scan hosted by UC San Diego](https://courses.physics.ucsd.edu/2017/Spring/physics221a/Swift-Hohenberg.pdf). Their paper treats thermal fluctuations near convection. The present world removes process fluctuations, uses an artificial one-dimensional ring and adds an optional anchored spatial forcing. It is not a reproduction of their full physical setting.

On 64 equally spaced periodic sites, the authoritative finite-dimensional dynamics are

```
du/dt = (r0 + gain*drive) u - (q0² + Dxx)² u - cubic*u³
        + forcing*cos(2*pi*forcing_mode*j/64 + forcing_phase).
```

`Dxx` is the Fourier collocation second derivative. The pointwise cubic uses the same grid without de-aliasing. This defines a particular 64-dimensional ODE; no claim of a converged continuum PDE is made. Probe `j` samples site `4*j`. Increasing ring length changes physical wave numbers `2*pi*k/length` while preserving site count and the forcing's integer number of periods. Its phase remains anchored to the apparatus origin.

For an unforced zero state, the linear growth eigenvalue for mode `k` is

```
lambda(k) = r0 + gain*drive - (q0² - (2*pi*k/length)²)².
```

A positive control coefficient does not guarantee an available growing mode on every finite ring. The cubic term saturates growth at finite amplitude. With no forcing, exact zero is invariant even if an accessible mode has a positive eigenvalue: no hidden process noise seeds a pattern. Readout noise changes neither initial state nor subsequent dynamics.

Three operator strata alter mechanism structure: positive `r0` without forcing, negative `r0` without forcing and nonzero anchored forcing with negative `r0` at zero drive. These labels are sampling metadata. In the forced stratum positive drive can also create linear instability; “forced” and “unstable” are not mutually exclusive explanations over all conditions. Source or prediction accuracy does not by itself identify the stratum or eliminate flexible alternatives.

The symmetric spectral linear operator and local cubic term commute with discrete grid translations. Continuous translation equivalence is only an approximation for this collocation world because aliasing can break it. The checked exact symmetry is a shift by four grid sites, equivalent to one probe. An anchored forcing generally breaks this symmetry unless the shift happens to be a period of that particular forcing. The numerical checks compare positive-time outputs after matching the assigned reset shift; time-zero differences are not evidence of dynamics.

With constant controls this finite ODE is a gradient flow. If `A` is its symmetric linear matrix and `f` the fixed forcing vector, the discrete potential `V=-uᵀAu/2 + cubic*sum(u⁴)/4 - fᵀu` obeys `dV/dt=-||du/dt||²`. The positive quartic term bounds its sublevel sets, providing a dissipative large-amplitude constraint. This statement concerns the clean internal state; sparse noisy readouts need not exhibit a monotone estimated potential. It does not certify the solver numerically for all allowed inputs.

Production integration uses SciPy BDF with an analytic Jacobian, relative tolerance `1e-8`, absolute tolerance `1e-10`, maximum step `0.5 T`, at most 12,000 RHS and 1,000 Jacobian evaluations. A nonfinite state or internal magnitude above 8 causes an explicit failure. These limits bound work or fail closed rather than clipping trajectories. An independent Radau reference evaluates the linear part with FFTs and tighter tolerances; it checks the same finite ODE, not continuum convergence.

The completed same-family provisional review independently reconstructed the linear matrix from a real trigonometric basis and checked public reset, sampling and noise semantics. Its 42 trajectory attempts contained 36 completions, three expected cap failures and three unexpected failures. A production corner (`r0=.32`, `gain=.7`, `q0=.85`, `cubic=.8`, forcing `.07` in mode 2 at phase pi; L=12 and drive=.4) exhausted the Jacobian cap. This constructor-valid cross-stratum combination is outside generated support. Three fixed generated-stratum endpoint checks at the same public controls completed. Two reviewer real-basis Radau calls also exhausted their own RHS cap; those comparisons remain unresolved. These outcomes limit numerical-availability claims and were preserved before registration. They do not alter the dynamics or provide a generator-wide reliability estimate.

The tenth-world integration followed the independent review as a separate implementation phase. Its shared policy declares a 0.25 T minimum readout lag after assigned reset, without mid-run event rules; this is pilot eligibility metadata, not a hidden time constant. The review route and acceptance remain `same-family` and `provisional`; registration does not constitute an external scientific acceptance or an automatic discovery-depth grade.

All probes report independent additive Gaussian measurement noise (`0.002 U` standard deviation), including at time zero, with no clipping. Output is signed and the spatial average need not be conserved. Because 16 probes observe 64 sites, some spatial modes alias and a mode-8 sine can be invisible at reset while nonzero between probes. Valid initial assignments and controls are public knowledge; matching them is not a discovery.

Prospective discovery tasks should freeze predictions or rival mechanisms before new observations and preserve failed predictions, ambiguity and condition limits. Broad claims of autonomous pattern formation need more than nonzero final readouts: initial-amplitude, phase, length and drive interventions can test narrower alternatives. This package supplies no automatic mechanism judge or discovery-depth score.
