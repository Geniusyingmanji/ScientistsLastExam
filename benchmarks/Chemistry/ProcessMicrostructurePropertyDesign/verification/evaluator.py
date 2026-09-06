"""Frozen reduced-order process--microstructure--property evaluator.

The oracle evolves a one-dimensional conserved phase-field spectrum, applies a
bounded coarsening closure, and homogenizes the resulting local fields.  It is
deterministic and mechanism-shaped, but intentionally not validated as a model
of any named commercial material.  Scores therefore compare algorithms inside
this frozen synthetic cell; they are not evidence of a real material discovery.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import math
from collections.abc import Mapping
from functools import lru_cache
from pathlib import Path

import numpy as np

TASK_DIR = Path(__file__).resolve().parent.parent
CONTRACT_DIR = TASK_DIR / "frontier_eval" / "contracts"
PANEL_PATH = CONTRACT_DIR / "evaluation_panel_v1.json"

_PANEL = json.loads(PANEL_PATH.read_text(encoding="utf-8"))
if _PANEL.get("schema_version") != 1:
    raise RuntimeError("unsupported process evaluation panel schema")
PROCESS_FIELDS = tuple(_PANEL["process_fields"])
BOUNDS = {
    key: tuple(float(value) for value in bounds)
    for key, bounds in _PANEL["bounds"].items()
}
RESOLUTIONS = {
    key: float(value)
    for key, value in _PANEL["manufacturing_resolutions"].items()
}
ARCHIVE_SIZE = tuple(int(value) for value in _PANEL["archive_size_bounds"])
GRID_CELLS = int(_PANEL["grid_cells"])
HYPERVOLUME_REFERENCE_POINT = tuple(
    float(value) for value in _PANEL["hypervolume_reference_point"]
)
OBJECTIVE_NORMALIZATION = _PANEL["objective_normalization"]
MODEL_PARAMETERS = _PANEL["model_parameters"]
BASELINE_POLICY = _PANEL["baseline_policy"]
REFERENCE_SEARCH = _PANEL["reference_search"]
FRONTIER_PROMOTION = _PANEL["frontier_promotion"]
WORLDS = tuple(dict(world) for world in _PANEL["worlds"])
SHIFT_SPECS = tuple(dict(shift) for shift in _PANEL["shift_specs"])


def _load_contract(name, filename):
    spec = importlib.util.spec_from_file_location(name, CONTRACT_DIR / filename)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load frozen semantic contract")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_reference(name):
    frozen = _PANEL["reference_policy"]
    path = TASK_DIR / frozen["path"]
    if hashlib.sha256(path.read_bytes()).hexdigest() != frozen["sha256"]:
        raise RuntimeError("independent reference policy hash differs")
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load independent reference policy")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_CANONICALIZER = _load_contract(
    "process_microstructure_canonicalizer", "process_canonicalizer_v1.py"
)
_EVIDENCE = _load_contract(
    "process_microstructure_evidence", "evidence_predicate_v1.py"
)
_REFERENCE = _load_reference("process_microstructure_reference")
_reference_policy = _REFERENCE.design_process_archive


DEVELOPMENT_WORLDS = tuple(world for world in WORLDS if world["split"] == "development")
HELDOUT_WORLDS = tuple(world for world in WORLDS if world["split"] == "heldout")


def _problem(world):
    proxy_parameters = {
        name: MODEL_PARAMETERS["properties"][name]
        for name in REFERENCE_SEARCH["proxy_parameter_names"]
    }
    return {
        "process_fields": list(PROCESS_FIELDS),
        "bounds": {key: list(value) for key, value in BOUNDS.items()},
        "archive_size_bounds": list(ARCHIVE_SIZE),
        "manufacturing_resolutions": dict(RESOLUTIONS),
        "grid_cells": GRID_CELLS,
        "constituent_properties": {
            "reduced_modulus": [world["modulus_a"], world["modulus_b"]],
            "reduced_permeability": [world["permeability_a"], world["permeability_b"]],
        },
        "critical_temperature_estimate": world["critical_temperature"],
        "reference_search": {
            "pool_size": REFERENCE_SEARCH["pool_size"],
            "archive_size": REFERENCE_SEARCH["archive_size"],
            "coordinate_refinement_passes": REFERENCE_SEARCH[
                "coordinate_refinement_passes"
            ],
            "coordinate_refinement_points_per_axis": REFERENCE_SEARCH[
                "coordinate_refinement_points_per_axis"
            ],
            "latin_hypercube_multipliers": list(
                REFERENCE_SEARCH["latin_hypercube_multipliers"]
            ),
            "latin_hypercube_offsets": list(
                REFERENCE_SEARCH["latin_hypercube_offsets"]
            ),
            "proxy_parameters": proxy_parameters,
            "objective_normalization": {
                "specific_modulus": dict(
                    OBJECTIVE_NORMALIZATION["specific_modulus"]
                ),
                "barrier_index": dict(
                    OBJECTIVE_NORMALIZATION["barrier_index"]
                ),
                "process_energy_maximum": OBJECTIVE_NORMALIZATION[
                    "process_energy"
                ]["maximum"],
                "clip": {
                    "minimum": OBJECTIVE_NORMALIZATION["objective_clip"][0],
                    "maximum": OBJECTIVE_NORMALIZATION["objective_clip"][1],
                },
            },
        },
        "phase_field_model": (
            "frozen one-dimensional linearized conserved phase-field growth with bounded "
            "nonlinear saturation and a coarsening closure"
        ),
        "homogenization_model": (
            "frozen Voigt--Reuss interpolation with interface, crystallinity and draw terms"
        ),
        "objectives": [
            {"name": "specific_modulus", "sense": "maximize"},
            {"name": "barrier_index", "sense": "maximize"},
            {"name": "process_energy", "sense": "minimize"},
        ],
        "scope_warning": (
            "the oracle is a deterministic reduced mechanism benchmark, not a validated "
            "material model or evidence for real-world discovery"
        ),
    }


def _number(value, name, low, high):
    if isinstance(value, bool) or not isinstance(value, (int, float, np.integer, np.floating)):
        raise TypeError(name + " must be numeric")
    value = float(value)
    if not math.isfinite(value):
        raise ValueError(name + " must be finite")
    if not low <= value <= high:
        raise ValueError(name + " is outside its public process bound")
    return value


def _validate_submission(submission):
    if not isinstance(submission, Mapping) or set(submission) != {"processes"}:
        raise ValueError("submission must contain exactly processes")
    rows = submission["processes"]
    if not isinstance(rows, (list, tuple)) or not ARCHIVE_SIZE[0] <= len(rows) <= ARCHIVE_SIZE[1]:
        raise ValueError("process archive has the wrong size")
    parsed = []
    keys = set()
    for row in rows:
        if not isinstance(row, Mapping) or set(row) != set(PROCESS_FIELDS):
            raise ValueError("each artifact must be a manufacturable process with exact fields")
        process = {}
        key_values = []
        for field in PROCESS_FIELDS:
            value = _number(row[field], field, *BOUNDS[field])
            low, _high = BOUNDS[field]
            bin_index = round((value - low) / RESOLUTIONS[field])
            value = low + bin_index * RESOLUTIONS[field]
            process[field] = value
            key_values.append(bin_index)
        key = tuple(key_values)
        if key in keys:
            raise ValueError("duplicate process schedules do not enlarge a Pareto archive")
        keys.add(key)
        parsed.append(process)
    return tuple(parsed)


def _weak_archive(problem):
    bounds = problem["bounds"]
    low, high = bounds["blend_fraction_b"]
    return [
        {
            "blend_fraction_b": low + fraction * (high - low),
            "anneal_temperature": bounds["anneal_temperature"][
                1 if BASELINE_POLICY["anneal_temperature_bound"] == "upper" else 0
            ],
            "anneal_time": bounds["anneal_time"][
                1 if BASELINE_POLICY["anneal_time_bound"] == "upper" else 0
            ],
            "cooling_rate": bounds["cooling_rate"][
                1 if BASELINE_POLICY["cooling_rate_bound"] == "upper" else 0
            ],
            "draw_ratio": bounds["draw_ratio"][
                1 if BASELINE_POLICY["draw_ratio_bound"] == "upper" else 0
            ],
        }
        for fraction in BASELINE_POLICY["blend_unit_fractions"]
    ]


def _phase_field(world, process):
    """Stable spectral reduced-order phase field with an exactly conserved mean."""
    parameters = MODEL_PARAMETERS["phase_field"]
    cells = GRID_CELLS
    coordinate = np.arange(cells, dtype=float) / cells
    rng = np.random.default_rng(world["seed"])
    mode_count = int(parameters["perturbation_mode_count"])
    phases = rng.uniform(0.0, 2.0 * np.pi, size=mode_count)
    perturbation = sum(
        (parameters["perturbation_amplitude"] / mode)
        * np.sin(2.0 * np.pi * mode * coordinate + phases[mode - 1])
        for mode in range(1, mode_count + 1)
    )
    spectrum = np.fft.rfft(perturbation)
    modes = np.arange(len(spectrum), dtype=float) / parameters["spectral_mode_divisor"]
    mode2 = modes * modes
    temperature = process["anneal_temperature"]
    duration = (
        process["anneal_time"]
        + parameters["cooling_duration_coefficient"] / process["cooling_rate"]
    )
    mobility = world["mobility_scale"] * math.exp(
        -parameters["mobility_activation"]
        / (temperature + parameters["mobility_temperature_offset"])
    )
    instability = world["critical_temperature"] - temperature
    exponent = mobility * duration * (
        instability * mode2 - world["gradient_penalty"] * mode2 * mode2
    )
    exponent -= (
        parameters["high_wave_coarsening_coefficient"]
        * world["coarsening_scale"] * duration * mode2 * mode2
    )
    spectrum *= np.exp(np.clip(exponent, *parameters["exponent_clip"]))
    spectrum[0] = 0.0
    shape = np.fft.irfft(spectrum, n=cells)
    scale = float(np.std(shape))
    growth = scale / max(
        float(np.std(perturbation)), parameters["growth_denominator_floor"]
    )
    capacity = parameters["composition_capacity"] * min(
        process["blend_fraction_b"], 1.0 - process["blend_fraction_b"]
    )
    contrast = capacity * math.tanh(parameters["contrast_response"] * growth)
    if scale > 0.0:
        shape = np.tanh(shape / scale)
    field = process["blend_fraction_b"] + contrast * shape
    for _ in range(int(parameters["mean_restore_iterations"])):
        field = np.clip(
            field + process["blend_fraction_b"] - float(np.mean(field)),
            *parameters["field_clip"],
        )
    return field


def _properties(world, process):
    parameters = MODEL_PARAMETERS["properties"]
    field = _phase_field(world, process)
    contrast = float(np.std(field))
    interface = float(np.mean(np.abs(np.roll(field, -1) - field)))
    temperature = process["anneal_temperature"]
    equilibrium_crystallinity = 1.0 / (
        1.0 + math.exp(
            parameters["crystallinity_equilibrium_temperature_coefficient"]
            * (
                temperature
                - parameters["crystallinity_equilibrium_temperature_reference"]
            )
            + parameters["crystallinity_equilibrium_cooling_coefficient"]
            * process["cooling_rate"]
        )
    )
    effective_time = (
        process["anneal_time"]
        + parameters["crystallization_effective_time_cooling_coefficient"]
        / process["cooling_rate"]
    )
    crystallization_rate = (
        parameters["crystallization_rate_constant"]
        * world["mobility_scale"]
        * math.exp(
            -parameters["crystallization_activation_energy"]
            / (temperature + parameters["crystallization_temperature_offset"])
        )
    )
    crystallinity = equilibrium_crystallinity * (
        1.0 - math.exp(-crystallization_rate * effective_time)
    )
    draw_low, draw_high = BOUNDS["draw_ratio"]
    orientation = (process["draw_ratio"] - draw_low) / (draw_high - draw_low)

    local_modulus = (
        world["modulus_a"] * (1.0 - field) + world["modulus_b"] * field
    )
    voigt = float(np.mean(local_modulus))
    reuss = float(1.0 / np.mean(1.0 / local_modulus))
    modulus = (
        (parameters["modulus_voigt_base"]
         + parameters["modulus_orientation_weight"] * orientation) * voigt
        + (parameters["modulus_reuss_base"]
           - parameters["modulus_orientation_weight"] * orientation) * reuss
    )
    modulus *= (
        parameters["crystallinity_base"]
        + parameters["crystallinity_gain"] * crystallinity
    )
    modulus *= 1.0 + parameters["draw_modulus_gain"] * orientation
    modulus *= max(
        parameters["minimum_interface_factor"],
        parameters["interface_factor_base"]
        - world["interface_penalty"] * interface,
    )
    density = (
        parameters["density_base"]
        + parameters["density_blend_coefficient"] * process["blend_fraction_b"]
    )
    specific_modulus = modulus / density

    local_permeability = (
        world["permeability_a"] * (1.0 - field)
        + world["permeability_b"] * field
    )
    parallel = float(np.mean(local_permeability))
    series = float(1.0 / np.mean(1.0 / local_permeability))
    effective_permeability = (
        (parameters["permeability_parallel_base"]
         + parameters["permeability_orientation_weight"] * orientation) * parallel
        + (parameters["permeability_series_base"]
           - parameters["permeability_orientation_weight"] * orientation) * series
    )
    effective_permeability *= (
        1.0 + parameters["draw_permeability_penalty"] * orientation
    )
    tortuosity = (
        parameters["tortuosity_base"]
        + parameters["tortuosity_contrast_coefficient"] * contrast
        + parameters["tortuosity_interface_coefficient"] * interface
    )
    barrier_index = tortuosity / max(
        effective_permeability, parameters["permeability_floor"]
    )

    energy = (
        process["anneal_time"]
        * (parameters["energy_time_base"]
           + parameters["energy_temperature_coefficient"]
           * (temperature - parameters["energy_temperature_reference"]) ** 2)
        + parameters["energy_draw_coefficient"]
        * (process["draw_ratio"] - draw_low) ** parameters["energy_draw_exponent"]
        + parameters["energy_cooling_coefficient"] / process["cooling_rate"]
    )
    modulus_normalization = OBJECTIVE_NORMALIZATION["specific_modulus"]
    barrier_normalization = OBJECTIVE_NORMALIZATION["barrier_index"]
    energy_normalization = OBJECTIVE_NORMALIZATION["process_energy"]
    objectives = (
        float(np.clip(
            (specific_modulus - modulus_normalization["offset"])
            / modulus_normalization["scale"],
            *OBJECTIVE_NORMALIZATION["objective_clip"],
        )),
        float(np.clip(
            (barrier_index - barrier_normalization["offset"])
            / barrier_normalization["scale"],
            *OBJECTIVE_NORMALIZATION["objective_clip"],
        )),
        float(np.clip(
            parameters["energy_saving_base"]
            - energy / energy_normalization["maximum"],
            *OBJECTIVE_NORMALIZATION["objective_clip"],
        )),
    )
    return {
        "specific_modulus": specific_modulus,
        "barrier_index": barrier_index,
        "process_energy": energy,
        "crystallinity": crystallinity,
        "phase_contrast": contrast,
        "interface_density": interface,
        "objectives": objectives,
    }


def _hypervolume_2d(points, reference):
    xs = sorted({reference[0], *(point[0] for point in points)})
    area = 0.0
    for left, right in zip(xs, xs[1:]):
        active = [point[1] for point in points if point[0] >= right]
        if active:
            area += (right - left) * max(max(active) - reference[1], 0.0)
    return float(area)


def _hypervolume_3d(points, reference=HYPERVOLUME_REFERENCE_POINT):
    xs = sorted({reference[0], *(point[0] for point in points)})
    volume = 0.0
    for left, right in zip(xs, xs[1:]):
        active = [(point[1], point[2]) for point in points if point[0] >= right]
        if active:
            volume += (right - left) * _hypervolume_2d(active, reference[1:])
    return float(volume)


def _archive_metrics(world, processes):
    rows = [_properties(world, process) for process in processes]
    return {
        "raw_hypervolume": _hypervolume_3d([row["objectives"] for row in rows]),
        "mean_specific_modulus": float(np.mean([row["specific_modulus"] for row in rows])),
        "mean_barrier_index": float(np.mean([row["barrier_index"] for row in rows])),
        "mean_process_energy": float(np.mean([row["process_energy"] for row in rows])),
        "mean_phase_contrast": float(np.mean([row["phase_contrast"] for row in rows])),
    }


def _shifted_worlds(world):
    shifts = []
    for specification in SHIFT_SPECS:
        shifted = dict(world)
        for operation, value in specification.items():
            if operation.endswith("_factor"):
                field = operation[:-len("_factor")]
                shifted[field] *= value
            elif operation.endswith("_delta"):
                field = operation[:-len("_delta")]
                shifted[field] += value
            else:
                raise RuntimeError("unsupported frozen shift operation: " + operation)
        shifts.append(shifted)
    return tuple(shifts)


def _score_world(processes, world, split, index):
    nominal = _archive_metrics(world, processes)
    shifted = [
        _archive_metrics(shifted_world, processes)["raw_hypervolume"]
        for shifted_world in _shifted_worlds(world)
    ]
    return {
        "world_index": int(index),
        "split": split,
        "valid": True,
        "failure_kind": None,
        "archive_size": len(processes),
        "archive_canonical_id": _CANONICALIZER.canonical_archive_id(
            processes, PROCESS_FIELDS, BOUNDS, RESOLUTIONS
        ),
        **nominal,
        "raw_shifted_hypervolumes": shifted,
        "raw_shifted_hypervolume": float(np.mean(shifted)),
    }


def _failed_world(split, index, failure_kind):
    return {
        "world_index": int(index),
        "split": split,
        "valid": False,
        "failure_kind": failure_kind,
        "archive_size": 0,
        "archive_canonical_id": None,
        "raw_hypervolume": 0.0,
        "mean_specific_modulus": 0.0,
        "mean_barrier_index": 0.0,
        "mean_process_energy": 0.0,
        "mean_phase_contrast": 0.0,
        "raw_shifted_hypervolumes": [0.0 for _ in SHIFT_SPECS],
        "raw_shifted_hypervolume": 0.0,
    }


def _evaluate_world(candidate, world, split, index):
    try:
        processes = _validate_submission(candidate(_problem(world)))
        return _score_world(processes, world, split, index)
    except Exception as exc:  # noqa: BLE001 - bad candidate artifacts fail closed
        return _failed_world(split, index, f"{type(exc).__name__}: {exc}")


@lru_cache(maxsize=1)
def _anchors():
    result = {}
    for world in WORLDS:
        problem = _problem(world)
        weak = _validate_submission({"processes": _weak_archive(problem)})
        reference = _validate_submission(_reference_policy(problem))
        weak_metrics = _score_world(weak, world, world["split"], 0)
        reference_metrics = _score_world(reference, world, world["split"], 0)
        result[world["seed"]] = {
            "weak": weak_metrics["raw_hypervolume"],
            "reference": reference_metrics["raw_hypervolume"],
            "weak_shifted": weak_metrics["raw_shifted_hypervolume"],
            "reference_shifted": reference_metrics["raw_shifted_hypervolume"],
        }
    for split, worlds in (("development", DEVELOPMENT_WORLDS), ("heldout", HELDOUT_WORLDS)):
        result[split] = {
            key: float(np.mean([result[world["seed"]][key] for world in worlds]))
            for key in ("weak", "reference", "weak_shifted", "reference_shifted")
        }
        if result[split]["reference"] <= (
            result[split]["weak"]
            + OBJECTIVE_NORMALIZATION["anchor_headroom_tolerance"]
        ):
            raise RuntimeError(split + " reference has no nominal Pareto headroom")
        if result[split]["reference_shifted"] <= (
            result[split]["weak_shifted"]
            + OBJECTIVE_NORMALIZATION["anchor_headroom_tolerance"]
        ):
            raise RuntimeError(split + " reference has no shifted Pareto headroom")
    return result


def _normalized(value, weak, reference):
    if reference <= weak:
        raise RuntimeError("invalid Pareto normalization anchors")
    return float(max(
        (value - weak) / (reference - weak),
        OBJECTIVE_NORMALIZATION["score_floor"],
    ))


def _summary(records, split):
    anchor = _anchors()[split]
    raw = float(np.mean([row["raw_hypervolume"] for row in records]))
    shifted = float(np.mean([row["raw_shifted_hypervolume"] for row in records]))
    return {
        "score": _normalized(raw, anchor["weak"], anchor["reference"]),
        "shifted_score": _normalized(
            shifted, anchor["weak_shifted"], anchor["reference_shifted"]
        ),
        "raw": raw,
        "shifted_raw": shifted,
        "feasibility_rate": float(np.mean([row["valid"] for row in records])),
        "mean_specific_modulus": float(np.mean([
            row["mean_specific_modulus"] for row in records
        ])),
        "mean_barrier_index": float(np.mean([
            row["mean_barrier_index"] for row in records
        ])),
        "mean_process_energy": float(np.mean([
            row["mean_process_energy"] for row in records
        ])),
        "mean_phase_contrast": float(np.mean([
            row["mean_phase_contrast"] for row in records
        ])),
    }


def _passes_frontier_promotion(development, heldout):
    if heldout["feasibility_rate"] < FRONTIER_PROMOTION[
        "minimum_heldout_feasibility_rate"
    ]:
        return False
    required = (
        FRONTIER_PROMOTION["minimum_transfer_ratio"] * development["score"]
    )
    return all(
        value + FRONTIER_PROMOTION["comparison_tolerance"] >= required
        for value in (
            development["shifted_score"],
            heldout["score"],
            heldout["shifted_score"],
        )
    )


def evaluate(design_process_archive):
    records = []
    for index, world in enumerate(WORLDS):
        if index and hasattr(design_process_archive, "reset_session"):
            design_process_archive.reset_session()
        records.append(_evaluate_world(
            design_process_archive, world, world["split"], index
        ))
    development = [row for row in records if row["split"] == "development"]
    heldout = [row for row in records if row["split"] == "heldout"]
    dev = _summary(development, "development")
    held = _summary(heldout, "heldout")
    development_valid = all(row["valid"] for row in development)
    frontier_records = []
    if development_valid and _passes_frontier_promotion(dev, held):
        canonical_id = _CANONICALIZER.canonical_panel_archive_id([
            row["archive_canonical_id"] for row in development
        ])
        record = _EVIDENCE.make_frontier_record(canonical_id, dev["raw"], True)
        if record is not None:
            frontier_records.append(record)
    result = {
        "combined_score": dev["score"] if development_valid else 0.0,
        "valid": 1.0 if development_valid else 0.0,
        "feasibility_rate": dev["feasibility_rate"],
        "raw_score": dev["score"] if development_valid else 0.0,
        "development_hypervolume_score": dev["score"],
        "development_shifted_hypervolume_score": dev["shifted_score"],
        "development_raw_hypervolume": dev["raw"],
        "development_raw_shifted_hypervolume": dev["shifted_raw"],
        "development_feasibility_rate": dev["feasibility_rate"],
        "development_mean_specific_modulus": dev["mean_specific_modulus"],
        "development_mean_barrier_index": dev["mean_barrier_index"],
        "development_mean_process_energy": dev["mean_process_energy"],
        "development_mean_phase_contrast": dev["mean_phase_contrast"],
        "heldout_hypervolume_score": held["score"],
        "heldout_shifted_hypervolume_score": held["shifted_score"],
        "heldout_raw_hypervolume": held["raw"],
        "heldout_raw_shifted_hypervolume": held["shifted_raw"],
        "heldout_feasibility_rate": held["feasibility_rate"],
        "heldout_mean_specific_modulus": held["mean_specific_modulus"],
        "heldout_mean_barrier_index": held["mean_barrier_index"],
        "heldout_mean_process_energy": held["mean_process_energy"],
        "heldout_mean_phase_contrast": held["mean_phase_contrast"],
        "frontier_record_emitted": bool(frontier_records),
        "frontier_records": frontier_records,
        "per_instance": records,
    }
    if not development_valid:
        result["error_message"] = "candidate invalid on one or more development worlds"
    return result
