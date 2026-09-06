"""Path-free identities for trusted evaluator runtimes."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import re
import sys
import sysconfig
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .oracle_package_pins import (
    TOOLKIT_DEPENDENCY_PINS,
    TRUSTED_TOOLKIT_DEPENDENCY_PINS,
)


@dataclass(frozen=True)
class TrustedRuntime:
    """Private launch path paired with its public, path-free identity."""

    executable: str
    descriptor: dict

    @property
    def fingerprint_sha256(self) -> str:
        return str(self.descriptor["fingerprint_sha256"])


def _distribution_name(value: str) -> str:
    return re.sub(r"[-_.]+", "-", str(value).strip()).lower()


def _fingerprint(value: dict) -> str:
    payload = json.dumps(
        value, allow_nan=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _is_path_free(value: str) -> bool:
    return not any(marker in value for marker in ("/", "\\", "\0"))


def current_runtime_descriptor(distributions: Iterable[str] = ()) -> dict:
    """Describe the active Python ABI and selected distributions without host paths."""

    versions = {}
    for raw_name in sorted({_distribution_name(name) for name in distributions}):
        try:
            versions[raw_name] = importlib.metadata.version(raw_name)
        except importlib.metadata.PackageNotFoundError:
            versions[raw_name] = None
    identity = {
        "schema_version": 1,
        "implementation": sys.implementation.name,
        "python_version": "%d.%d.%d" % sys.version_info[:3],
        "cache_tag": sys.implementation.cache_tag,
        "soabi": str(sysconfig.get_config_var("SOABI") or ""),
        "distributions": versions,
    }
    return {**identity, "fingerprint_sha256": _fingerprint(identity)}


def validate_runtime_descriptor(value: object) -> dict:
    """Validate a descriptor received from a separately launched interpreter."""

    if not isinstance(value, dict):
        raise ValueError("trusted runtime descriptor must be an object")
    expected_keys = {
        "schema_version", "implementation", "python_version", "cache_tag",
        "soabi", "distributions", "fingerprint_sha256",
    }
    if set(value) != expected_keys or value.get("schema_version") != 1:
        raise ValueError("trusted runtime descriptor schema is invalid")
    identity = {key: value[key] for key in expected_keys - {"fingerprint_sha256"}}
    distributions = identity.get("distributions")
    if not isinstance(distributions, dict) or any(
        not isinstance(name, str)
        or not _is_path_free(name)
        or (version is not None and not isinstance(version, str))
        or (isinstance(version, str) and not _is_path_free(version))
        for name, version in distributions.items()
    ):
        raise ValueError("trusted runtime distribution identity must be path-free")
    for key in ("implementation", "python_version", "cache_tag", "soabi"):
        if (
            not isinstance(identity.get(key), str)
            or not identity[key]
            or not _is_path_free(identity[key])
        ):
            raise ValueError("trusted runtime Python identity must be path-free")
    if value.get("fingerprint_sha256") != _fingerprint(identity):
        raise ValueError("trusted runtime fingerprint differs from descriptor")
    return dict(value)


def task_runtime_distributions(task_dir: Path | None) -> tuple[str, ...]:
    """Return the direct and audited transitive distributions used by one oracle."""

    names = {"numpy", "scipy"}
    if task_dir is not None:
        requirements = Path(task_dir) / "verification" / "requirements.txt"
        if requirements.is_file():
            for raw_line in requirements.read_text(encoding="utf-8").splitlines():
                line = raw_line.split("#", 1)[0].strip()
                match = re.match(r"^([A-Za-z0-9][A-Za-z0-9._-]*)", line)
                if match:
                    names.add(_distribution_name(match.group(1)))
    dependency_map = {}
    for source in (TOOLKIT_DEPENDENCY_PINS, TRUSTED_TOOLKIT_DEPENDENCY_PINS):
        for name, dependencies in source.items():
            dependency_map.setdefault(_distribution_name(name), set()).update(
                _distribution_name(value) for value in dependencies
            )
    for name in tuple(names):
        names.update(dependency_map.get(name, ()))
    return tuple(sorted(names))


def main(argv: list[str] | None = None) -> int:
    descriptor = current_runtime_descriptor(sys.argv[1:] if argv is None else argv)
    print(json.dumps(descriptor, allow_nan=False, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
