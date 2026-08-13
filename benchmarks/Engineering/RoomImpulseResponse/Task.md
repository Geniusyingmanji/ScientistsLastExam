# RoomImpulseResponse — robust room-acoustic treatment design

## Scientific background

Room impulse responses couple source placement, boundary absorption and receiver layout. For
speech-oriented rooms, useful treatment must balance three different outcomes: early-to-late
energy ratio (clarity), reverberation time, and level uniformity over the occupied area. A
first-order reflection proxy can rank designs differently from a longer-horizon image-source
calculation, while installation error, material ageing and geometry uncertainty can erase a
nominal gain.

This benchmark uses an energy image-source model and octave-band Eyring decay. It is a
reduced-order architectural-acoustics optimization task, not a claim of wave-resolved or
measurement-grade prediction.

## Your task

Implement one policy for rooms with different dimensions, receiver grids, surface materials,
treatment budgets and target reverberation-time curves:

```python
def design_room(problem):
    """Return one finite vector with nine real entries."""
```

The entries are, in order:

```text
[source_x_m, source_y_m, source_z_m,
 treatment_area_x0_m2, treatment_area_x1_m2,
 treatment_area_y0_m2, treatment_area_y1_m2,
 treatment_area_floor_m2, treatment_area_ceiling_m2]
```

The public `problem` gives source-position bounds, receiver locations, six surface areas,
octave-band untreated and porous-treatment absorption, the total material budget, per-surface
coverage limits, target reverberation times, and the nominal image order. Values outside the
contract are rejected rather than clipped.

## Evaluation

For each receiver and octave band, the trusted evaluator enumerates specular image paths,
multiplies energy reflection coefficients by wall-hit counts, applies geometric spreading and
air loss, and separates energy in the first 50 ms after the direct arrival. It also computes
Eyring reverberation time from the treated surface coefficients. The nominal utility is

```text
0.46 * clarity utility
+ 0.34 * target-RT utility
+ 0.20 * spatial-uniformity utility.
```

`combined_score` is the mean development utility improvement over a valid weak policy,
normalized by independently and deterministically optimized family witnesses. The same policy is called
on interleaved held-out rooms. The evaluator separately retains:

- clarity, reverberation-time error and level-uniformity axes;
- a first-order reflection proxy versus the order-10 nominal oracle;
- held-out-room transfer; and
- worst-case utility over source installation error, receiver-layout changes, geometry and
  sound-speed uncertainty, material ageing, and a combined order-14 horizon shift.

Nominal and robust references are reproducible anchors in a transparent bounded family, not
global optima. Better valid designs are allowed and clip at one. Each room receives a fresh
candidate process and private temporary filesystem; held-out and shifted metrics are sealed
from proposal feedback.

## Scope and rules

- Only edit `solution.py`; keep `design_room(problem)`.
- Use deterministic Python/NumPy/SciPy CPU code only.
- Handle the supplied public room instead of hard-coding one artifact.
- No network or process creation. Do not read `verification/` or `frontier_eval/`.

The oracle assumes a rectangular room, frequency-banded energy reflections and locally mixed
surface treatment. It omits phase interference, diffraction, scattering, seat-by-seat occupancy,
nonuniform patch placement and coupled structural response. Engineering claims require hybrid
wave/ray simulation and measured RIR replication.

References: Allen & Berkley, *JASA* 65(4), 943–950 (1979), doi:10.1121/1.382599; Lehmann &
Johansson, *IEEE TASLP* 16(4), 742–752 (2008), doi:10.1109/TASL.2008.917341; ISO 3382-1:2009,
*Acoustics—Measurement of room acoustic parameters—Part 1: Performance spaces*.


## Inputs the candidate receives

Every key the baseline reads off the input mapping. Names are part of the contract: a candidate
that reaches for one of these quantities under a different name raises at runtime and scores
nothing, and that zero cannot be told apart from a zero earned on the science.

| key | |
|---|---|
| `maximum_treatment_area_m2` | previously undocumented |
| `maximum_treatment_fraction_by_surface` | previously undocumented |
| `source_position_bounds_m` | previously undocumented |
| `surface_areas_m2` | previously undocumented |

A key not listed here may still exist; this table is what the shipped baseline uses.
