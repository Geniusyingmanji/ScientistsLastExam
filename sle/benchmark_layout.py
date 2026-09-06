"""Physical benchmark layout and stable logical task identities.

Benchmark packages are grouped on disk by broad discipline while the finer-grained
``domain`` in each package's metadata remains part of its stable public task id.
"""

from __future__ import annotations

from pathlib import Path


DISCIPLINE_DOMAINS: dict[str, tuple[str, ...]] = {
    "Biology": (
        "Bioprocess",
        "Biophysics",
        "ConservationBiology",
        "StructuralBiology",
        "Biomechanics",
        "EvidenceSynthesis",
        "Genomics",
        "MetabolicEngineering",
        "Microbiology",
        "Phylogenetics",
        "PopulationGenetics",
        "ProteinEngineering",
        "RNAEngineering",
        "SystemsBiology",
    ),
    "Chemistry": (
        "Catalysis",
        "ChemicalKinetics",
        "ChemicalProcess",
        "Chemistry",
        "Combustion",
        "CrystalGrowth",
        "Electrochemistry",
        "MaterialsScience",
        "MedicinalChemistry",
        "MolecularDynamics",
        "Photovoltaics",
        "QuantumChemistry",
        "Spectroscopy",
    ),
    "ComputerScience": (
        "Algorithm",
        "CausalDiscovery",
        "ScientificComputing",
        "SignalProcessing",
    ),
    "EarthScience": (
        "AtmosphericChemistry",
        "AtmosphericScience",
        "ClimateScience",
        "Geophysics",
        "Oceanography",
        "WavePropagation",
    ),
    "Mathematics": (
        "DiscreteGeometry",
        "BayesianInference",
        "DynamicalSystems",
        "Mathematics",
        "Optimization",
    ),
    "Physics": (
        "Electromagnetics",
        "Optics",
        "Optoelectronics",
        "ParticlePhysics",
        "Photonics",
        "Physics",
        "QuantumControl",
        "QuantumDynamics",
        "QuantumFoundations",
        "Exoplanets",
        "QuantumErrorCorrection",
        "Gravitation",
        "Superconductivity",
    ),
    "Engineering": (
        "AcousticMetamaterials",
        "Acoustics",
        "Astrodynamics",
        "ControlTheory",
        "FluidDynamics",
        "FluidMechanics",
        "Geomechanics",
        "HeatTransfer",
        "InventoryManagement",
        "NuclearEngineering",
        "PowerSystems",
        "Semiconductor",
        "Sensors",
        "StructuralEngineering",
        "Thermodynamics",
        "Transportation",
        "Turbulence",
    ),
}

DOMAIN_DISCIPLINES = {
    domain: discipline
    for discipline, domains in DISCIPLINE_DOMAINS.items()
    for domain in domains
}


def discipline_for_domain(domain: str) -> str:
    """Return the broad physical discipline for a metadata domain."""

    try:
        return DOMAIN_DISCIPLINES[domain]
    except KeyError as exc:
        raise ValueError(
            "Unknown benchmark domain %r; add it to DISCIPLINE_DOMAINS before "
            "creating the task." % domain
        ) from exc


def task_path(benchmarks: Path, domain: str, task: str) -> Path:
    """Build the canonical physical path for a logical ``domain/task`` id."""

    return Path(benchmarks) / discipline_for_domain(domain) / task
