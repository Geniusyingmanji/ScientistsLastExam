# LowThrustTransfer — design transferable finite-thrust orbit transfers

## Scientific background

Electric propulsion trades small thrust for high specific impulse.  A useful trajectory policy
must steer for many revolutions, trade terminal orbit accuracy against propellant, and remain
valid across raising, lowering, eccentricity and plane-change missions.  Direct trajectory
optimization commonly parameterizes a bounded control and propagates the dynamics; see Betts,
*Journal of Guidance, Control, and Dynamics* 21, 193–207 (1998),
doi:10.2514/2.4231, and Conway (ed.), *Spacecraft Trajectory Optimization* (2010),
doi:10.1017/CBO9780511778025.  The public state uses Walker modified equinoctial elements
(MEE), doi:10.1007/BF01227493, which avoid the circular/equatorial singularities of classical
elements in this prograde regime.

The state is

```text
y = (p, f, g, h, k, L, mass)
```

where `p` is semilatus rectum in metres, `(f,g)` encode eccentricity,
`(h,k)` encode inclination and ascending node, and `L` is true longitude in radians.  With
local radial/transverse/normal acceleration `(a_r,a_t,a_n)`, define

```text
w = 1 + f*cos(L) + g*sin(L)
s2 = 1 + h*h + k*k
q = h*sin(L) - k*cos(L)
root = sqrt(p / mu)

p_dot = root * 2*p/w * a_t
f_dot = root * (a_r*sin(L) + ((w+1)*cos(L)+f)/w*a_t - q*g/w*a_n)
g_dot = root * (-a_r*cos(L) + ((w+1)*sin(L)+g)/w*a_t + q*f/w*a_n)
h_dot = root * s2/(2*w) * cos(L)*a_n
k_dot = root * s2/(2*w) * sin(L)*a_n
L_dot = sqrt(mu*p)*(w/p)**2 + root*q/w*a_n
mass_dot = -maximum_thrust*norm(u)/(specific_impulse*g0)
```

The nominal Earth model uses `mu = 3.986004418e14 m^3/s^2`, equatorial radius
`R = 6378137 m`, `J2 = 1.08262668e-3` and `g0 = 9.80665 m/s^2`.  For Cartesian position
`(x,y,z)` and radius `r`, the trusted propagator adds

```text
factor = 1.5*J2*mu*R**2/r**5
a_J2 = factor * (x*(5*z**2/r**2-1),
                 y*(5*z**2/r**2-1),
                 z*(5*z**2/r**2-3))
```

and integrates the same documented model for every policy.

## Your task

Implement one policy that returns four segments of harmonic local-frame guidance:

```python
def design_guidance(initial_elements, target_elements, initial_mass_kg,
                    maximum_thrust_n, specific_impulse_s, duration_s, n_segments):
    """Return a finite real array with shape (n_segments, 7)."""
```

For each segment, a row

```text
(t0, r_sin, r_cos, t_sin, t_cos, n_sin, n_cos)
```

defines normalized thrust components at true longitude `L`:

```text
u_r = r_sin*sin(L) + r_cos*cos(L)
u_t = t0 + t_sin*sin(L) + t_cos*cos(L)
u_n = n_sin*sin(L) + n_cos*cos(L)
```

The physical acceleration is `maximum_thrust/mass * u`.  Every coefficient must lie in
`[-1.25,1.25]`, and `norm(u) <= 1` for every longitude, not merely at sample points.  Invalid
controls are rejected; they are never clipped or repaired.

## Constraints and scoring

- The osculating perigee altitude must remain at least 150 km.
- Eccentricity must remain below 0.85 and mass above 50% of the initial mass.
- Terminal orbit error uses the first five MEE components.  Public one-sigma-like scales are
  `max(50 km, 0.006*p_target)` for `p`, `0.008` for each of `f,g`, and `0.004` for each of
  `h,k`.
- Terminal accuracy is `exp(-mean(scaled_error**2)/2)`.  A mission is terminal-feasible when
  every absolute scaled error is at most one; the development feasibility rate is visible
  separately from the graded objective.
- Propellant efficiency is `exp(-delta_v/2000)`, with delta-v in m/s from the rocket equation.
- Utility is terminal accuracy times propellant efficiency.  `combined_score` normalizes
  development utility between the valid coast baseline and the ideal value one.

The trusted report separately retains terminal phase, held-out mission families, and robustness
under small thrust, specific-impulse, J2, pointing, navigation and cutoff deviations.  These
metrics do not influence proposal feedback or parent selection.

## Rules

- Only edit `solution.py`; keep the `design_guidance` signature.
- Deterministic CPU code using Python, NumPy and SciPy only; no network or process creation.
- Do not read `verification/` or `frontier_eval/`.
