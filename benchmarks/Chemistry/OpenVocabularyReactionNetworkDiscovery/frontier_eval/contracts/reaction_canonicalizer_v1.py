"""Stable novelty identities for verified graph-reaction claims."""
from __future__ import annotations

import hashlib
import json

NOVELTY_NAMESPACE = "sle/open-vocabulary-reaction-network/edge/v1"


def canonical_reaction_id(condition, reactant_key, product_key):
    semantic_condition = {
        key: condition[key]
        for key in ("favoured_pair", "barrier_offset", "barrier_limit")
    }
    payload = {
        "namespace": NOVELTY_NAMESPACE,
        "condition": semantic_condition,
        "reactant": reactant_key,
        "product": product_key,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return NOVELTY_NAMESPACE + ":sha256:" + hashlib.sha256(encoded.encode()).hexdigest()
