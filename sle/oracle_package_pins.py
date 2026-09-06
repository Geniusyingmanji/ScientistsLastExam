"""Canonical package pins shared by candidate isolation and oracle setup."""

from __future__ import annotations

from typing import Iterable


# Packages installed for trusted oracles. Candidate visibility remains separately allowlisted in
# secure_eval.py; this map only owns the versions used by both setup and runtime validation.
ORACLE_PACKAGE_PINS = {
    "stim": "1.13.0",
    "pymatching": "2.4.0",
    "rdkit": "2024.3.5",
    "ViennaRNA": "2.7.2",
    "nmrsim": "0.6.0",
    "networkx": "3.1",
    "sympy": "1.13.3",
    "qutip": "4.7.6",
    "astropy": "5.2.2",
}

# NumPy and SciPy are exposed to every candidate. The Python 3.8--3.11 line preserves the
# versions used for the recorded oracle anchors; Python 3.12 uses its repository-supported pair.
BASE_CANDIDATE_PINS = {
    (3, 8): {"numpy": "1.24.4", "scipy": "1.10.1"},
    (3, 9): {"numpy": "1.24.4", "scipy": "1.10.1"},
    (3, 10): {"numpy": "1.24.4", "scipy": "1.10.1"},
    (3, 11): {"numpy": "1.24.4", "scipy": "1.10.1"},
    (3, 12): {"numpy": "1.26.4", "scipy": "1.14.1"},
}

# These distributions carry Astropy's numerical and serialization behavior into Radial. They are
# mounted under their import-directory aliases, so validating only `astropy` is not sufficient.
TOOLKIT_DEPENDENCY_PINS = {
    "rdkit": {"Pillow": "10.4.0"},
    "sympy": {"mpmath": "1.3.0"},
    "nmrsim": {
        "sparse": "0.15.5",
        "numba": "0.58.1",
        "llvmlite": "0.41.1",
        "numpy-groupies": "0.9.22",
        "importlib-metadata": "8.5.0",
        "typing-extensions": "4.12.2",
        "zipp": "3.20.2",
    },
    "qutip": {"packaging": "26.2"},
    "astropy": {
        "pyerfa": "2.0.0.3",
        "PyYAML": "6.0.2",
        "packaging": "26.2",
    },
}

# Matplotlib and its runtime closure are trusted-only for the toolkits that use it. Keep the
# complete closure together so task-specific identities do not rely on unrelated toolkits being
# present in the global oracle environment.
ORACLE_DEPENDENCY_PINS = {
    "matplotlib": "3.7.5",
    "contourpy": "1.1.1",
    "cycler": "0.12.1",
    "fonttools": "4.57.0",
    "importlib-resources": "6.4.5",
    "kiwisolver": "1.4.7",
    "packaging": TOOLKIT_DEPENDENCY_PINS["qutip"]["packaging"],
    "Pillow": TOOLKIT_DEPENDENCY_PINS["rdkit"]["Pillow"],
    "pyparsing": "3.1.4",
    "python-dateutil": "2.9.0.post0",
    "six": "1.17.0",
    "zipp": TOOLKIT_DEPENDENCY_PINS["nmrsim"]["zipp"],
}

# Associate trusted-only packages with only the task toolkits whose oracle code imports them.
TRUSTED_TOOLKIT_DEPENDENCY_PINS = {
    "pymatching": {
        "networkx": ORACLE_PACKAGE_PINS["networkx"],
        **ORACLE_DEPENDENCY_PINS,
    },
    "nmrsim": dict(ORACLE_DEPENDENCY_PINS),
}


def candidate_distribution_pins(
    python_version: tuple[int, int], toolkits: Iterable[str] = ()
) -> dict[str, str]:
    """Return the exact distributions that a candidate runtime must validate."""
    try:
        pins = dict(BASE_CANDIDATE_PINS[tuple(python_version)])
    except KeyError as exc:
        raise RuntimeError(
            "candidate package pins do not support Python %d.%d" % tuple(python_version)
        ) from exc
    for toolkit in toolkits:
        pins[toolkit] = ORACLE_PACKAGE_PINS[toolkit]
        pins.update(TOOLKIT_DEPENDENCY_PINS.get(toolkit, {}))
    return pins


def setup_requirements(python_version: tuple[int, int]) -> tuple[str, ...]:
    """Return one fully pinned transaction for scripts/setup_oracle_env.sh."""
    if tuple(python_version) != (3, 8):
        raise RuntimeError(
            "full oracle setup supports only certified Python 3.8; got Python %d.%d"
            % tuple(python_version)
        )
    pins = dict(ORACLE_PACKAGE_PINS)
    pins.update(candidate_distribution_pins(python_version))
    for dependencies in TOOLKIT_DEPENDENCY_PINS.values():
        pins.update(dependencies)
    for dependencies in TRUSTED_TOOLKIT_DEPENDENCY_PINS.values():
        pins.update(dependencies)
    return tuple("%s==%s" % item for item in pins.items())
