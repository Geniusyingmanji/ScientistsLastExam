"""Private bounded complex-amplitude single-scattering kernel."""
from dataclasses import dataclass
import cmath
import math

from .protocol import validate_spec

_complex_exponential = cmath.exp


@dataclass(frozen=True)
class Parameters:
    positions_um: tuple
    weights: tuple
    tags: tuple

    def __post_init__(self):
        x, w, tags = self.positions_um, self.weights, self.tags
        if any(not isinstance(items, (list, tuple)) for items in (x, w, tags)) or not 1 <= len(x) <= 7 or len(w) != len(x) or len(tags) != len(x):
            raise ValueError("expected 1..7 matched sites, weights and tags")
        for values in (x, w):
            if any(isinstance(v, bool) or not isinstance(v, (int, float)) for v in values):
                raise ValueError("parameters must be finite real numbers")
        try:
            x, w, tags = tuple(map(float, x)), tuple(map(float, w)), tuple(tags)
        except (ValueError, OverflowError) as exc:
            raise ValueError("parameters must be finite real numbers") from exc
        if any(not math.isfinite(v) for values in (x, w) for v in values):
            raise ValueError("parameters must be finite real numbers")
        if any(not -3 <= v <= 3 for v in x) or any(b <= a for a, b in zip(x, x[1:])):
            raise ValueError("positions must be distinct, sorted and in [-3,3]")
        if any(v <= 0 for v in w) or abs(math.fsum(w)-1) > 1e-12 or any(t not in ("A", "B") for t in tags):
            raise ValueError("positive normalized weights and A/B tags required")
        object.__setattr__(self, "positions_um", x)
        object.__setattr__(self, "weights", w)
        object.__setattr__(self, "tags", tags)

    def as_dict(self):
        return {"positions_um": list(self.positions_um), "weights": list(self.weights), "tags": list(self.tags)}


class Kernel:
    MAX_EXPONENTIALS = 455
    BOUND_TOLERANCE = 3e-12

    def __init__(self, parameters):
        if not isinstance(parameters, Parameters):
            raise ValueError("expected validated Parameters")
        self.parameters = parameters

    def intensity(self, spec):
        spec = validate_spec(spec)
        required = len(spec["angles_rad"]) * len(self.parameters.positions_um)
        if required > self.MAX_EXPONENTIALS:
            raise RuntimeError("optical exponential work budget exhausted")
        amplitudes = [w * (1 if tag == "A" else spec["contrast_b"]) for w, tag in zip(self.parameters.weights, self.parameters.tags)]
        rows, calls = [], 0
        for angle in spec["angles_rad"]:
            q = 2 * math.pi * math.sin(angle) / spec["wavelength_um"]
            terms = []
            for amplitude, position in zip(amplitudes, self.parameters.positions_um):
                terms.append(amplitude * _complex_exponential(1j*q*position))
                calls += 1
            field = complex(math.fsum(v.real for v in terms), math.fsum(v.imag for v in terms))
            value = field.real**2 + field.imag**2
            if not math.isfinite(value):
                raise RuntimeError("optical intensity became nonfinite")
            if value < -self.BOUND_TOLERANCE or value > 1 + self.BOUND_TOLERANCE:
                raise RuntimeError("optical intensity left calibrated bounds")
            rows.append([value])
        return rows, {"complex_exponential_evaluations": calls, "sample_count": len(rows)}
