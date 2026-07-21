# InvertedPendulumSwingUp — swing up and robustly stabilize a cart-pole

## Scientific background

Cart-pole swing-up is a canonical nonlinear-control problem. A controller must first inject
energy to move the pendulum from its stable hanging equilibrium into the neighborhood of the
unstable upright equilibrium, then switch to a stabilizing feedback law while keeping the cart
inside its track and limiting actuator effort. Standard solutions combine energy shaping with
LQR or another local controller.

The public coordinate convention is:

- `theta = 0`: pendulum hanging down (stable without control);
- `theta = pi`: pendulum upright (open-loop unstable).

The nominal plant has cart mass 1.0 kg, pendulum mass 0.1 kg, pendulum length 1.0 m, cart
friction 0.05 and joint friction 0.005. The force limit is 10 N, controller interval is 0.02 s,
episode duration is 20 s and cart travel is limited to `|x| <= 5 m`.

For state `(x, x_dot, theta, theta_dot)` and commanded force `F`, the nominal continuous
dynamics are exactly

```text
total = cart_mass + pendulum_mass
temp = (F - cart_friction*x_dot
        - pendulum_mass*length*theta_dot**2*sin(theta)) / total
denom = length * (4/3 - pendulum_mass*cos(theta)**2/total)
theta_ddot = (-g*sin(theta) + cos(theta)*temp
              - joint_friction*theta_dot/(pendulum_mass*length)) / denom
x_ddot = temp + pendulum_mass*length*theta_ddot*cos(theta)/total
```

The `4/3` factor is part of the benchmark plant and must not be replaced by a point-mass
pendulum model. The trusted simulator applies two RK4 substeps per controller interval and clips
the commanded force to `[-10, 10]` N.

References: Åström & Furuta, *Automatica* 36, 287–295 (2000),
doi:10.1016/S0005-1098(99)00140-5; Tedrake, *Underactuated Robotics*.

## Your task

```python
def swing_up_controller(state, t, dt):
    """Return cart force in newtons for state (x, x_dot, theta, theta_dot)."""
```

The same controller is evaluated from several initial states. If using mutable internal state,
reset it whenever `t == 0`.

## Scoring

The development score combines time balanced near upright, terminal stabilization, RMS command
force and RMS cart displacement. The evaluator separately reports robustness under hidden plant
parameter shifts and bounded external-force pulses; robustness is not folded into the
optimization score.

## Rules

- Only edit `solution.py`. numpy/scipy only. CPU. Do not read `verification/`.
