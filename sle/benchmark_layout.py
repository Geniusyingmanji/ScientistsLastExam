"""Physical benchmark layout and stable logical task identities.

Benchmark packages are grouped on disk by broad discipline while the finer-grained
``domain`` in each package's metadata remains part of its stable public task id.
"""

from __future__ import annotations

from pathlib import Path


DISCIPLINE_DOMAINS: dict[str, tuple[str, ...]] = {
    "Biology": (
        "Biomechanics",
        "EvidenceSynthesis",
        "PopulationGenetics",
        "ProteinEngineering",
        "RNAEngineering",
        "SyntheticBiology",
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
        "AtmosphericScience",
        "ClimateScience",
        "Cryosphere",
        "Geophysics",
        "Hydrology",
        "Oceanography",
        "Paleoclimate",
        "Volcanology",
        "WavePropagation",
    ),
    "Mathematics": (
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
        "Exoplanets",
        "QuantumErrorCorrection",
        "Gravitation",
    ),
    "Engineering": (
        "AcousticMetamaterials",
        "Acoustics",
        "AerospaceStructures",
        "Astrodynamics",
        "BuildingControls",
        "ControlTheory",
        "FluidDynamics",
        "FluidMechanics",
        "Geomechanics",
        "HeatTransfer",
        "InventoryManagement",
        "NuclearEngineering",
        "PowerSystems",
        "ProductionSystems",
        "Semiconductor",
        "Sensors",
        "StructuralEngineering",
        "Thermodynamics",
        "Transportation",
        "Turbulence",
        "Wastewater",
        "WaterDistribution",
        "WindEnergy",
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
