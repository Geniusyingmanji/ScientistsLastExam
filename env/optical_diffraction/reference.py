"""Independent operator-only pair-cosine reference; no production imports."""
import math


def _finite(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("real JSON number required")
    try:
        value = float(value)
    except (ValueError, OverflowError) as exc:
        raise ValueError("finite number required") from exc
    if not math.isfinite(value):
        raise ValueError("finite number required")
    return value


def pair_intensity(parameters, spec):
    if not isinstance(parameters, dict) or set(parameters) != {"positions_um", "weights", "tags"}:
        raise ValueError("independent reference requires raw parameter fields")
    x = [_finite(v) for v in parameters["positions_um"]]
    weights = [_finite(v) for v in parameters["weights"]]
    tags = list(parameters["tags"])
    if not 1 <= len(x) <= 7 or len(weights) != len(x) or len(tags) != len(x):
        raise ValueError("invalid reference lengths")
    if any(abs(v) > 3 for v in x) or any(b <= a for a, b in zip(x, x[1:])) or any(w <= 0 for w in weights) or abs(math.fsum(weights)-1) > 1e-12 or any(t not in ("A", "B") for t in tags):
        raise ValueError("invalid reference state")
    if not isinstance(spec, dict) or not {"angles_rad", "wavelength_um"} <= set(spec) or set(spec)-{"angles_rad", "wavelength_um", "contrast_b"}:
        raise ValueError("invalid reference spec fields")
    if not isinstance(spec["angles_rad"], list) or not 1 <= len(spec["angles_rad"]) <= 65:
        raise ValueError("invalid angle count")
    angles = [_finite(v) for v in spec["angles_rad"]]
    wavelength, contrast = _finite(spec["wavelength_um"]), _finite(spec.get("contrast_b", 1))
    if any(abs(v) > .4 for v in angles) or any(b <= a for a, b in zip(angles, angles[1:])) or not .5 <= wavelength <= 1.5 or not -1 <= contrast <= 1:
        raise ValueError("invalid reference public controls")
    amplitudes = [w if tag == "A" else contrast*w for w, tag in zip(weights, tags)]
    rows = []
    for angle in angles:
        q = 2*math.pi*math.sin(angle)/wavelength
        terms = [a*a for a in amplitudes]
        for j in range(len(x)):
            for k in range(j):
                terms.append(2*amplitudes[j]*amplitudes[k]*math.cos(q*(x[j]-x[k])))
        result = math.fsum(terms)
        if not math.isfinite(result):
            raise RuntimeError("reference became nonfinite")
        rows.append([result])
    return rows


def analytic_single(spec):
    return [[1.] for _ in spec["angles_rad"]]


def analytic_doublet(spec):
    """Specific fixed x=[-.5,.5], w=.5 and A/B labels only."""
    c = spec["contrast_b"]
    return [[.25*(1+c*c+2*c*math.cos(2*math.pi*math.sin(t)/spec["wavelength_um"]))] for t in spec["angles_rad"]]
