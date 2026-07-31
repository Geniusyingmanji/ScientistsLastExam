#!/usr/bin/env python3
"""Cross-check the grating oracle against pinned external grcwa 0.1.2."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import importlib.util
import json
import os
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parent.parent
TASK = ROOT / "benchmarks/Physics/DiffractionGratingDesign"
sys.path.insert(0, str(ROOT))

from frontier_science.provenance import (  # noqa: E402
    finalize_report_trust,
    source_provenance,
)


GRCWA_VERSION = "0.1.2"
GRCWA_WHEEL_SHA256 = (
    "65dbc0151d46a22985c1fe7f1070347e67562363fcb04371e9d158e3ba6140ee"
)
GRCWA_SDIST_SHA256 = (
    "f4983743b94cad92560c0cf528a66ad632357d4df5fd536eb5bbf2cb69708664"
)
GRCWA_PAPER_DOI = "10.1021/acsphotonics.0c00768"
GRCWA_LICENSE = "GPL-3.0-or-later"
INTERNAL_ORDER = 19
EXTERNAL_REQUESTED_HARMONICS = 81
EXTERNAL_GRID_POINTS = 768


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError("cannot load %s" % path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _external_efficiency(
    grcwa,
    design,
    problem,
    wavelength,
    angle,
    polarization,
):
    period = float(problem["period_um"])
    simulation = grcwa.obj(
        EXTERNAL_REQUESTED_HARMONICS,
        [period, 0.0],
        [0.0, period / 100.0],
        1.0 / float(wavelength),
        np.deg2rad(float(angle)),
        0.0,
        verbose=0,
    )
    simulation.Add_LayerUniform(0.0, float(problem["incident_index"]) ** 2)
    for depth in np.asarray(design)[:, 0]:
        simulation.Add_LayerGrid(float(depth), EXTERNAL_GRID_POINTS, 1)
    simulation.Add_LayerUniform(0.0, float(problem["substrate_index"]) ** 2)
    simulation.Init_Setup(Gmethod=0)
    coordinate = (np.arange(EXTERNAL_GRID_POINTS) + 0.5) / EXTERNAL_GRID_POINTS
    epsilon = []
    for _depth, fill, offset in np.asarray(design, dtype=float):
        distance = ((coordinate - offset + 0.5) % 1.0) - 0.5
        epsilon.extend(np.where(
            np.abs(distance) < fill / 2.0,
            float(problem["ridge_index"]) ** 2,
            1.0,
        ))
    simulation.GridLayer_geteps(np.asarray(epsilon))
    if polarization == "TE":
        simulation.MakeExcitationPlanewave(0.0, 0.0, 1.0, 0.0)
    elif polarization == "TM":
        simulation.MakeExcitationPlanewave(1.0, 0.0, 0.0, 0.0)
    else:
        raise ValueError("unknown polarization")
    reflection, transmission = simulation.RT_Solve(normalize=1, byorder=1)
    target = np.where(
        (simulation.G[:, 0] == 1) & (simulation.G[:, 1] == 0)
    )[0]
    if len(target) != 1:
        raise ValueError("grcwa target order is ambiguous")
    return {
        "target_efficiency": float(transmission[target[0]]),
        "energy_sum": float(np.sum(reflection) + np.sum(transmission)),
        "actual_harmonic_count": int(simulation.nG),
    }


def crosscheck():
    import grcwa

    version = importlib.metadata.version("grcwa")
    oracle = _load(
        TASK / "verification/evaluator.py", "grating_grcwa_crosscheck_oracle"
    )
    records = []
    for world in oracle.WORLDS:
        problem = world["problem"]
        wavelength = float(problem["center_wavelength_um"])
        angles = (
            float(problem["development_angles_deg"][0]),
            0.0,
            float(problem["development_angles_deg"][-1]),
        )
        for artifact, design in (
            ("baseline", world["baseline_design"]),
            ("reference", world["reference_design"]),
        ):
            for angle in angles:
                for polarization in oracle.POLARIZATIONS:
                    internal = oracle._rcwa_efficiencies(
                        design,
                        wavelength,
                        problem["period_um"],
                        problem["incident_index"],
                        problem["substrate_index"],
                        problem["ridge_index"],
                        angle,
                        polarization,
                        fourier_order=INTERNAL_ORDER,
                    )
                    external = _external_efficiency(
                        grcwa,
                        design,
                        problem,
                        wavelength,
                        angle,
                        polarization,
                    )
                    records.append({
                        "world": world["name"],
                        "split": world["split"],
                        "artifact": artifact,
                        "wavelength_um": wavelength,
                        "angle_deg": angle,
                        "polarization": polarization,
                        "internal_target_efficiency": internal[
                            "target_efficiency"
                        ],
                        "external_target_efficiency": external[
                            "target_efficiency"
                        ],
                        "absolute_efficiency_difference": abs(
                            internal["target_efficiency"]
                            - external["target_efficiency"]
                        ),
                        "internal_energy_residual": abs(
                            internal["energy_sum"] - 1.0
                        ),
                        "external_energy_residual": abs(
                            external["energy_sum"] - 1.0
                        ),
                        "external_actual_harmonic_count": external[
                            "actual_harmonic_count"
                        ],
                    })
    differences = np.asarray([
        row["absolute_efficiency_difference"] for row in records
    ])
    execution_passed = bool(
        version == GRCWA_VERSION
        and len(records) == 72
        and max(row["internal_energy_residual"] for row in records) < 1.0e-10
        and max(row["external_energy_residual"] for row in records) < 1.0e-8
        and float(np.max(differences)) < 0.01
        and float(np.mean(differences)) < 0.0025
        and float(np.quantile(differences, 0.95)) < 0.007
    )
    report = {
        "schema_version": 1,
        "trust_status": "TRUSTED_INDEPENDENT_IMPLEMENTATION_CROSSCHECK",
        "evidence_scope": (
            "PINNED_EXTERNAL_GRCWA_NUMERICAL_CROSSCHECK_NOT_DEVICE_"
            "MEASUREMENT_FABRICATION_OR_GLOBAL_OPTIMALITY_EVIDENCE"
        ),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_provenance": source_provenance(ROOT),
        "environment": {
            "python": sys.version,
            "numpy": np.__version__,
            "platform": platform.platform(),
            "openblas_num_threads": os.environ.get("OPENBLAS_NUM_THREADS"),
        },
        "task": "Optics/DiffractionGratingDesign",
        "external_implementation": {
            "package": "grcwa",
            "version": version,
            "repository": "https://github.com/weiliangjinca/grcwa",
            "license": GRCWA_LICENSE,
            "paper_doi": GRCWA_PAPER_DOI,
            "wheel_sha256": GRCWA_WHEEL_SHA256,
            "sdist_sha256": GRCWA_SDIST_SHA256,
            "installation": "isolated temporary virtual environment",
            "runtime_dependency_of_benchmark": False,
        },
        "configuration": {
            "internal_fourier_order": INTERNAL_ORDER,
            "external_requested_harmonics": EXTERNAL_REQUESTED_HARMONICS,
            "external_grid_points_per_period": EXTERNAL_GRID_POINTS,
            "world_count": len(oracle.WORLDS),
            "artifacts_per_world": 2,
            "angles_per_artifact": 3,
            "polarizations": oracle.POLARIZATIONS,
        },
        "records": records,
        "summary": {
            "condition_count": len(records),
            "maximum_absolute_efficiency_difference": float(np.max(differences)),
            "mean_absolute_efficiency_difference": float(np.mean(differences)),
            "q95_absolute_efficiency_difference": float(
                np.quantile(differences, 0.95)
            ),
            "maximum_internal_energy_residual": max(
                row["internal_energy_residual"] for row in records
            ),
            "maximum_external_energy_residual": max(
                row["external_energy_residual"] for row in records
            ),
        },
        "limitations": [
            "The external package is an independent software implementation but uses the same RCWA method family and is not experimental validation.",
            "The cross-check covers registered baseline/reference geometries at the center wavelength and three incidence angles for both polarizations; it is not a proof for arbitrary structures.",
            "Both calculations use finite harmonic/grid truncations, so agreement is numerical within the registered tolerance rather than exact identity.",
        ],
    }
    finalize_report_trust(report, execution_passed)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = crosscheck()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    print(json.dumps({
        "execution_passed": report["execution_passed"],
        "trust_decision": report["trust_decision"],
        **report["summary"],
    }, indent=2))
    print("Report: %s" % args.output.resolve())
    return 0 if report["execution_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
