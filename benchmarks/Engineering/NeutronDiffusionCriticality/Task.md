# NeutronDiffusionCriticality — optimize reactor fuel loading for maximum k-effective

## Scientific background
The neutron multiplication factor k_eff determines whether a nuclear reactor is critical
(self-sustaining chain reaction). Optimizing the spatial distribution of fuel enrichment
across reactor zones to maximize k_eff — subject to average enrichment constraints (fuel
cost/safety) — is a core nuclear engineering challenge. The physics is governed by the
two-group neutron diffusion equation, solved as an eigenvalue problem via power iteration.

Reference: Duderstadt & Hamilton, Nuclear Reactor Analysis (1976); Yamamoto et al. (2002).

## Your task
```python
def optimize_enrichment(n_zones, avg_max):
    \"\"\"Return enrichment values (n_zones,) in [0.02, 0.20] with mean <= avg_max.
    Goal: maximize k_eff of the 1D slab reactor.\"\"\"
```

## Scoring
`score = clip((k - k_uniform) / (k_reference - k_uniform), 0, 1)`, where the flat 5%
loading gives `k_uniform = 0.984179` and a reproducible constrained numerical witness gives
`k_reference = 1.059182`. The reference uses low enrichment near the leaking boundaries and
concentrates fuel toward the high-importance central region. It is a calibration witness, not a
claim of a globally proved physical optimum.

## Rules
- Only edit `solution.py`. numpy/scipy only. CPU. Do not read `verification/`.
