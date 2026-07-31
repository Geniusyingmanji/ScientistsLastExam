"""Active competing-hypothesis pair-potential laboratory, version 2.

Candidates select three-particle energy/force queries while preregistering a
Mie/Morse/unsupported hypothesis state.  Supported pair laws are scored on
model and parameter recovery, uncertainty, hidden predictions and virial
decisions.  Buckingham, Axilrod--Teller and state-dependent worlds require
refusal.  This is a deterministic reduced-order task calibration, not a real
molecular-dynamics or autonomous-discovery result.
"""

from __future__ import annotations

import hashlib
import math

import numpy as np
from scipy.integrate import quad
from scipy.optimize import brentq, least_squares


FORCE_FIELD_HYPOTHESIS_LAB_V2 = True

PAIR_FAMILIES = ("mie", "morse")
HYPOTHESES = ("mie", "morse", "unsupported")
UNSUPPORTED_KINDS = {"buckingham", "three_body", "state_dependent"}
MINIMUM_RETAINED_WEIGHT = 0.01

PARAMETER_SPECS = {
    "mie": (
        ("epsilon_ev", (0.055, 0.160)),
        ("sigma_a", (2.45, 3.35)),
    ),
    "morse": (
        ("well_depth_ev", (0.055, 0.160)),
        ("inverse_range_per_a", (1.25, 2.25)),
        ("equilibrium_distance_a", (2.75, 3.45)),
    ),
}

DISTANCE_BOUNDS_A = (2.20, 5.40)
COORDINATE_BOUND_A = 5.5
TEMPERATURES_K = (180.0, 450.0, 900.0)
QUERY_BUDGET_UNITS = 24
MAX_BATCH_CONFIGURATIONS = 8
MAX_QUERY_CALLS = 6
FIRST_QUERY_DISTANCE_BOUNDS_A = (3.00, 3.50)
FIRST_QUERY_MAX_CONFIGURATIONS = 1
FIRST_QUERY_MAX_DISTANCE_RATIO = 1.0
FIRST_QUERY_TEMPERATURE_K = 450.0
INTERVAL_CONFIDENCE = 0.90
BOYLE_TEMPERATURE_BOUNDS_K = (900.0, 26000.0)
BOYLE_TEMPERATURE_THRESHOLD_K = 4000.0
VIRIAL_TEMPERATURE_GRID_K = tuple(np.linspace(600.0, 6500.0, 18))
SECOND_VIRIAL_BOUNDS_CM3_MOL = (-5000.0, 5000.0)
ENERGY_NOISE_EV = 3.5e-4
FORCE_NOISE_EV_PER_A = 7.0e-4
BOLTZMANN_EV_PER_K = 8.617333262145e-5
ANGSTROM3_TO_CM3_PER_MOL = 0.602214076

DEVELOPMENT_SPECS = (
    (52011, "mie", 1.00),
    (52021, "morse", 1.00),
    (52027, "mie", 1.25),
    (52039, "morse", 1.20),
    (52051, "buckingham", 1.00),
    (52057, "three_body", 1.10),
    (52067, "state_dependent", 1.05),
)
HELDOUT_SPECS = (
    (62003, "morse", 1.45),
    (62011, "mie", 1.50),
    (62017, "buckingham", 1.35),
    (62029, "three_body", 1.40),
    (62039, "state_dependent", 1.35),
)

SUBMISSION_KEYS = {
    "hypothesis_weights",
    "retained_hypotheses",
    "selected_model",
    "parameters",
    "parameter_intervals",
    "second_virial_cm3_mol_by_temperature",
    "boyle_temperature_k",
    "boyle_temperature_above_threshold",
    "confidence",
    "abstain",
    "evidence_ids",
}
HYPOTHESIS_STATE_KEYS = {"weights", "retained"}


def _token(prefix, *values):
    payload = "|".join(str(value) for value in values).encode("utf-8")
    return prefix + hashlib.sha256(payload).hexdigest()[:16]


def _finite_scalar(value, name):
    if isinstance(value, (bool, np.bool_)) or np.iscomplexobj(value):
        raise ValueError(name + " must be a real-valued non-boolean scalar")
    try:
        scalar = float(value)
    except Exception as exc:
        raise ValueError(name + " must be numeric") from exc
    if not math.isfinite(scalar):
        raise ValueError(name + " must be finite")
    return scalar


def _bounded(value, bounds, name):
    scalar = _finite_scalar(value, name)
    if scalar < bounds[0] or scalar > bounds[1]:
        raise ValueError(name + " outside public bounds")
    return scalar


def _strict_bool(value, name):
    if not isinstance(value, (bool, np.bool_)):
        raise ValueError(name + " must be boolean")
    return bool(value)


def _geometric(values):
    values = [float(np.clip(value, 0.0, 1.0)) for value in values]
    if not values or any(value <= 0.0 for value in values):
        return 0.0
    return float(math.exp(sum(math.log(value) for value in values) / len(values)))


def _entropy(weights):
    values = np.asarray([weights[name] for name in HYPOTHESES], dtype=float)
    values = values[values > 0.0]
    return float(-np.sum(values * np.log(values)))


def _normalize_weights(logits):
    values = np.asarray(logits, dtype=float)
    values -= float(np.max(values))
    probabilities = np.exp(np.clip(values, -60.0, 0.0))
    probabilities = np.maximum(probabilities, 1.0e-9)
    probabilities /= float(np.sum(probabilities))
    return {name: float(probabilities[index])
            for index, name in enumerate(HYPOTHESES)}


def _brier_quality(weights, true_hypothesis):
    squared_error = sum(
        (weights[hypothesis] - float(hypothesis == true_hypothesis)) ** 2
        for hypothesis in HYPOTHESES
    )
    return float(np.clip(1.0 - 0.5 * squared_error, 0.0, 1.0))


def _pair_value_derivative(family, parameters, distance):
    distance = float(distance)
    if family == "mie":
        epsilon, sigma = np.asarray(parameters, dtype=float)
        ratio6 = (sigma / distance) ** 6
        energy = 4.0 * epsilon * (ratio6 * ratio6 - ratio6)
        derivative = 24.0 * epsilon / distance * (ratio6 - 2.0 * ratio6 * ratio6)
        return float(energy), float(derivative)
    if family == "morse":
        depth, inverse_range, equilibrium = np.asarray(parameters, dtype=float)
        exponential = math.exp(-inverse_range * (distance - equilibrium))
        energy = depth * (exponential * exponential - 2.0 * exponential)
        derivative = 2.0 * inverse_range * depth * exponential * (1.0 - exponential)
        return float(energy), float(derivative)
    if family == "buckingham":
        amplitude, inverse_range, dispersion = np.asarray(parameters, dtype=float)
        exponential = math.exp(-inverse_range * distance)
        energy = amplitude * exponential - dispersion / distance**6
        derivative = -amplitude * inverse_range * exponential + 6.0 * dispersion / distance**7
        return float(energy), float(derivative)
    raise ValueError("unknown pair family")


def _pair_energy_forces(family, parameters, coordinates):
    coordinates = np.asarray(coordinates, dtype=float)
    if coordinates.shape != (3, 3):
        raise ValueError("coordinates must have shape (3,3)")
    energy = 0.0
    forces = np.zeros((3, 3), dtype=float)
    for first in range(3):
        for second in range(first + 1, 3):
            delta = coordinates[second] - coordinates[first]
            distance = float(np.linalg.norm(delta))
            value, derivative = _pair_value_derivative(
                family, parameters, distance
            )
            pair_force = derivative * delta / distance
            energy += value
            forces[first] += pair_force
            forces[second] -= pair_force
    return float(energy), forces


def _axilrod_teller_energy(coordinates, coefficient):
    coordinates = np.asarray(coordinates, dtype=float)
    vectors = (
        coordinates[1] - coordinates[0],
        coordinates[2] - coordinates[0],
        coordinates[2] - coordinates[1],
    )
    r01, r02, r12 = [float(np.linalg.norm(vector)) for vector in vectors]
    cos0 = float(np.dot(vectors[0], vectors[1]) / (r01 * r02))
    cos1 = float(np.dot(-vectors[0], vectors[2]) / (r01 * r12))
    cos2 = float(np.dot(-vectors[1], -vectors[2]) / (r02 * r12))
    angular = 1.0 + 3.0 * cos0 * cos1 * cos2
    return float(coefficient * angular / (r01 * r02 * r12) ** 3)


def _axilrod_teller_energy_forces(coordinates, coefficient):
    coordinates = np.asarray(coordinates, dtype=float)
    energy = _axilrod_teller_energy(coordinates, coefficient)
    forces = np.zeros((3, 3), dtype=float)
    step = 2.0e-5
    for particle in range(3):
        for axis in range(3):
            plus = coordinates.copy()
            minus = coordinates.copy()
            plus[particle, axis] += step
            minus[particle, axis] -= step
            forces[particle, axis] = -(
                _axilrod_teller_energy(plus, coefficient)
                - _axilrod_teller_energy(minus, coefficient)
            ) / (2.0 * step)
    forces -= np.mean(forces, axis=0, keepdims=True)
    return energy, forces


def _make_pair_parameters(rng, family):
    if family == "mie":
        return np.asarray((
            rng.uniform(0.075, 0.138),
            rng.uniform(2.68, 3.17),
        ), dtype=float)
    return np.asarray((
        rng.uniform(0.075, 0.138),
        rng.uniform(1.42, 2.08),
        rng.uniform(2.84, 3.31),
    ), dtype=float)


def _make_world(spec):
    seed, kind, noise_scale = int(spec[0]), str(spec[1]), float(spec[2])
    rng = np.random.default_rng(seed)
    world = {
        "seed": seed,
        "kind": kind,
        "noise_scale": noise_scale,
        "energy_noise": ENERGY_NOISE_EV * noise_scale,
        "force_noise": FORCE_NOISE_EV_PER_A * noise_scale,
    }
    if kind in PAIR_FAMILIES:
        world["family"] = kind
        world["parameters"] = _make_pair_parameters(rng, kind)
    elif kind == "buckingham":
        depth = float(rng.uniform(0.078, 0.132))
        equilibrium = float(rng.uniform(2.87, 3.28))
        inverse_range = float(rng.uniform(3.15, 3.75))
        denominator = 1.0 - 6.0 / (inverse_range * equilibrium)
        dispersion = depth * equilibrium**6 / denominator
        amplitude = (
            6.0 * dispersion * math.exp(inverse_range * equilibrium)
            / (inverse_range * equilibrium**7)
        )
        world["family"] = "buckingham"
        world["parameters"] = np.asarray(
            (amplitude, inverse_range, dispersion), dtype=float
        )
    elif kind == "three_body":
        base_family = str(rng.choice(PAIR_FAMILIES))
        world["family"] = base_family
        world["parameters"] = _make_pair_parameters(rng, base_family)
        world["three_body_coefficient_ev_a9"] = float(rng.uniform(150.0, 285.0))
    elif kind == "state_dependent":
        base_family = str(rng.choice(PAIR_FAMILIES))
        world["family"] = base_family
        world["parameters"] = _make_pair_parameters(rng, base_family)
        world["temperature_coefficient"] = float(
            rng.choice((-1.0, 1.0)) * rng.uniform(0.19, 0.29)
        )
    else:
        raise ValueError("unknown world kind")
    return world


def _world_energy_forces(world, coordinates, temperature_k):
    if world["kind"] == "buckingham":
        return _pair_energy_forces(
            "buckingham", world["parameters"], coordinates
        )
    energy, forces = _pair_energy_forces(
        world["family"], world["parameters"], coordinates
    )
    if world["kind"] == "three_body":
        three_energy, three_forces = _axilrod_teller_energy_forces(
            coordinates, world["three_body_coefficient_ev_a9"]
        )
        energy += three_energy
        forces = forces + three_forces
    elif world["kind"] == "state_dependent":
        scale = 1.0 + world["temperature_coefficient"] * (
            float(temperature_k) - 450.0
        ) / 450.0
        energy *= scale
        forces = forces * scale
    return float(energy), np.asarray(forces, dtype=float)


def _triangle_coordinates(side01, side02, side12):
    side01 = float(side01)
    side02 = float(side02)
    side12 = float(side12)
    x_coordinate = (
        side01 * side01 + side02 * side02 - side12 * side12
    ) / (2.0 * side01)
    height_squared = max(0.0, side02 * side02 - x_coordinate * x_coordinate)
    coordinates = np.asarray((
        (0.0, 0.0, 0.0),
        (side01, 0.0, 0.0),
        (x_coordinate, math.sqrt(height_squared), 0.0),
    ), dtype=float)
    return coordinates - np.mean(coordinates, axis=0, keepdims=True)


def _pair_distances(coordinates):
    coordinates = np.asarray(coordinates, dtype=float)
    return np.asarray((
        np.linalg.norm(coordinates[0] - coordinates[1]),
        np.linalg.norm(coordinates[0] - coordinates[2]),
        np.linalg.norm(coordinates[1] - coordinates[2]),
    ), dtype=float)


def _public_problem(world):
    return {
        "schema_version": 2,
        "model_families": {
            "mie": {
                "equation": "4*epsilon_ev*((sigma_a/r_a)^12-(sigma_a/r_a)^6)",
                "parameter_bounds": {
                    name: list(bounds) for name, bounds in PARAMETER_SPECS["mie"]
                },
            },
            "morse": {
                "equation": "well_depth_ev*(exp(-2*a*(r-r_e))-2*exp(-a*(r-r_e)))",
                "parameter_bounds": {
                    name: list(bounds) for name, bounds in PARAMETER_SPECS["morse"]
                },
            },
        },
        "hypothesis_names": list(HYPOTHESES),
        "minimum_retained_weight": MINIMUM_RETAINED_WEIGHT,
        "distance_bounds_a": list(DISTANCE_BOUNDS_A),
        "coordinate_abs_bound_a": COORDINATE_BOUND_A,
        "temperatures_k": list(TEMPERATURES_K),
        "query_budget_units": QUERY_BUDGET_UNITS,
        "max_batch_configurations": MAX_BATCH_CONFIGURATIONS,
        "max_query_calls": MAX_QUERY_CALLS,
        "first_query_distance_bounds_a": list(FIRST_QUERY_DISTANCE_BOUNDS_A),
        "first_query_max_configurations": FIRST_QUERY_MAX_CONFIGURATIONS,
        "first_query_max_distance_ratio": FIRST_QUERY_MAX_DISTANCE_RATIO,
        "first_query_temperature_k": FIRST_QUERY_TEMPERATURE_K,
        "nominal_energy_noise_sigma_ev": ENERGY_NOISE_EV,
        "nominal_force_noise_sigma_ev_per_a": FORCE_NOISE_EV_PER_A,
        "parameter_interval_confidence": INTERVAL_CONFIDENCE,
        "virial_temperature_grid_k": list(VIRIAL_TEMPERATURE_GRID_K),
        "second_virial_bounds_cm3_mol": list(
            SECOND_VIRIAL_BOUNDS_CM3_MOL
        ),
        "boyle_temperature_bounds_k": list(BOYLE_TEMPERATURE_BOUNDS_K),
        "boyle_temperature_threshold_k": BOYLE_TEMPERATURE_THRESHOLD_K,
    }


def _validate_weight_state(value, name):
    if not isinstance(value, dict) or set(value) != HYPOTHESIS_STATE_KEYS:
        raise ValueError(name + " must contain exactly weights and retained")
    raw_weights = value["weights"]
    if not isinstance(raw_weights, dict) or set(raw_weights) != set(HYPOTHESES):
        raise ValueError(name + ".weights must contain exactly the public hypotheses")
    weights = {
        hypothesis: _bounded(
            raw_weights[hypothesis], (0.0, 1.0),
            name + ".weights[" + hypothesis + "]",
        ) for hypothesis in HYPOTHESES
    }
    if abs(sum(weights.values()) - 1.0) > 1.0e-8:
        raise ValueError(name + ".weights must sum to one")
    retained = value["retained"]
    if (
        not isinstance(retained, list)
        or not retained
        or any(not isinstance(item, str) or item not in HYPOTHESES
               for item in retained)
        or len(retained) != len(set(retained))
    ):
        raise ValueError(name + ".retained must be a non-empty unique public subset")
    retained_set = set(retained)
    for hypothesis, weight in weights.items():
        if hypothesis in retained_set and weight < MINIMUM_RETAINED_WEIGHT:
            raise ValueError(name + " retained weight is below the public minimum")
        if hypothesis not in retained_set and weight != 0.0:
            raise ValueError(name + " omitted hypotheses must have zero weight")
    return weights, list(retained)


def _reference_report_weights(weights):
    """Keep all three hypotheses materially alive for the HP1 calibration witness."""
    floor = MINIMUM_RETAINED_WEIGHT
    return {
        hypothesis: floor + (1.0 - len(HYPOTHESES) * floor) * weights[hypothesis]
        for hypothesis in HYPOTHESES
    }


def _query_noise(seed, call_index, configuration_id, energy_sigma, force_sigma):
    digest = hashlib.sha256(
        (str(seed) + "|" + str(call_index) + "|" + configuration_id).encode("utf-8")
    ).digest()
    words = np.frombuffer(digest[:16], dtype="<u4")
    sequence = np.random.SeedSequence([int(value) for value in words])
    rng = np.random.default_rng(sequence)
    return (
        float(rng.normal(0.0, energy_sigma)),
        rng.normal(0.0, force_sigma, size=(3, 3)),
    )


def _parameter_arrays(problem, family):
    items = PARAMETER_SPECS[family]
    names = [item[0] for item in items]
    lower = np.asarray([problem["model_families"][family]["parameter_bounds"][name][0]
                        for name in names], dtype=float)
    upper = np.asarray([problem["model_families"][family]["parameter_bounds"][name][1]
                        for name in names], dtype=float)
    return names, lower, upper


def _stack_observations(observations):
    coordinates = []
    energies = []
    forces = []
    temperatures = []
    for observation in observations:
        batch_coordinates = np.asarray(observation["configurations"], dtype=float)
        batch_energies = np.asarray(observation["energies_ev"], dtype=float)
        batch_forces = np.asarray(observation["forces_ev_per_a"], dtype=float)
        for index in range(len(batch_coordinates)):
            coordinates.append(batch_coordinates[index])
            energies.append(batch_energies[index])
            forces.append(batch_forces[index])
            temperatures.append(float(observation["temperature_k"]))
    return (
        np.asarray(coordinates, dtype=float),
        np.asarray(energies, dtype=float),
        np.asarray(forces, dtype=float),
        np.asarray(temperatures, dtype=float),
    )


def _fit_family(observations, family, problem):
    if not observations:
        raise ValueError("at least one observation is required")
    coordinates, observed_energies, observed_forces, _ = _stack_observations(
        observations
    )
    names, lower, upper = _parameter_arrays(problem, family)
    energy_sigma = float(problem["nominal_energy_noise_sigma_ev"])
    force_sigma = float(problem["nominal_force_noise_sigma_ev_per_a"])

    def residual(parameters):
        energies = []
        forces = []
        for configuration in coordinates:
            energy, force = _pair_energy_forces(
                family, parameters, configuration
            )
            energies.append(energy)
            forces.append(force)
        energy_residual = (
            np.asarray(energies) - observed_energies
        ) / energy_sigma
        force_residual = (
            np.asarray(forces) - observed_forces
        ) / force_sigma
        return np.concatenate((energy_residual.ravel(), force_residual.ravel()))

    middle = 0.5 * (lower + upper)
    starts = (
        middle,
        lower + 0.25 * (upper - lower),
        lower + 0.75 * (upper - lower),
    )
    best = None
    for start in starts:
        result = least_squares(
            residual,
            start,
            bounds=(lower, upper),
            x_scale=np.maximum(upper - lower, 1.0e-6),
            max_nfev=700,
            ftol=1.0e-10,
            xtol=1.0e-10,
            gtol=1.0e-10,
        )
        if best is None or result.cost < best.cost:
            best = result
    assert best is not None
    residual_values = np.asarray(best.fun, dtype=float)
    rms = float(math.sqrt(np.mean(residual_values * residual_values)))
    jacobian = np.asarray(best.jac, dtype=float)
    covariance = np.linalg.pinv(jacobian.T @ jacobian, rcond=1.0e-12)
    reduced = float(np.sum(residual_values * residual_values) /
                    max(1, len(residual_values) - len(best.x)))
    covariance *= max(1.0, reduced)
    return {
        "family": family,
        "names": names,
        "parameters": np.asarray(best.x, dtype=float),
        "rms": rms,
        "covariance": covariance,
        "residual_count": len(residual_values),
    }


def _diagnostic_weights(observations, problem):
    if not observations:
        return {hypothesis: 1.0 / 3.0 for hypothesis in HYPOTHESES}
    fits = {family: _fit_family(observations, family, problem)
            for family in PAIR_FAMILIES}
    configuration_count = sum(
        len(observation["configuration_ids"]) for observation in observations
    )
    scale = min(8.0, max(1.0, math.sqrt(configuration_count)))
    logits = []
    for family in PAIR_FAMILIES:
        rms = min(20.0, fits[family]["rms"])
        complexity = len(PARAMETER_SPECS[family])
        logits.append(-0.5 * scale * rms * rms - 0.08 * complexity)
    logits.append(-0.5 * scale * 3.0**2)
    return _normalize_weights(logits)


class _Laboratory:
    def __init__(self, world, problem):
        self.world = world
        self.problem = problem
        self.used = 0
        self.calls = 0
        self.violated = False
        self.observations = []
        self.available_evidence = set()
        self.eliminated = set()
        self.state_scores = []
        self.true_retention = []
        self.state_history = []
        self._posterior_cache = None

    def posterior(self):
        if self._posterior_cache is None:
            self._posterior_cache = _diagnostic_weights(
                self.observations, self.problem
            )
        return dict(self._posterior_cache)

    def query(self, configurations, temperature_k, hypothesis_state):
        try:
            weights, retained = _validate_weight_state(
                hypothesis_state, "hypothesis_state"
            )
            restored = {
                hypothesis for hypothesis in self.eliminated
                if hypothesis in retained or weights[hypothesis] > 0.0
            }
            if restored:
                raise RuntimeError("an eliminated hypothesis cannot be restored")
            coordinates = np.asarray(configurations, dtype=float)
            if (
                coordinates.ndim != 3
                or coordinates.shape[1:] != (3, 3)
                or len(coordinates) < 1
                or len(coordinates) > MAX_BATCH_CONFIGURATIONS
                or np.any(~np.isfinite(coordinates))
            ):
                raise ValueError("configurations must be a finite (n,3,3) array")
            if np.max(np.abs(coordinates)) > COORDINATE_BOUND_A:
                raise ValueError("configuration coordinate outside public bounds")
            for configuration in coordinates:
                distances = _pair_distances(configuration)
                if (
                    np.min(distances) < DISTANCE_BOUNDS_A[0] - 1.0e-10
                    or np.max(distances) > DISTANCE_BOUNDS_A[1] + 1.0e-10
                ):
                    raise ValueError("pair distance outside public bounds")
                if self.calls == 0 and (
                    np.min(distances) < FIRST_QUERY_DISTANCE_BOUNDS_A[0] - 1.0e-10
                    or np.max(distances) > FIRST_QUERY_DISTANCE_BOUNDS_A[1] + 1.0e-10
                ):
                    raise ValueError(
                        "first-query pair distance outside the screening envelope"
                    )
                if self.calls == 0 and (
                    np.max(distances) / np.min(distances)
                    > FIRST_QUERY_MAX_DISTANCE_RATIO + 1.0e-10
                ):
                    raise ValueError(
                        "first-query configuration must be near-equilateral"
                    )
            if self.calls == 0 and len(coordinates) > FIRST_QUERY_MAX_CONFIGURATIONS:
                raise ValueError("first query exceeds the screening-batch limit")
            temperature = _finite_scalar(temperature_k, "temperature_k")
            if not any(abs(temperature - value) <= 1.0e-10
                       for value in TEMPERATURES_K):
                raise ValueError("temperature_k is not an allowed temperature")
            if self.calls == 0 and abs(
                temperature - FIRST_QUERY_TEMPERATURE_K
            ) > 1.0e-10:
                raise ValueError(
                    "first query must use the screening temperature"
                )
            if self.calls + 1 > MAX_QUERY_CALLS:
                raise RuntimeError("query-call limit exceeded")
            if self.used + len(coordinates) > QUERY_BUDGET_UNITS:
                raise RuntimeError("query budget exceeded")

            expected = self.posterior()
            true_hypothesis = (
                self.world["family"]
                if self.world["kind"] in PAIR_FAMILIES else "unsupported"
            )
            state_score = _brier_quality(weights, true_hypothesis)
            retained_truth = bool(
                true_hypothesis in retained
                and weights[true_hypothesis] >= MINIMUM_RETAINED_WEIGHT
            )
            self.state_scores.append(float(np.clip(state_score, 0.0, 1.0)))
            self.true_retention.append(retained_truth)
            self.state_history.append({
                "call_index": self.calls,
                "weights": dict(weights),
                "retained": list(retained),
                "expected_weights": expected,
                "true_hypothesis_retained": retained_truth,
            })
            self.eliminated.update(
                hypothesis for hypothesis in HYPOTHESES
                if hypothesis not in retained or weights[hypothesis] == 0.0
            )
            self.calls += 1
            self.used += len(coordinates)
            observation_id = _token(
                "OBS-", self.world["seed"], self.calls, temperature
            )
            configuration_ids = []
            energies = []
            forces = []
            for index, configuration in enumerate(coordinates):
                coordinate_digest = hashlib.sha256(
                    np.asarray(configuration, dtype="<f8").tobytes()
                ).hexdigest()[:16]
                configuration_id = _token(
                    "CFG-", self.world["seed"], self.calls, index,
                    temperature, coordinate_digest,
                )
                energy, force = _world_energy_forces(
                    self.world, configuration, temperature
                )
                energy_noise, force_noise = _query_noise(
                    self.world["seed"], self.calls, configuration_id,
                    self.world["energy_noise"], self.world["force_noise"],
                )
                configuration_ids.append(configuration_id)
                energies.append(energy + energy_noise)
                forces.append(force + force_noise)
            observation = {
                "observation_id": observation_id,
                "configuration_ids": configuration_ids,
                "configurations": coordinates.copy(),
                "temperature_k": temperature,
                "energies_ev": np.asarray(energies, dtype=float),
                "forces_ev_per_a": np.asarray(forces, dtype=float),
            }
            self.observations.append(observation)
            self.available_evidence.add(observation_id)
            self.available_evidence.update(configuration_ids)
            self._posterior_cache = None
            posterior_after = self.posterior()
            batch_information_gain = float(np.clip(
                (_entropy(expected) - _entropy(posterior_after))
                / math.log(len(HYPOTHESES)),
                -1.0, 1.0,
            ))
            self.state_history[-1]["posterior_after"] = posterior_after
            self.state_history[-1]["batch_information_gain"] = (
                batch_information_gain
            )
            return observation
        except Exception:
            self.violated = True
            raise


def _validate_submission(submission, problem, laboratory):
    if laboratory.violated:
        raise RuntimeError("query protocol was violated")
    if laboratory.calls < 1:
        raise ValueError("at least one query is required")
    if not isinstance(submission, dict) or set(submission) != SUBMISSION_KEYS:
        raise ValueError("submission must contain exactly the documented fields")
    final_state = {
        "weights": submission["hypothesis_weights"],
        "retained": submission["retained_hypotheses"],
    }
    weights, retained = _validate_weight_state(final_state, "final hypothesis state")
    restored = {
        hypothesis for hypothesis in laboratory.eliminated
        if hypothesis in retained or weights[hypothesis] > 0.0
    }
    if restored:
        raise ValueError("final state restores an eliminated hypothesis")
    selected = submission["selected_model"]
    if not isinstance(selected, str) or selected not in HYPOTHESES:
        raise ValueError("selected_model is not a public hypothesis")
    if selected not in retained or weights[selected] < MINIMUM_RETAINED_WEIGHT:
        raise ValueError("selected_model must be retained with positive weight")
    if weights[selected] + 1.0e-12 < max(weights.values()):
        raise ValueError("selected_model must have maximum final hypothesis weight")
    confidence = _bounded(submission["confidence"], (0.0, 1.0), "confidence")
    abstain = _strict_bool(submission["abstain"], "abstain")
    parameters = submission["parameters"]
    intervals = submission["parameter_intervals"]
    virial_curve = submission["second_virial_cm3_mol_by_temperature"]
    if (
        not isinstance(parameters, dict)
        or not isinstance(intervals, dict)
        or not isinstance(virial_curve, dict)
    ):
        raise ValueError("parameters, intervals and virial curve must be mappings")
    parsed_parameters = {}
    parsed_intervals = {}
    if selected == "unsupported":
        if not abstain:
            raise ValueError("unsupported selection must abstain")
        if parameters or intervals or virial_curve:
            raise ValueError(
                "unsupported selection requires empty parameter and virial maps"
            )
        if submission["boyle_temperature_k"] is not None:
            raise ValueError("unsupported selection requires null Boyle temperature")
        if submission["boyle_temperature_above_threshold"] is not None:
            raise ValueError("unsupported selection requires null Boyle decision")
        boyle = None
        above = None
        parsed_virial = {}
    else:
        if abstain:
            raise ValueError("supported selection cannot abstain")
        expected = {name for name, _ in PARAMETER_SPECS[selected]}
        if set(parameters) != expected or set(intervals) != expected:
            raise ValueError("parameter maps must exactly match the selected family")
        for name, bounds in PARAMETER_SPECS[selected]:
            estimate = _bounded(parameters[name], bounds, "parameters[" + name + "]")
            interval = intervals[name]
            if not isinstance(interval, (list, tuple)) or len(interval) != 2:
                raise ValueError("each parameter interval must be [lower,upper]")
            lower = _bounded(interval[0], bounds, "parameter interval lower")
            upper = _bounded(interval[1], bounds, "parameter interval upper")
            if lower > estimate or estimate > upper:
                raise ValueError("parameter interval must contain its point estimate")
            parsed_parameters[name] = estimate
            parsed_intervals[name] = (lower, upper)
        expected_temperatures = {
            str(float(value)) for value in problem["virial_temperature_grid_k"]
        }
        if set(virial_curve) != expected_temperatures:
            raise ValueError(
                "second_virial_cm3_mol_by_temperature must contain every public grid temperature"
            )
        parsed_virial = {
            key: _bounded(
                virial_curve[key],
                problem["second_virial_bounds_cm3_mol"],
                "second_virial_cm3_mol_by_temperature[" + key + "]",
            ) for key in expected_temperatures
        }
        boyle = _bounded(
            submission["boyle_temperature_k"],
            BOYLE_TEMPERATURE_BOUNDS_K,
            "boyle_temperature_k",
        )
        above = _strict_bool(
            submission["boyle_temperature_above_threshold"],
            "boyle_temperature_above_threshold",
        )
    evidence = submission["evidence_ids"]
    if (
        not isinstance(evidence, list)
        or not evidence
        or any(not isinstance(value, str) for value in evidence)
        or len(evidence) != len(set(evidence))
        or not set(evidence).issubset(laboratory.available_evidence)
    ):
        raise ValueError("evidence_ids must be unique IDs returned by this laboratory")
    return {
        "weights": weights,
        "retained": retained,
        "selected": selected,
        "parameters": parsed_parameters,
        "intervals": parsed_intervals,
        "virial_curve": parsed_virial,
        "boyle": boyle,
        "above": above,
        "confidence": confidence,
        "abstain": abstain,
        "evidence": list(evidence),
    }


def _second_virial_curve(family, parameters, temperatures):
    values = []
    for temperature in temperatures:
        def integrand(distance):
            energy = _pair_value_derivative(
                family, parameters, distance
            )[0]
            exponent = float(np.clip(
                -energy / (BOLTZMANN_EV_PER_K * float(temperature)),
                -700.0, 50.0,
            ))
            return math.expm1(exponent) * distance * distance

        integral, _ = quad(
            integrand, 0.0, np.inf, epsabs=1.0e-8,
            epsrel=2.0e-10, limit=600,
        )
        values.append(-2.0 * math.pi * integral * ANGSTROM3_TO_CM3_PER_MOL)
    return np.asarray(values, dtype=float)


def _boyle_temperature(family, parameters):
    lower, upper = BOYLE_TEMPERATURE_BOUNDS_K

    def value(temperature):
        return float(_second_virial_curve(
            family, parameters, (temperature,)
        )[0])

    lower_value = value(lower)
    upper_value = value(upper)
    if lower_value * upper_value > 0.0:
        grid = np.linspace(lower, upper, 80)
        values = _second_virial_curve(family, parameters, grid)
        changes = np.flatnonzero(values[:-1] * values[1:] <= 0.0)
        if not len(changes):
            raise RuntimeError("Boyle root is outside the public bounds")
        lower = float(grid[changes[0]])
        upper = float(grid[changes[0] + 1])
    return float(brentq(value, lower, upper, xtol=1.0e-7, rtol=1.0e-10))


def _prediction_configurations(seed, robust):
    if robust:
        triples = (
            (2.23, 2.42, 3.74),
            (2.31, 3.12, 4.88),
            (2.48, 4.62, 5.31),
            (3.16, 4.91, 5.36),
            (3.72, 4.84, 5.29),
            (5.02, 5.18, 5.33),
        )
    else:
        triples = (
            (2.58, 2.91, 3.44),
            (2.82, 3.08, 4.67),
            (3.03, 3.39, 4.91),
            (3.27, 3.76, 4.22),
            (3.51, 4.18, 5.02),
            (4.08, 4.62, 5.17),
        )
    rng = np.random.default_rng(int(seed) + (99173 if robust else 77137))
    configurations = []
    for triple in triples:
        jittered = np.asarray(triple, dtype=float) + rng.uniform(-0.018, 0.018, 3)
        coordinates = _triangle_coordinates(*jittered)
        rotation, _ = np.linalg.qr(rng.normal(size=(3, 3)))
        configurations.append(coordinates @ rotation)
    return np.asarray(configurations, dtype=float)


def _prediction_quality(world, family, parameters, robust):
    configurations = _prediction_configurations(world["seed"], robust)
    temperatures = (
        np.asarray((180.0, 900.0, 180.0, 900.0, 180.0, 900.0))
        if robust else np.full(len(configurations), 450.0)
    )
    energy_errors = []
    force_errors = []
    for configuration, temperature in zip(configurations, temperatures):
        truth_energy, truth_force = _world_energy_forces(
            world, configuration, temperature
        )
        predicted_energy, predicted_force = _pair_energy_forces(
            family, parameters, configuration
        )
        energy_errors.append(
            abs(predicted_energy - truth_energy) / max(0.025, abs(truth_energy))
        )
        force_scale = max(0.04, float(math.sqrt(np.mean(truth_force**2))))
        force_errors.append(
            float(math.sqrt(np.mean((predicted_force - truth_force) ** 2)))
            / force_scale
        )
    energy_score = math.exp(-float(np.mean(energy_errors)) / 0.10)
    force_score = math.exp(-float(np.mean(force_errors)) / 0.10)
    return _geometric((energy_score, force_score))


def _acquisition_metrics(laboratory):
    posterior = laboratory.posterior()
    information_gain = float(np.clip(
        1.0 - _entropy(posterior) / math.log(len(HYPOTHESES)), 0.0, 1.0
    ))
    coordinates, _, _, temperatures = _stack_observations(
        laboratory.observations
    )
    distances = np.concatenate([_pair_distances(value) for value in coordinates])
    distance_coverage = float(np.mean((
        bool(np.any(distances < 2.70)),
        bool(np.any((distances >= 2.70) & (distances <= 3.70))),
        bool(np.any(distances > 3.70)),
    )))
    temperature_coverage = len(set(float(value) for value in temperatures)) / len(
        TEMPERATURES_K
    )
    aspect_ratios = np.asarray([
        np.max(_pair_distances(value)) / np.min(_pair_distances(value))
        for value in coordinates
    ])
    shape_coverage = 0.5 * float(np.any(aspect_ratios < 1.12)) + 0.5 * float(
        np.any(aspect_ratios > 1.55)
    )
    design_coverage = float(np.mean((
        distance_coverage, temperature_coverage, shape_coverage
    )))
    acquisition_quality = _geometric((information_gain, design_coverage))
    batch_information_gains = [
        float(row["batch_information_gain"])
        for row in laboratory.state_history
    ]
    return {
        "information_gain": information_gain,
        "distance_coverage": distance_coverage,
        "temperature_coverage": float(temperature_coverage),
        "shape_coverage": shape_coverage,
        "design_coverage": design_coverage,
        "acquisition_quality": acquisition_quality,
        "information_per_query_unit": information_gain / max(laboratory.used, 1),
        "mean_positive_batch_information_gain": float(np.mean(
            np.maximum(batch_information_gains, 0.0)
        )),
    }


def _score_values(values, laboratory, world, problem):
    supported = world["kind"] in PAIR_FAMILIES
    true_hypothesis = world["family"] if supported else "unsupported"
    correct_conclusion = bool(
        (supported and not values["abstain"]
         and values["selected"] == true_hypothesis)
        or (not supported and values["abstain"]
            and values["selected"] == "unsupported")
    )
    final_weight_quality = _brier_quality(
        values["weights"], true_hypothesis
    )
    trajectory_weight_quality = float(np.mean(laboratory.state_scores))
    final_retention = float(
        true_hypothesis in values["retained"]
        and values["weights"][true_hypothesis] >= MINIMUM_RETAINED_WEIGHT
    )
    true_retention_rate = float(np.mean(
        list(laboratory.true_retention) + [bool(final_retention)]
    ))
    premature_elimination = not bool(np.all(
        list(laboratory.true_retention) + [bool(final_retention)]
    ))
    hypothesis_quality = _geometric((
        trajectory_weight_quality, final_weight_quality, true_retention_rate
    ))
    acquisition = _acquisition_metrics(laboratory)
    lineage_quality = len(values["evidence"]) / max(
        len(laboratory.available_evidence), 1
    )
    confidence_target = 1.0 if correct_conclusion else 0.0
    confidence_score = float(np.clip(
        1.0 - (values["confidence"] - confidence_target) ** 2, 0.0, 1.0
    ))
    selection_quality = float(correct_conclusion)
    parameter_quality = None
    interval_quality = None
    interval_coverage = None
    prediction_quality = None
    robust_prediction_quality = None
    virial_quality = None
    decision_quality = None
    robust_joint = 0.0

    if supported and correct_conclusion:
        family = true_hypothesis
        names = [name for name, _ in PARAMETER_SPECS[family]]
        estimates = np.asarray([values["parameters"][name] for name in names])
        truth = np.asarray(world["parameters"], dtype=float)
        tolerances = (
            np.asarray((0.008, 0.045)) if family == "mie"
            else np.asarray((0.008, 0.070, 0.045))
        )
        parameter_quality = float(np.mean(np.exp(-np.abs(
            estimates - truth
        ) / tolerances)))
        coverage_values = []
        sharpness_values = []
        for index, (name, bounds) in enumerate(PARAMETER_SPECS[family]):
            lower, upper = values["intervals"][name]
            coverage_values.append(lower <= truth[index] <= upper)
            width_scale = 0.20 * (bounds[1] - bounds[0])
            sharpness_values.append(math.exp(-(upper - lower) / width_scale))
        interval_coverage = float(np.mean(coverage_values))
        interval_quality = interval_coverage * float(np.mean(sharpness_values))
        prediction_quality = _prediction_quality(
            world, family, estimates, robust=False
        )
        robust_prediction_quality = _prediction_quality(
            world, family, estimates, robust=True
        )
        temperatures = np.asarray(problem["virial_temperature_grid_k"], dtype=float)
        truth_curve = _second_virial_curve(family, truth, temperatures)
        parameter_curve = _second_virial_curve(family, estimates, temperatures)
        submitted_curve = np.asarray([
            values["virial_curve"][str(float(temperature))]
            for temperature in temperatures
        ], dtype=float)
        relative_curve_error = np.mean(
            np.abs(submitted_curve - truth_curve)
            / np.maximum(25.0, np.abs(truth_curve))
        )
        self_consistency_error = np.mean(
            np.abs(submitted_curve - parameter_curve)
            / np.maximum(25.0, np.abs(parameter_curve))
        )
        virial_quality = _geometric((
            math.exp(-relative_curve_error / 0.08),
            math.exp(-self_consistency_error / 0.02),
        ))
        truth_boyle = _boyle_temperature(family, truth)
        parameter_boyle = _boyle_temperature(family, estimates)
        boyle_quality = _geometric((
            math.exp(-abs(values["boyle"] - truth_boyle) / 120.0),
            math.exp(-abs(values["boyle"] - parameter_boyle) / 25.0),
        ))
        truth_decision = truth_boyle > BOYLE_TEMPERATURE_THRESHOLD_K
        decision_quality = _geometric((
            boyle_quality,
            float(values["above"] == truth_decision),
        ))
        joint = _geometric((
            lineage_quality,
            acquisition["acquisition_quality"],
            hypothesis_quality,
            selection_quality,
            parameter_quality,
            interval_quality,
            prediction_quality,
            virial_quality,
            decision_quality,
            confidence_score,
        ))
        robust_joint = _geometric((
            lineage_quality,
            acquisition["acquisition_quality"],
            hypothesis_quality,
            selection_quality,
            parameter_quality,
            interval_quality,
            robust_prediction_quality,
            virial_quality,
            decision_quality,
            confidence_score,
        ))
    elif not supported and correct_conclusion:
        joint = _geometric((
            lineage_quality,
            acquisition["acquisition_quality"],
            hypothesis_quality,
            selection_quality,
            confidence_score,
        ))
        robust_joint = joint
    else:
        joint = 0.0

    false_discovery = bool(
        (not supported and not values["abstain"])
        or (supported and not values["abstain"]
            and values["selected"] != true_hypothesis)
    )
    return {
        "supported": supported,
        "true_hypothesis": true_hypothesis,
        "selected_model": values["selected"],
        "lineage_quality": float(lineage_quality),
        **acquisition,
        "trajectory_weight_quality": trajectory_weight_quality,
        "final_weight_quality": final_weight_quality,
        "true_hypothesis_retention_rate": true_retention_rate,
        "premature_elimination": premature_elimination,
        "hypothesis_quality": hypothesis_quality,
        "selection_quality": selection_quality,
        "parameter_quality": parameter_quality,
        "interval_quality": interval_quality,
        "interval_coverage": interval_coverage,
        "prediction_quality": prediction_quality,
        "robust_prediction_quality": robust_prediction_quality,
        "virial_quality": virial_quality,
        "decision_quality": decision_quality,
        "confidence_score": confidence_score,
        "joint_quality": joint,
        "robust_joint_quality": robust_joint,
        "correct_refusal": bool(not supported and correct_conclusion),
        "false_discovery": false_discovery,
        "abstained": values["abstain"],
        "confidence": values["confidence"],
        "query_calls": laboratory.calls,
        "query_budget_units": laboratory.used,
        "evidence_count": len(values["evidence"]),
        "available_evidence_count": len(laboratory.available_evidence),
        "hypothesis_state_history": laboratory.state_history,
    }


def _reference_configurations():
    screening = ((3.18, 3.18, 3.18),)
    discriminating = (
        (2.24, 2.43, 3.72),
        (2.38, 3.02, 4.76),
        (2.62, 2.62, 2.62),
        (2.86, 3.19, 4.91),
        (3.12, 3.12, 5.08),
        (3.28, 3.83, 4.31),
        (3.72, 4.46, 5.23),
        (4.92, 4.92, 4.92),
    )
    return (
        np.asarray([_triangle_coordinates(*triple) for triple in screening]),
        np.asarray([
            _triangle_coordinates(*(
                np.asarray(discriminating[index % len(discriminating)])
                + (index // len(discriminating))
                * np.asarray((0.013, -0.009, 0.017))
            ))
            for index in range(23)
        ]),
    )


def _reference_intervals(fit, family):
    minimum_half_width = (
        np.asarray((0.0018, 0.008))
        if family == "mie" else np.asarray((0.0018, 0.018, 0.009))
    )
    standard_error = np.sqrt(np.maximum(0.0, np.diag(fit["covariance"])))
    # 1.645 is the two-sided normal critical value for the public 90% interval.
    half_width = np.maximum(1.645 * standard_error, minimum_half_width)
    intervals = {}
    for index, (name, bounds) in enumerate(PARAMETER_SPECS[family]):
        intervals[name] = [
            float(max(bounds[0], fit["parameters"][index] - half_width[index])),
            float(min(bounds[1], fit["parameters"][index] + half_width[index])),
        ]
    return intervals


def _reference_agent(problem, query):
    observations = []
    screening, discriminating = _reference_configurations()
    batches = (
        (screening, 450.0),
        (discriminating[:8], 180.0),
        (discriminating[8:16], 450.0),
        (discriminating[16:], 900.0),
    )
    for configurations, temperature in batches:
        weights = _reference_report_weights(
            _diagnostic_weights(observations, problem)
        )
        observation = query(
            configurations,
            temperature,
            {"weights": weights, "retained": list(HYPOTHESES)},
        )
        observations.append(observation)
    final_weights = _reference_report_weights(
        _diagnostic_weights(observations, problem)
    )
    fits = {family: _fit_family(observations, family, problem)
            for family in PAIR_FAMILIES}
    selected = max(HYPOTHESES, key=lambda name: final_weights[name])
    evidence = []
    for observation in observations:
        evidence.append(observation["observation_id"])
        evidence.extend(observation["configuration_ids"])
    confidence = float(min(0.995, max(0.85, final_weights[selected])))
    if selected == "unsupported":
        return {
            "hypothesis_weights": final_weights,
            "retained_hypotheses": list(HYPOTHESES),
            "selected_model": "unsupported",
            "parameters": {},
            "parameter_intervals": {},
            "second_virial_cm3_mol_by_temperature": {},
            "boyle_temperature_k": None,
            "boyle_temperature_above_threshold": None,
            "confidence": confidence,
            "abstain": True,
            "evidence_ids": evidence,
        }
    fit = fits[selected]
    parameters = {
        name: float(fit["parameters"][index])
        for index, name in enumerate(fit["names"])
    }
    boyle = _boyle_temperature(selected, fit["parameters"])
    virial_temperatures = np.asarray(
        problem["virial_temperature_grid_k"], dtype=float
    )
    virial_values = _second_virial_curve(
        selected, fit["parameters"], virial_temperatures
    )
    return {
        "hypothesis_weights": final_weights,
        "retained_hypotheses": list(HYPOTHESES),
        "selected_model": selected,
        "parameters": parameters,
        "parameter_intervals": _reference_intervals(fit, selected),
        "second_virial_cm3_mol_by_temperature": {
            str(float(temperature)): float(value)
            for temperature, value in zip(virial_temperatures, virial_values)
        },
        "boyle_temperature_k": boyle,
        "boyle_temperature_above_threshold": bool(
            boyle > problem["boyle_temperature_threshold_k"]
        ),
        "confidence": confidence,
        "abstain": False,
        "evidence_ids": evidence,
    }


def _invalid_record(split, index, world, laboratory, failure_kind):
    return {
        "split": str(split),
        "world_index": int(index),
        "kind": world["kind"],
        "valid": False,
        "failure_kind": str(failure_kind),
        "supported": world["kind"] in PAIR_FAMILIES,
        "true_hypothesis": (
            world["family"] if world["kind"] in PAIR_FAMILIES else "unsupported"
        ),
        "selected_model": None,
        "lineage_quality": 0.0,
        "acquisition_quality": 0.0,
        "information_gain": 0.0,
        "design_coverage": 0.0,
        "hypothesis_quality": 0.0,
        "true_hypothesis_retention_rate": 0.0,
        "premature_elimination": False,
        "selection_quality": 0.0,
        "parameter_quality": None,
        "interval_quality": None,
        "interval_coverage": None,
        "prediction_quality": None,
        "robust_prediction_quality": None,
        "virial_quality": None,
        "decision_quality": None,
        "confidence_score": 0.0,
        "joint_quality": 0.0,
        "robust_joint_quality": 0.0,
        "correct_refusal": False,
        "false_discovery": False,
        "abstained": False,
        "confidence": 0.0,
        "query_calls": laboratory.calls,
        "query_budget_units": laboratory.used,
        "evidence_count": 0,
        "available_evidence_count": len(laboratory.available_evidence),
        "hypothesis_state_history": laboratory.state_history,
        "reference_policy_joint_quality": 0.0,
        "oracle_clean_joint_quality": 1.0,
    }


def _run_policy(policy, world, problem):
    laboratory = _Laboratory(world, problem)
    stage = "candidate_execution"
    try:
        submission = policy(problem, laboratory.query)
        if laboratory.violated:
            raise RuntimeError("query protocol was violated")
        stage = "submission_validation"
        values = _validate_submission(submission, problem, laboratory)
        stage = "trusted_scoring"
        return _score_values(values, laboratory, world, problem), None
    except Exception:
        failure_kind = (
            "invalid_submission" if stage == "submission_validation"
            else "trusted_scoring_failure" if stage == "trusted_scoring"
            else "query_protocol_or_candidate_execution_failure"
        )
        return laboratory, failure_kind


def _evaluate_world(candidate, spec, split, index):
    world = _make_world(spec)
    problem = _public_problem(world)
    result, failure = _run_policy(candidate, world, problem)
    if failure is not None:
        return _invalid_record(split, index, world, result, failure)
    scored = result
    if candidate is _reference_agent:
        reference_quality = scored["joint_quality"]
    else:
        reference_result, reference_failure = _run_policy(
            _reference_agent, world, problem
        )
        reference_quality = (
            0.0 if reference_failure is not None
            else reference_result["joint_quality"]
        )
    record = {
        "split": str(split),
        "world_index": int(index),
        "kind": world["kind"],
        "valid": True,
        "failure_kind": None,
        **scored,
        "reference_policy_joint_quality": reference_quality,
        "oracle_clean_joint_quality": 1.0,
    }
    rounded = {}
    for key, value in record.items():
        if isinstance(value, float):
            rounded[key] = round(value, 6)
        else:
            rounded[key] = value
    return rounded


def _mean_applicable(records, field, supported_only=False):
    selected = [
        row for row in records if not supported_only or row["supported"]
    ]
    values = [
        0.0 if row[field] is None else row[field]
        for row in selected
        if supported_only or row[field] is not None
    ]
    return float(np.mean(values)) if values else 0.0


def _split_metrics(records):
    supported_count = sum(row["supported"] for row in records)
    unsupported_count = len(records) - supported_count
    claims = sum(bool(row["valid"] and not row["abstained"]) for row in records)
    abstention_baseline = unsupported_count / len(records)
    raw_joint = _mean_applicable(records, "joint_quality")
    raw_robust_joint = _mean_applicable(records, "robust_joint_quality")
    normalized_joint = float(np.clip(
        (raw_joint - abstention_baseline)
        / max(1.0e-12, 1.0 - abstention_baseline),
        0.0, 1.0,
    ))
    normalized_robust_joint = float(np.clip(
        (raw_robust_joint - abstention_baseline)
        / max(1.0e-12, 1.0 - abstention_baseline),
        0.0, 1.0,
    ))
    return {
        "valid_rate": float(np.mean([row["valid"] for row in records])),
        "joint": normalized_joint,
        "robust_joint": normalized_robust_joint,
        "raw_joint": raw_joint,
        "raw_robust_joint": raw_robust_joint,
        "abstention_baseline": abstention_baseline,
        "lineage": _mean_applicable(records, "lineage_quality"),
        "acquisition": _mean_applicable(records, "acquisition_quality"),
        "information_gain": _mean_applicable(records, "information_gain"),
        "design_coverage": _mean_applicable(records, "design_coverage"),
        "hypothesis": _mean_applicable(records, "hypothesis_quality"),
        "retention": _mean_applicable(records, "true_hypothesis_retention_rate"),
        "premature_elimination_rate": float(np.mean([
            row["premature_elimination"] for row in records
        ])),
        "selection": _mean_applicable(records, "selection_quality"),
        "parameter": _mean_applicable(records, "parameter_quality", True),
        "interval": _mean_applicable(records, "interval_quality", True),
        "interval_coverage": _mean_applicable(records, "interval_coverage", True),
        "prediction": _mean_applicable(records, "prediction_quality", True),
        "robust_prediction": _mean_applicable(
            records, "robust_prediction_quality", True
        ),
        "virial": _mean_applicable(records, "virial_quality", True),
        "decision": _mean_applicable(records, "decision_quality", True),
        "confidence": _mean_applicable(records, "confidence_score"),
        "supported_claim_coverage": sum(
            row["supported"] and row["valid"] and not row["abstained"]
            for row in records
        ) / max(supported_count, 1),
        "supported_correct_model_rate": sum(
            row["supported"] and row["valid"] and row["selection_quality"] == 1.0
            for row in records
        ) / max(supported_count, 1),
        "unsupported_refusal_rate": sum(
            row["correct_refusal"] for row in records
        ) / max(unsupported_count, 1),
        "false_discovery_rate": sum(
            row["false_discovery"] for row in records
        ) / max(claims, 1),
        "mean_query_calls": float(np.mean([row["query_calls"] for row in records])),
        "mean_query_budget_units": float(np.mean([
            row["query_budget_units"] for row in records
        ])),
        "reference_policy": _mean_applicable(
            records, "reference_policy_joint_quality"
        ),
        "oracle_clean": _mean_applicable(records, "oracle_clean_joint_quality"),
    }


def evaluate(calibrate_forcefield):
    development = []
    heldout = []
    rows = [
        ("development", index, spec)
        for index, spec in enumerate(DEVELOPMENT_SPECS)
    ] + [
        ("heldout", index, spec)
        for index, spec in enumerate(HELDOUT_SPECS)
    ]
    for call_index, (split, index, spec) in enumerate(rows):
        if call_index and hasattr(calibrate_forcefield, "reset_session"):
            calibrate_forcefield.reset_session()
        record = _evaluate_world(calibrate_forcefield, spec, split, index)
        (development if split == "development" else heldout).append(record)
    dev = _split_metrics(development)
    held = _split_metrics(heldout)
    development_valid = all(row["valid"] for row in development)
    heldout_valid = all(row["valid"] for row in heldout)
    return {
        "combined_score": dev["joint"] if development_valid else 0.0,
        "valid": float(development_valid),
        "feasibility_rate": dev["valid_rate"],
        "robustness_score": dev["robust_joint"] if development_valid else 0.0,
        "heldout_policy_score": held["joint"] if heldout_valid else 0.0,
        "heldout_robustness_score": (
            held["robust_joint"] if heldout_valid else 0.0
        ),
        "heldout_feasibility_rate": held["valid_rate"],
        "development_raw_joint_score": dev["raw_joint"],
        "heldout_raw_joint_score": held["raw_joint"],
        "development_raw_robust_joint_score": dev["raw_robust_joint"],
        "heldout_raw_robust_joint_score": held["raw_robust_joint"],
        "development_abstention_baseline": dev["abstention_baseline"],
        "heldout_abstention_baseline": held["abstention_baseline"],
        "development_lineage_score": dev["lineage"],
        "heldout_lineage_score": held["lineage"],
        "development_acquisition_score": dev["acquisition"],
        "heldout_acquisition_score": held["acquisition"],
        "development_information_gain": dev["information_gain"],
        "heldout_information_gain": held["information_gain"],
        "development_design_coverage": dev["design_coverage"],
        "heldout_design_coverage": held["design_coverage"],
        "development_hypothesis_score": dev["hypothesis"],
        "heldout_hypothesis_score": held["hypothesis"],
        "development_true_hypothesis_retention_rate": dev["retention"],
        "heldout_true_hypothesis_retention_rate": held["retention"],
        "development_premature_elimination_rate": dev[
            "premature_elimination_rate"
        ],
        "heldout_premature_elimination_rate": held[
            "premature_elimination_rate"
        ],
        "development_model_selection_score": dev["selection"],
        "heldout_model_selection_score": held["selection"],
        "development_parameter_score": dev["parameter"],
        "heldout_parameter_score": held["parameter"],
        "development_interval_score": dev["interval"],
        "heldout_interval_score": held["interval"],
        "development_interval_coverage": dev["interval_coverage"],
        "heldout_interval_coverage": held["interval_coverage"],
        "development_prediction_score": dev["prediction"],
        "heldout_prediction_score": held["prediction"],
        "development_robust_prediction_score": dev["robust_prediction"],
        "heldout_robust_prediction_score": held["robust_prediction"],
        "development_virial_score": dev["virial"],
        "heldout_virial_score": held["virial"],
        "development_boyle_decision_score": dev["decision"],
        "heldout_boyle_decision_score": held["decision"],
        "development_confidence_score": dev["confidence"],
        "heldout_confidence_score": held["confidence"],
        "development_supported_claim_coverage": dev[
            "supported_claim_coverage"
        ],
        "heldout_supported_claim_coverage": held["supported_claim_coverage"],
        "development_supported_correct_model_rate": dev[
            "supported_correct_model_rate"
        ],
        "heldout_supported_correct_model_rate": held[
            "supported_correct_model_rate"
        ],
        "development_unsupported_refusal_rate": dev[
            "unsupported_refusal_rate"
        ],
        "heldout_unsupported_refusal_rate": held["unsupported_refusal_rate"],
        "development_false_discovery_rate": dev["false_discovery_rate"],
        "heldout_false_discovery_rate": held["false_discovery_rate"],
        "development_mean_query_calls": dev["mean_query_calls"],
        "heldout_mean_query_calls": held["mean_query_calls"],
        "development_mean_query_budget_units": dev["mean_query_budget_units"],
        "heldout_mean_query_budget_units": held["mean_query_budget_units"],
        "development_reference_policy_score": dev["reference_policy"],
        "heldout_reference_policy_score": held["reference_policy"],
        "development_oracle_clean_score": dev["oracle_clean"],
        "heldout_oracle_clean_score": held["oracle_clean"],
        "candidate_instance_call_count": len(rows),
        "candidate_instance_valid_rate": float(np.mean([
            row["valid"] for row in development + heldout
        ])),
        "per_world": development + heldout,
    }
