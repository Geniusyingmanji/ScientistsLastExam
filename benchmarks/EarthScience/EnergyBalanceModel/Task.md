# EnergyBalanceModel-v2 — identify climate response by choosing forcing experiments

## Scientific problem

Idealized energy-balance models separate radiative feedback from ocean heat uptake.  You control
external radiative forcing and observe annual global-mean surface-temperature anomaly and
top-of-atmosphere energy imbalance.  When the public two-layer model is supported, recover its
five parameters.  When the response is null or requires state-dependent feedback or another
ocean layer, abstain rather than force a misleading two-layer explanation.

The public model uses one-year piecewise-constant forcing `F(t)`:

```text
C_s dT_s/dt = q F(t) - lambda T_s - gamma (T_s - T_d)
C_d dT_d/dt = gamma (T_s - T_d)
N(t)         = q F(t) - lambda T_s
```

The parameters and public bounds are:

```text
lambda : radiative feedback             [0.80, 2.20] W m^-2 K^-1
C_s    : surface-layer heat capacity    [6, 15]       W yr m^-2 K^-1
C_d    : deep-ocean heat capacity       [70, 180]     W yr m^-2 K^-1
gamma  : ocean heat-exchange coefficient[0.35, 1.20]  W m^-2 K^-1
q      : effective-forcing scale        [0.85, 1.15]
```

## Artifact and experiment API

Implement:

```python
def identify_climate_response(parameter_names, parameter_bounds, experiment, budget_units):
    """Return a dict with:
      parameters: five finite values in parameter_names order
      confidence: scalar in [0,1] for the returned parameter claim or refusal
      abstain: bool; True means the public two-layer family is unsupported

    experiment(forcing_w_m2) returns a dict containing:
      time_years
      forcing_w_m2
      surface_temperature_anomaly_k
      toa_imbalance_w_m2
      surface_noise_std_k
      toa_noise_std_w_m2
      budget_cost
      budget_used
    """
```

Each forcing array represents 12–160 annual intervals and must stay in `[-1,8] W m^-2`.  A call
costs `ceil(number_of_years/20)` units; the complete per-world budget is 8 units.  Invalid or
over-budget calls invalidate that world even when caught by candidate code.  Fresh laboratories
are deterministic, while repeated calls receive distinct noise realizations.  Every call is an
independent experiment initialized at `T_s = T_d = 0`; model state never carries between calls.

## Evaluation

- `combined_score` measures parameter/mechanism recovery plus correct refusal on development
  worlds, normalized so always abstaining scores zero.
- Public-model prediction under sealed abrupt/ramp forcing and under negative, pulse and
  oscillatory forcing remains evaluator-only, as do held-out worlds.
- Supported-world claim coverage, false discovery, unsupported-world refusal, confidence,
  experiment count and budget use are reported separately.
- Development and held-out worlds include supported two-layer responses, null responses,
  state-dependent radiative feedback and three-layer ocean uptake.  The kind is never supplied.

This is controlled system identification in a synthetic climate emulator.  It does not infer
Earth's climate sensitivity, validate a general circulation model or establish a physical
climate discovery.

## Rules

- Only edit `solution.py`; keep the `identify_climate_response` signature.
- Deterministic CPU code using Python, NumPy, SciPy and the standard library only.
- Do not assume world order, parameter values, noise realization or response kind.
- No network or process creation. Do not read `verification/` or `frontier_eval/`.

## References

- North, Cahalan and Coakley, *Energy balance climate models*, Reviews of Geophysics 19(1),
  91–121 (1981), DOI `10.1029/RG019i001p00091`.
- Geoffroy et al., *Transient Climate Response in a Two-Layer Energy-Balance Model. Part I*,
  Journal of Climate 26(6), 1841–1857 (2013), DOI `10.1175/JCLI-D-12-00195.1`.
- Gregory et al., *A new method for diagnosing radiative forcing and climate sensitivity*,
  Geophysical Research Letters 31(3) (2004), DOI `10.1029/2003GL018747`.
