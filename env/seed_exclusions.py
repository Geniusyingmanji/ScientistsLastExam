"""Explicit operator-owned world-seed exclusions; no world execution or discovery."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import stat

from .registry import ENVIRONMENTS


PROTOCOL = "sle-seed-exclusions-0.1"
COHORT_PROTOCOL = "sle-pilot-cohort-0.5"
LEGACY_RESERVED = (7, 46, 1439, 8743)
MAX_JSON_BYTES = 262144
MAX_SEEDS_PER_WORLD = 4096
MAX_TOTAL_SEEDS = 16384
MAX_WORLD_SEED_DRAWS = 4096
BINDING_FIELDS = ("seed_exclusions", "seed_exclusions_sha256")


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON object key")
        result[key] = value
    return result


def _invalid_constant(value):
    raise ValueError("nonfinite JSON number")


def strict_json_loads(text):
    """Also used for manifest loading so duplicate binding fields fail closed."""
    try:
        return json.loads(text, object_pairs_hook=_unique_object, parse_constant=_invalid_constant)
    except (json.JSONDecodeError, UnicodeError, RecursionError) as error:
        raise ValueError("invalid JSON document") from error


def validate_exclusions(value):
    if type(value) is not dict or set(value) != {"protocol", "environments"} or value["protocol"] != PROTOCOL:
        raise ValueError("invalid seed exclusion protocol or fields")
    mapping = value["environments"]
    if type(mapping) is not dict or len(mapping) > len(ENVIRONMENTS):
        raise ValueError("invalid seed exclusion environment map")
    if any(type(name) is not str or name not in ENVIRONMENTS for name in mapping):
        raise ValueError("unknown exclusion environment")
    total, canonical = 0, {}
    for name in sorted(mapping):
        seeds = mapping[name]
        if type(seeds) is not list or len(seeds) > MAX_SEEDS_PER_WORLD:
            raise ValueError("seed exclusion list exceeds per-world bound")
        if any(type(seed) is not int or not 0 <= seed < 2**31 for seed in seeds):
            raise ValueError("excluded seeds must be integers in [0,2**31-1]")
        if any(right <= left for left, right in zip(seeds, seeds[1:])):
            raise ValueError("excluded seeds must be sorted and unique")
        total += len(seeds)
        if total > MAX_TOTAL_SEEDS:
            raise ValueError("seed exclusions exceed total bound")
        canonical[name] = list(seeds)
    result = {"protocol": PROTOCOL, "environments": canonical}
    if len(json.dumps(result, sort_keys=True, separators=(",", ":")).encode("utf-8")) > MAX_JSON_BYTES:
        raise ValueError("seed exclusion document exceeds byte bound")
    return result


def parse_exclusions(text):
    if not isinstance(text, str):
        raise ValueError("seed exclusions must be a JSON text document")
    try:
        size = len(text.encode("utf-8"))
    except UnicodeError as error:
        raise ValueError("invalid UTF-8 seed exclusion document") from error
    if size > MAX_JSON_BYTES:
        raise ValueError("seed exclusion document exceeds byte bound")
    return validate_exclusions(strict_json_loads(text))


def load_exclusions(path):
    """Read only the explicit operator path, with a bounded binary read."""
    path = Path(path)
    metadata = path.stat()
    if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > MAX_JSON_BYTES:
        raise ValueError("seed exclusion file must be regular and within byte bound")
    with path.open("rb") as stream:
        content = stream.read(MAX_JSON_BYTES + 1)
    if len(content) > MAX_JSON_BYTES:
        raise ValueError("seed exclusion document exceeds byte bound")
    try:
        text = content.decode("utf-8")
    except UnicodeError as error:
        raise ValueError("invalid UTF-8 seed exclusion document") from error
    return parse_exclusions(text)


def exclusion_hash(value):
    canonical = validate_exclusions(value)
    return hashlib.sha256(json.dumps(canonical, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode("utf-8")).hexdigest()


def exclusion_binding(value):
    if value is None:
        return {}
    canonical = validate_exclusions(value)
    return {"seed_exclusions": canonical, "seed_exclusions_sha256": exclusion_hash(canonical)}


def public_summary(value):
    canonical = validate_exclusions(value)
    return {"protocol": PROTOCOL, "environment_count": len(canonical["environments"]),
            "seed_count": sum(len(seeds) for seeds in canonical["environments"].values()),
            "sha256": exclusion_hash(canonical)}


def validate_manifest_binding(manifest):
    """Legacy manifests stay legacy; explicit bindings are checked before effects.

    This is a consistency check, not authentication against coherent rewriting
    of every field/protocol/hash. Operators retain their immutable source plan.
    """
    if not isinstance(manifest, dict):
        raise ValueError("invalid cohort manifest")
    fields = set(BINDING_FIELDS).intersection(manifest)
    rows = manifest.get("instances", [])
    row_binding = isinstance(rows, list) and any(isinstance(row, dict) and
                   "seed_exclusions_sha256" in row for row in rows)
    if not fields and not row_binding and manifest.get("protocol") != COHORT_PROTOCOL:
        return None
    if fields != set(BINDING_FIELDS) or manifest.get("protocol") != COHORT_PROTOCOL:
        raise ValueError("missing or mismatched seed exclusion binding")
    exclusions = validate_exclusions(manifest["seed_exclusions"])
    digest = exclusion_hash(exclusions)
    if type(manifest["seed_exclusions_sha256"]) is not str or manifest["seed_exclusions_sha256"] != digest:
        raise ValueError("seed exclusion hash mismatch")
    if manifest.get("reserved_development_world_seeds") != list(LEGACY_RESERVED):
        raise ValueError("legacy reserved-seed policy changed")
    names = manifest.get("environments")
    if (type(names) is not list or not names or len(names) > len(ENVIRONMENTS) or
            any(type(name) is not str or name not in ENVIRONMENTS for name in names) or len(set(names)) != len(names)):
        raise ValueError("invalid bound environment selection")
    if type(rows) is not list or not 1 <= len(rows) <= 30*len(names):
        raise ValueError("invalid bound cohort rows")
    for row in rows:
        if not isinstance(row, dict) or row.get("environment") not in names:
            raise ValueError("invalid bound row environment")
        if row.get("seed_exclusions_sha256") != digest:
            raise ValueError("row seed exclusion binding mismatch")
        seed = row.get("world_seed")
        if type(seed) is not int or not 0 <= seed < 2**31:
            raise ValueError("invalid bound world seed")
        if seed in LEGACY_RESERVED or seed in exclusions["environments"].get(row["environment"], []):
            raise ValueError("cohort row uses an excluded world seed")
    return deepcopy(exclusions)
