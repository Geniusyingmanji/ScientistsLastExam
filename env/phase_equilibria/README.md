# Phase equilibria and preparation history

Status: experimental package; campaign inclusion and shared registration are
tracked separately. A fresh binary material sample is prepared for every query.
The Agent controls overall composition, preparation route, hold time, loading,
and diffraction angles; it measures a continuous noisy intensity spectrum.
The public apparatus is defined by `World.describe()`, not this operator README.

A rich spectrum need not imply a new phase: it can combine neighboring phases.
A changing spectrum can also contain precursor remnants, and a small constant
peak can originate in the holder. Composition scans, alternative preparations,
longer holds and empty-holder controls let investigators test those explanations.
No phase name or exact phase set is accepted as a golden answer. Evidence comes
from executable predictions of new spectra and contrasts fixed before observation.

## Interface

```python
from env.phase_equilibria.world import World, baseline
world = World(71)  # operator-only instance creation
spec = {"composition": 0.45, "hold_time": 40, "preparation": "powder_blend",
        "loading": 1, "angles_deg": list(range(10, 91))}
observation = world.run(spec, noise_key="independent-measurement")
```

The axis is `angles_deg`; the only channel is `intensity`, normalization 1,
independent additive Gaussian readout standard deviation 0.003, without clipping.
There are 1–241 requested angles in [10,90] degrees and hold times in [0,120]
apparatus units. `loading=0` returns the unknown holder response. None of the
readouts are directly assigned, including preparation time and empty-holder data.
Experiments reset preparation and never carry hidden state between calls.

The empirical baseline selects the closest public preparation/composition/hold/
loading record and interpolates its angle grid; it has no parameter or family
access. Without data it predicts zero. It is an engineering comparison, not an
author-informed proof of identifiability or difficulty.

See `SCIENTIFIC_NOTES.md` for the private generative assumptions and limits,
`DEVELOPMENT_PLAN.md` for checks fixed before development diagnostics, and
`tests/test_phase_equilibria_world.py` for independent numerical checks.

## Migration limits

This replaces the legacy PhaseDiagramDiscovery peak-list and exact-phase-set
evaluator with a fixed-size intensity response and executable prediction tests.
It deliberately does not migrate its random impurities, peak censoring, or
call-index-dependent trapped mixtures. Here the holder is fixed, and the
explicit deterministic relaxation preserves composition. Repeat measurements
estimate readout uncertainty; they do not sample stochastic preparation failures.
Finite-time agreement cannot establish equilibrium or unique crystal structures.
