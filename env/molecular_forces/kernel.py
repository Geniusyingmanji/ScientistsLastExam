"""Private effective potentials and conservative Cartesian forces.

No benchmark evaluator imported. Complex-step differentiation is analytic to
machine precision for this smooth, nonconjugating energy implementation. This
is a constrained static apparatus, not molecular dynamics.
"""
import hashlib
import numpy as np

STRATA = ("pair", "three_body", "temperature_dependent")


def make_instance(seed):
    rng = np.random.default_rng(seed)
    digest = hashlib.sha256(("molecular-forces-structure-v1:%d" % seed).encode()).digest()
    stratum = STRATA[digest[0] % len(STRATA)]
    family = "lj" if digest[1] % 2 == 0 else "morse"
    params = {"family": family, "depth": float(rng.uniform(.075, .138)),
              "length": float(rng.uniform(2.68, 3.17)), "inverse_range": float(rng.uniform(1.42, 2.08)),
              "three_body": 0., "temperature_coefficient": 0., "stratum": stratum}
    if family == "morse":
        params["length"] = float(rng.uniform(2.84, 3.31))
    if stratum == "three_body":
        params["three_body"] = float(rng.uniform(150., 285.))
    if stratum == "temperature_dependent":
        params["temperature_coefficient"] = float(rng.choice([-1., 1.]) * rng.uniform(.19, .29))
    return params


def energy(positions, temperature, params):
    # np.linalg.norm would conjugate complex coordinates, breaking the analytic
    # extension used below. All products here deliberately omit conjugation.
    p = np.asarray(positions)
    distances = np.asarray([np.sqrt(np.sum((p[i] - p[j]) ** 2)) for i, j in ((0, 1), (0, 2), (1, 2))])
    depth, length = params["depth"], params["length"]
    if params["family"] == "lj":
        z = (length / distances) ** 6
        pair = np.sum(4 * depth * (z * z - z))
    elif params["family"] == "morse":
        z = np.exp(-params["inverse_range"] * (distances - length))
        pair = np.sum(depth * (z * z - 2 * z))
    else:
        raise RuntimeError("invalid private potential")
    pair *= 1 + params["temperature_coefficient"] * (temperature - 450.) / 450.
    x, y, z = distances
    c0 = (x*x + y*y - z*z) / (2*x*y)
    c1 = (x*x + z*z - y*y) / (2*x*z)
    c2 = (y*y + z*z - x*x) / (2*y*z)
    return pair + params["three_body"] * (1 + 3*c0*c1*c2) / (x*y*z) ** 3


def energy_forces(positions, temperature, params):
    positions = np.asarray(positions, dtype=float)
    value = float(energy(positions, temperature, params))
    forces = np.empty((3, 3))
    h = 1e-25
    for i in range(3):
        for j in range(3):
            perturbed = positions.astype(complex)
            perturbed[i, j] += h * 1j
            forces[i, j] = -float(np.imag(energy(perturbed, temperature, params))) / h
    if not np.isfinite(value) or not np.isfinite(forces).all():
        raise RuntimeError("force calculation failed")
    return value, forces
