"""Manufacturing-resolution canonical IDs for process archives."""
from __future__ import annotations

import hashlib
import json

NAMESPACE = "sle:process-microstructure-property:archive:v1"


def canonical_recipe_bins(process, fields, bounds, resolutions):
    return tuple(
        round((float(process[field]) - float(bounds[field][0]))
              / float(resolutions[field]))
        for field in fields
    )


def canonical_archive_id(processes, fields, bounds, resolutions):
    recipes = sorted({
        canonical_recipe_bins(process, fields, bounds, resolutions)
        for process in processes
    })
    encoded = json.dumps({"namespace": NAMESPACE, "recipes": recipes}, separators=(",", ":"))
    return NAMESPACE + ":sha256:" + hashlib.sha256(encoded.encode()).hexdigest()


def canonical_panel_archive_id(archive_ids):
    encoded = json.dumps(
        {"namespace": NAMESPACE, "world_archives": list(archive_ids)},
        separators=(",", ":"),
    )
    return NAMESPACE + ":panel:sha256:" + hashlib.sha256(encoded.encode()).hexdigest()
