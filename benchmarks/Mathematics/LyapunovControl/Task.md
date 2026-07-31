# LyapunovControl — stabilize the chaotic Lorenz system with minimal control

## Scientific background
The Lorenz system (σ=10, ρ=28, β=8/3) exhibits deterministic chaos with a maximum Lyapunov
exponent (MLE) ≈ 0.9, meaning nearby trajectories diverge exponentially. Controlling chaos —
making MLE negative (stable) — with minimal energy is fundamental to nonlinear dynamics,
turbulence control, and secure communications. The OGY method (1990) showed even small
perturbations can stabilize unstable periodic orbits.

Reference: Ott, Grebogi & Yorke, PRL 64, 1196 (1990); Pyragas, Phys. Lett. A 170, 421 (1992).

The benchmark implements a sampled-data controller: `controller(state)` is evaluated at every
`dt=0.01` integration step and that control is held constant during the step. The evaluator
estimates the closed-loop MLE by evolving and periodically renormalizing two nearby controlled
trajectories. Consequently, nonlinear, clipped and piecewise feedback is evaluated without
assuming an analytic controller Jacobian. The returned controller must be a deterministic,
memoryless function of its supplied state; hidden mutable state would make the paired local
stability experiment ill-defined.

## Your task
```python
def design_controller(sigma, rho, beta):
    \"\"\"Return a callable controller(state) -> control_vector (3,).
    Control is added to the Lorenz equations: dx/dt = f(x) + u(x).
    Constraint: average ||u||^2 <= 50 over the trajectory.\"\"\"
```

## Scoring
`score = clip((MLE_uncontrolled - MLE_controlled) / (MLE_uncontrolled - (-0.5)), 0, 1)`
Full stabilization (MLE = -0.5) → score 1.0. Uncontrolled MLE ≈ 0.9 → score 0.

## Rules
- Only edit `solution.py`. numpy/scipy only. CPU. Do not read `verification/`.
