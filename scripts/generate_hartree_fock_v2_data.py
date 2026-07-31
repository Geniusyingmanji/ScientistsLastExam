#!/usr/bin/env python3
"""Generate deterministic finite-basis Hamiltonians for HartreeFockSCF-v2.

This is an offline provenance utility.  It requires PySCF, but the generated task
oracle depends only on NumPy/SciPy.  Run single-threaded for reproducible symmetry
breaking and reference selection, for example::

    OMP_NUM_THREADS=1 python scripts/generate_hartree_fock_v2_data.py

The archive stores full AO integrals, fixed-seed stable multistart RHF witnesses,
small sealed molecular-geometry perturbations, and two representation transforms.  The
witnesses are finite-basis RHF solutions, not exact electronic energies or proofs
of the global minimum over all Slater determinants.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import zipfile
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = (
    ROOT
    / "benchmarks/Chemistry/HartreeFockSCF/verification"
    / "rhf_instances_v2.npz"
)
GENERATION_SEED = 20260723


CASES = (
    {
        "name": "dev_h2_equilibrium_631g",
        "split": "development",
        "atom": "H 0 0 -0.37; H 0 0 0.37",
        "charge": 0,
        "basis": "6-31g",
        "description": "H2 at 0.74 Angstrom",
    },
    {
        "name": "heldout_heh_plus_631g",
        "split": "heldout",
        "atom": "He 0 0 0; H 0 0 0.80",
        "charge": 1,
        "basis": "6-31g",
        "description": "heteronuclear HeH+ at 0.80 Angstrom",
    },
    {
        "name": "dev_lih_stretched_sto3g",
        "split": "development",
        "atom": "Li 0 0 0; H 0 0 3.0",
        "charge": 0,
        "basis": "sto-3g",
        "description": "stretched LiH at 3.0 Angstrom",
    },
    {
        "name": "dev_h6_chain_multisolution_sto3g",
        "split": "development",
        "atom": "; ".join(
            "H 0 0 %.8f" % ((index - 2.5) * 2.2) for index in range(6)
        ),
        "charge": 0,
        "basis": "sto-3g",
        "description": "six-hydrogen chain at 2.2 Angstrom spacing",
    },
    {
        "name": "heldout_water_stretched_sto3g",
        "split": "heldout",
        "atom": "O 0 0 0; H 1.6 0 0; H -0.4 1.549193338 0",
        "charge": 0,
        "basis": "sto-3g",
        "description": "symmetrically stretched water near 104.5 degrees",
    },
    {
        "name": "dev_h8_ring_symmetry_breaking_sto3g",
        "split": "development",
        "atom": "; ".join(
            "H %.10f %.10f 0"
            % (
                1.5 * np.cos(2.0 * np.pi * index / 8.0),
                1.5 * np.sin(2.0 * np.pi * index / 8.0),
            )
            for index in range(8)
        ),
        "charge": 0,
        "basis": "sto-3g",
        "description": "regular H8 ring of radius 1.5 Angstrom",
    },
    {
        "name": "heldout_h4_ring_symmetry_breaking_sto3g",
        "split": "heldout",
        "atom": "; ".join(
            "H %.10f %.10f 0"
            % (
                2.1 * np.cos(2.0 * np.pi * index / 4.0),
                2.1 * np.sin(2.0 * np.pi * index / 4.0),
            )
            for index in range(4)
        ),
        "charge": 0,
        "basis": "sto-3g",
        "description": "held-out stretched square H4 ring of radius 2.1 Angstrom",
    },
)


def _symmetric_orthogonalizer(overlap):
    values, vectors = np.linalg.eigh(overlap)
    if np.min(values) <= 1.0e-10:
        raise ValueError("linearly dependent AO basis")
    return (vectors * (1.0 / np.sqrt(values))) @ vectors.T


def _random_density(overlap, occupied, rng):
    orthogonalizer = _symmetric_orthogonalizer(overlap)
    rotation, _ = np.linalg.qr(rng.normal(size=overlap.shape))
    coefficients = orthogonalizer @ rotation[:, :occupied]
    return 2.0 * coefficients @ coefficients.T


def _configure_rhf(molecule, overlap, core, eri, nuclear_repulsion):
    from pyscf import scf

    mean_field = scf.RHF(molecule)
    mean_field.conv_tol = 1.0e-12
    mean_field.max_cycle = 300
    mean_field.diis_space = 12
    mean_field.get_ovlp = lambda *_args: overlap
    mean_field.get_hcore = lambda *_args: core
    mean_field.energy_nuc = lambda *_args: float(nuclear_repulsion)
    mean_field._eri = eri
    return mean_field


def _stable_multistart_reference(
    molecule, overlap, core, eri, nuclear_repulsion, seed, starts=96
):
    occupied = molecule.nelectron // 2
    rng = np.random.default_rng(seed)
    candidates = []
    converged_count = 0
    stable_count = 0
    starting_densities = [None] + [
        _random_density(overlap, occupied, rng) for _ in range(starts)
    ]
    for density in starting_densities:
        mean_field = _configure_rhf(
            molecule, overlap, core, eri, nuclear_repulsion
        )
        energy = mean_field.kernel(dm0=density)
        if not mean_field.converged or not np.isfinite(energy):
            continue
        converged_count += 1
        stability = mean_field.stability(
            internal=True, external=False, return_status=True
        )
        internally_stable = bool(stability[2])
        stable_count += int(internally_stable)
        if internally_stable:
            coefficients = np.asarray(
                mean_field.mo_coeff[:, mean_field.mo_occ > 0.0], dtype=float
            )
            candidates.append((float(energy), coefficients, mean_field))
    if not candidates:
        raise RuntimeError("no internally stable RHF witness was found")
    energy, coefficients, mean_field = min(candidates, key=lambda item: item[0])
    full_stability = mean_field.stability(
        internal=True, external=True, return_status=True
    )
    return {
        "energy": energy,
        "occupied_coefficients": coefficients,
        "internally_stable": bool(full_stability[2]),
        "externally_stable": bool(full_stability[3]),
        "converged_start_count": converged_count,
        "internally_stable_start_count": stable_count,
        "start_count": len(starting_densities),
    }


def _geometry_shifted_molecule(molecule, basis, case_index):
    """Return a nearby, physically realizable geometry with the same AO dimension."""
    from pyscf import gto

    coordinates = _nuclear_coordinates(molecule)
    charges = np.asarray(molecule.atom_charges(), dtype=float)
    center = np.average(coordinates, axis=0, weights=charges)
    # Alternate expansion/contraction to prevent one fixed bond-length bias.  A
    # 3-percent displacement is large enough to test transfer yet remains local.
    scale = 1.03 if case_index % 2 == 0 else 0.97
    shifted = center + scale * (coordinates - center)
    atoms = [
        (molecule.atom_symbol(index), shifted[index])
        for index in range(molecule.natm)
    ]
    return gto.M(
        atom=atoms,
        charge=int(molecule.charge),
        spin=int(molecule.spin),
        basis=basis,
        unit="Angstrom",
        verbose=0,
    )


def _representation_transforms(size, seed):
    rng = np.random.default_rng(seed)
    permutation = rng.permutation(size)
    permutation_matrix = np.eye(size)[:, permutation]
    left, _ = np.linalg.qr(rng.normal(size=(size, size)))
    right, _ = np.linalg.qr(rng.normal(size=(size, size)))
    scales = rng.permutation(np.linspace(0.78, 1.22, size))
    dense = left @ np.diag(scales) @ right
    if np.linalg.cond(dense) > 1.7:
        raise AssertionError("unexpectedly ill-conditioned representation transform")
    return permutation_matrix, dense


def _nuclear_coordinates(molecule):
    return np.asarray(molecule.atom_coords(unit="Angstrom"), dtype=float)


def _write_deterministic_npz(path, arrays):
    """Write an NPZ with fixed member order/timestamps for byte reproducibility."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(
        str(path), mode="w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as archive:
        for key in sorted(arrays):
            buffer = io.BytesIO()
            np.lib.format.write_array(
                buffer, np.asanyarray(arrays[key]), allow_pickle=False
            )
            member = zipfile.ZipInfo(key + ".npy", date_time=(1980, 1, 1, 0, 0, 0))
            member.compress_type = zipfile.ZIP_DEFLATED
            member.external_attr = 0o100644 << 16
            archive.writestr(member, buffer.getvalue(), compress_type=zipfile.ZIP_DEFLATED)


def generate(output):
    try:
        import pyscf
        from pyscf import gto, scf
    except ImportError as exc:
        raise RuntimeError("offline generation requires PySCF") from exc

    if os.environ.get("OMP_NUM_THREADS") not in (None, "1"):
        raise RuntimeError("set OMP_NUM_THREADS=1 for deterministic generation")
    arrays = {}
    records = []
    for index, specification in enumerate(CASES):
        molecule = gto.M(
            atom=specification["atom"],
            charge=specification["charge"],
            spin=0,
            basis=specification["basis"],
            unit="Angstrom",
            verbose=0,
        )
        overlap = molecule.intor("int1e_ovlp")
        core = scf.hf.get_hcore(molecule)
        eri = molecule.intor("int2e", aosym="s1")
        nuclear_repulsion = float(molecule.energy_nuc())
        reference = _stable_multistart_reference(
            molecule,
            overlap,
            core,
            eri,
            nuclear_repulsion,
            GENERATION_SEED + 1000 * index,
        )
        shifted_molecule = _geometry_shifted_molecule(
            molecule, specification["basis"], index
        )
        shifted_overlap = shifted_molecule.intor("int1e_ovlp")
        shifted_core = scf.hf.get_hcore(shifted_molecule)
        shifted_eri = shifted_molecule.intor("int2e", aosym="s1")
        shifted_nuclear_repulsion = float(shifted_molecule.energy_nuc())
        shifted_reference = _stable_multistart_reference(
            shifted_molecule,
            shifted_overlap,
            shifted_core,
            shifted_eri,
            shifted_nuclear_repulsion,
            GENERATION_SEED + 1000 * index + 211,
        )
        permutation, dense_transform = _representation_transforms(
            molecule.nao_nr(), GENERATION_SEED + 1000 * index + 307
        )
        prefix = "case_%d_" % index
        arrays.update(
            {
                prefix + "overlap": overlap,
                prefix + "core_hamiltonian": core,
                prefix + "eri": eri,
                prefix + "nuclear_repulsion": np.asarray(nuclear_repulsion),
                prefix + "nuclear_charges": molecule.atom_charges(),
                prefix + "coordinates_angstrom": _nuclear_coordinates(molecule),
                prefix + "reference_coefficients": reference[
                    "occupied_coefficients"
                ],
                prefix + "reference_energy": np.asarray(reference["energy"]),
                prefix + "shifted_overlap": shifted_overlap,
                prefix + "shifted_core_hamiltonian": shifted_core,
                prefix + "shifted_eri": shifted_eri,
                prefix + "shifted_nuclear_repulsion": np.asarray(
                    shifted_nuclear_repulsion
                ),
                prefix + "shifted_coordinates_angstrom": _nuclear_coordinates(
                    shifted_molecule
                ),
                prefix + "shifted_reference_coefficients": shifted_reference[
                    "occupied_coefficients"
                ],
                prefix + "shifted_reference_energy": np.asarray(
                    shifted_reference["energy"]
                ),
                prefix + "permutation_transform": permutation,
                prefix + "dense_transform": dense_transform,
            }
        )
        records.append(
            {
                "index": int(index),
                "name": specification["name"],
                "split": specification["split"],
                "description": specification["description"],
                "geometry_angstrom": specification["atom"],
                "charge": int(specification["charge"]),
                "spin": 0,
                "basis": specification["basis"],
                "ao_count": int(molecule.nao_nr()),
                "electron_count": int(molecule.nelectron),
                "occupied_orbital_count": int(molecule.nelectron // 2),
                "reference": {
                    key: value
                    for key, value in reference.items()
                    if key != "occupied_coefficients"
                },
                "shifted_reference": {
                    key: value
                    for key, value in shifted_reference.items()
                    if key != "occupied_coefficients"
                },
                "dense_transform_condition_number": float(
                    np.linalg.cond(dense_transform)
                ),
                "geometry_shift_scale": 1.03 if index % 2 == 0 else 0.97,
            }
        )
        print(
            "%s: E=%.12f shifted=%.12f starts=%d/%d"
            % (
                specification["name"],
                reference["energy"],
                shifted_reference["energy"],
                reference["internally_stable_start_count"],
                reference["start_count"],
            )
        )
    manifest = {
        "schema_version": 2,
        "dataset": "HartreeFockSCF-v2 finite-basis AO Hamiltonians",
        "generation_date": "2026-07-23",
        "generation_seed": GENERATION_SEED,
        "pyscf_version": pyscf.__version__,
        "numpy_version": np.__version__,
        "integral_convention": "chemist pqrs = (pq|rs), real AO basis",
        "reference_method": (
            "fixed-seed multistart restricted closed-shell Hartree-Fock; lowest "
            "internally stable converged witness"
        ),
        "reference_scope": (
            "finite-basis RHF witness, not an exact correlated energy or global proof"
        ),
        "sealed_geometry_shift": (
            "charge-center radial coordinate scale of 1.03/0.97, followed by fresh "
            "PySCF overlap, one-electron, two-electron and nuclear-repulsion integrals"
        ),
        "citations": [
            "doi:10.1103/RevModPhys.23.69",
            "doi:10.1016/0009-2614(80)80396-4",
            "doi:10.1063/1.434318",
            "doi:10.1063/1.1672392",
            "doi:10.1063/1.438955",
            "doi:10.1002/wcms.1340",
            "doi:10.1063/5.0006074",
        ],
        "cases": records,
    }
    arrays["manifest_json"] = np.asarray(
        json.dumps(manifest, sort_keys=True, separators=(",", ":"))
    )
    _write_deterministic_npz(Path(output), arrays)
    digest = hashlib.sha256(Path(output).read_bytes()).hexdigest()
    print("wrote %s" % Path(output))
    print("sha256 %s" % digest)
    return digest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    generate(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
