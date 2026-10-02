"""Plan future single-factor paired cohorts; never run them or touch a ledger.

One fresh campaign manifest supplies the shared worlds and private panels.
Derived arms change only round allowance OR snapshot availability. Distinct
episode/confirmation keys give independently keyed noise, not common random
numbers. Existing historical cohorts cannot be imported or relabelled as pairs.
"""

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import secrets

from .analysis_api import PROTOCOL as SNAPSHOT_PROTOCOL, contract as snapshot_contract
from .campaign import create_manifest
from .runner import DEFAULT_LIMITS, source_digest
from .seed_exclusions import (BINDING_FIELDS, load_exclusions, public_summary,
                              validate_manifest_binding)


PROTOCOL = "sle-prospective-paired-design-0.1"
FACTORS = ("rounds", "analysis_protocol")
_DESIGN_ID = re.compile(r"[a-z0-9][a-z0-9_-]{0,39}\Z")
_SHARED_FIELDS = ("protocol", "created_unix", "source_sha256", "score_contract", "runtime",
                  "task_profile", "presentation_profile", "sampling_policy", "environments",
                  "requested_model", "decoding", "reserved_development_world_seeds", "discovery_depth")


def _shared_contract(manifest):
    fields = _SHARED_FIELDS + tuple(key for key in BINDING_FIELDS if key in manifest)
    return {key: deepcopy(manifest[key]) for key in fields}


def _exclusion_summary(manifest):
    exclusions = validate_manifest_binding(manifest)
    return {} if exclusions is None else {"seed_exclusions": public_summary(exclusions)}


def _hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def _integer(value, low, high, label):
    if type(value) is not int or not low <= value <= high:
        raise ValueError("%s must be an integer in [%d,%d]" % (label, low, high))
    return value


def _settings(factor, values, rounds, closing_opportunities, analysis_protocol):
    if factor not in FACTORS:
        raise ValueError("factor must be rounds or analysis_protocol")
    if not isinstance(values, (list, tuple)) or not 2 <= len(values) <= 4:
        raise ValueError("provide two to four distinct factor values")
    closing = _integer(closing_opportunities, 2, 31, "closing_opportunities")
    if factor == "rounds":
        if rounds is not None:
            raise ValueError("rounds factor must use values, not a second rounds setting")
        protocol = "legacy" if analysis_protocol is None else analysis_protocol
        if protocol not in ("legacy", SNAPSHOT_PROTOCOL):
            raise ValueError("unsupported shared analysis protocol")
        settings = [{"rounds": _integer(value, closing + 1, 32, "rounds"),
                     "analysis_protocol": protocol} for value in values]
    else:
        if analysis_protocol is not None:
            raise ValueError("analysis_protocol factor must use values, not a second protocol setting")
        if len(values) != 2 or any(not isinstance(value, str) for value in values) or set(values) != {"legacy", SNAPSHOT_PROTOCOL}:
            raise ValueError("snapshot comparison requires exactly legacy and the declared snapshot protocol")
        count = _integer(16 if rounds is None else rounds, closing + 1, 32, "shared rounds")
        settings = [{"rounds": count, "analysis_protocol": value} for value in values]
    if len(set(values)) != len(values):
        raise ValueError("factor values must be distinct")
    return settings


def _fresh_confirmation(used):
    for _ in range(128):
        key = secrets.token_hex(16)
        if key not in used:
            used.add(key)
            return key
    raise ValueError("could not allocate distinct confirmation keys")


def create_paired_design(design_id, names, *, factor, values, instances=5, rounds=None,
                         closing_opportunities=2, analysis_protocol=None,
                         task_profile="open_discovery", presentation_profile="full_description",
                         balanced_strata=(), seed_exclusions=None):
    """Return private manifests/index and a counts-only public summary.

    ``factor='rounds'`` uses values such as [8,16]; shared analysis_protocol may
    be chosen. ``factor='analysis_protocol'`` uses ['legacy', SNAPSHOT_PROTOCOL]
    and a shared rounds count. No per-arm override dictionary is accepted.
    """
    if not isinstance(design_id, str) or not _DESIGN_ID.fullmatch(design_id):
        raise ValueError("invalid design id; use 1..40 lowercase letters/digits/_/-")
    settings = _settings(factor, values, rounds, closing_opportunities, analysis_protocol)
    # This creates only an in-memory frozen plan. It does not run simulations,
    # model requests, a cohort executor, or any ledger constructor.
    template = create_manifest(design_id + "-sampling", names, instances=instances,
        rounds=settings[0]["rounds"], exploration_rounds=settings[0]["rounds"] - closing_opportunities,
        task_profile=task_profile, presentation_profile=presentation_profile,
        balanced_strata=balanced_strata, analysis_protocol=settings[0]["analysis_protocol"],
        seed_exclusions=seed_exclusions)
    used_keys = {row["confirmation_key"] for row in template["instances"]}
    manifests, arm_rows = {}, []
    for index, setting in enumerate(settings):
        arm = "a%d" % (index + 1)
        cohort = design_id + "-" + arm
        manifest = deepcopy(template)
        manifest["cohort"] = cohort
        manifest["limits"]["rounds"] = setting["rounds"]
        manifest["limits"]["exploration_rounds"] = setting["rounds"] - closing_opportunities
        manifest["analysis_protocol"] = setting["analysis_protocol"]
        manifest["analysis_contract"] = snapshot_contract() if setting["analysis_protocol"] == SNAPSHOT_PROTOCOL else None
        for ordinal, row in enumerate(manifest["instances"]):
            row["cohort"] = cohort
            row["episode_id"] = "%s-p%03d" % (cohort, ordinal + 1)
            row["confirmation_key"] = _fresh_confirmation(used_keys)
            row["analysis_protocol"] = setting["analysis_protocol"]
        manifest["planned_max_api_attempts"] = len(manifest["instances"]) * setting["rounds"]
        manifests[arm] = manifest
        arm_rows.append({"arm": arm, "value": values[index], "cohort": cohort,
                         "manifest_sha256": _hash(manifest)})
    pairs = []
    for index, row in enumerate(template["instances"]):
        pair = {"pair_id": "%s-p%03d" % (design_id, index + 1),
                "environment": row["environment"], "world_seed": row["world_seed"],
                "panel_seed": row["panel_seed"], "panel_hashes": deepcopy(row["panel_hashes"]),
                "members": [{"arm": arm["arm"], "cohort": arm["cohort"],
                             "episode_id": manifests[arm["arm"]]["instances"][index]["episode_id"]} for arm in arm_rows]}
        if "operator_sampling_stratum" in row:
            pair["operator_sampling_stratum"] = row["operator_sampling_stratum"]
        pairs.append(pair)
    public = {"protocol": PROTOCOL, "plan_only": True, "planned_pairs": len(pairs),
              "planned_arms": len(manifests), "planned_episodes": len(pairs) * len(manifests),
              "planned_max_api_attempts": sum(m["planned_max_api_attempts"] for m in manifests.values()),
              "ledger_modified": False}
    public.update(_exclusion_summary(template))
    result = {"protocol": PROTOCOL, "design_id": design_id, "factor": factor, "values": list(values),
              "closing_opportunities": closing_opportunities, "arms": arm_rows,
              "shared_contract": _shared_contract(template),
              "pair_index": pairs, "manifests": manifests, "public_summary": public,
              "interpretation": {
                  "prospective_only": "Fresh sampling before execution; historical cohorts cannot be retroactively treated as paired.",
                  "single_factor": "Round allowance (with exploration derived from fixed closing slots), OR snapshot interface availability. Other supplied scientific/model/resource settings are fixed.",
                  "noise": "Each arm has unique episode IDs and confirmation keys. Exploration keys are episode_id:observation_id; measurement streams are independently keyed, not common random numbers. Model sampling is not seed-controlled.",
                  "closing": "The scheduled closing-only slots are fixed. The existing identical wall-time rule can still force earlier closure; nominal rounds do not guarantee consumed rounds.",
                  "budget": "Maximum attempts are the sum over all planned episodes and arms, including invalid model turns. This planner does not inspect/create/extend any ledger, authorize calls or alter the existing 352-attempt cap.",
                  "execution": "No execution or execution-order assignment is performed. A future operator must check available budget, source freeze and scheduling/order effects before separately authorizing a run.",
                  "inference": "No outcomes are collected and no performance or scaling claim follows from this plan."}}
    validate_design(result)
    if source_digest() != template["source_sha256"]:
        raise ValueError("source changed while planning; freeze from one immutable checkout")
    return result


def _normalize(manifest, factor):
    value = deepcopy(manifest)
    for field in ("cohort", "planned_max_api_attempts"):
        value.pop(field)
    if factor == "rounds":
        value["limits"].pop("rounds")
        value["limits"].pop("exploration_rounds")
    else:
        value.pop("analysis_protocol")
        value.pop("analysis_contract")
    for row in value["instances"]:
        for field in ("episode_id", "cohort", "confirmation_key"):
            row.pop(field)
        if factor == "analysis_protocol":
            row.pop("analysis_protocol")
    return value


def validate_design(design):
    """Fail closed on unintended arm differences before writing any artifact."""
    if not isinstance(design, dict) or design.get("protocol") != PROTOCOL:
        raise ValueError("invalid paired design protocol")
    factor, values = design["factor"], design["values"]
    manifests, pairs, arms = design["manifests"], design["pair_index"], design["arms"]
    if not isinstance(manifests, dict) or len(manifests) != len(values) or len(arms) != len(values) or not pairs:
        raise ValueError("invalid arm/pair count")
    expected_ids = ["a%d" % (index + 1) for index in range(len(values))]
    if list(manifests) != expected_ids or [arm["arm"] for arm in arms] != expected_ids:
        raise ValueError("invalid arm identity/order")
    first = manifests[expected_ids[0]]
    validate_manifest_binding(first)
    settings = _settings(factor, values,
                         first["limits"]["rounds"] if factor == "analysis_protocol" else None,
                         design["closing_opportunities"], first["analysis_protocol"] if factor == "rounds" else None)
    reference = _normalize(first, factor)
    if _shared_contract(first) != design["shared_contract"]:
        raise ValueError("shared frozen contract changed")
    episode_ids, confirmation_keys = set(), set()
    for arm_index, (arm, setting) in enumerate(zip(arms, settings)):
        manifest = manifests[arm["arm"]]
        validate_manifest_binding(manifest)
        if _normalize(manifest, factor) != reference:
            raise ValueError("non-factor arm difference detected")
        if manifest["cohort"] != design["design_id"] + "-" + arm["arm"] or arm["cohort"] != manifest["cohort"] or arm["value"] != values[arm_index]:
            raise ValueError("arm metadata mismatch")
        if _hash(manifest) != arm["manifest_sha256"]:
            raise ValueError("arm manifest hash changed")
        expected_limits = dict(DEFAULT_LIMITS, rounds=setting["rounds"], exploration_rounds=setting["rounds"] - design["closing_opportunities"])
        if manifest["limits"] != expected_limits:
            raise ValueError("non-factor resource limits changed")
        protocol = setting["analysis_protocol"]
        if manifest["analysis_protocol"] != protocol or manifest["analysis_contract"] != (snapshot_contract() if protocol == SNAPSHOT_PROTOCOL else None):
            raise ValueError("analysis protocol/contract mismatch")
        if len(manifest["instances"]) != len(pairs) or manifest["planned_max_api_attempts"] != len(pairs) * setting["rounds"]:
            raise ValueError("invalid episode or request count")
        for index, row in enumerate(manifest["instances"]):
            if row["episode_id"] in episode_ids or row["confirmation_key"] in confirmation_keys:
                raise ValueError("episode ids and confirmation keys must be independent across arms")
            if row["episode_id"] != "%s-p%03d" % (manifest["cohort"], index + 1) or row["cohort"] != manifest["cohort"] or row["analysis_protocol"] != protocol:
                raise ValueError("episode arm identity mismatch")
            if not isinstance(row["confirmation_key"], str) or not re.fullmatch(r"[0-9a-f]{32}", row["confirmation_key"]):
                raise ValueError("invalid confirmation key")
            episode_ids.add(row["episode_id"])
            confirmation_keys.add(row["confirmation_key"])
            pair = pairs[index]
            if pair["pair_id"] != "%s-p%03d" % (design["design_id"], index + 1):
                raise ValueError("invalid pair identity")
            for field in ("environment", "world_seed", "panel_seed", "panel_hashes"):
                if row[field] != pair[field]:
                    raise ValueError("paired world/panel mismatch")
            if row.get("operator_sampling_stratum") != pair.get("operator_sampling_stratum"):
                raise ValueError("paired stratum mismatch")
            expected_member = {"arm": arm["arm"], "cohort": manifest["cohort"], "episode_id": row["episode_id"]}
            members = [member for member in pair["members"] if member.get("arm") == arm["arm"]]
            if len(pair["members"]) != len(arms) or members != [expected_member]:
                raise ValueError("pair membership mismatch")
    public = {"protocol": PROTOCOL, "plan_only": True, "planned_pairs": len(pairs), "planned_arms": len(arms),
              "planned_episodes": len(episode_ids), "planned_max_api_attempts": sum(m["planned_max_api_attempts"] for m in manifests.values()), "ledger_modified": False}
    public.update(_exclusion_summary(first))
    if design["public_summary"] != public:
        raise ValueError("public counts or allowlist mismatch")
    json.dumps(design, allow_nan=False)
    return deepcopy(public)


def write_design(design, output):
    """Write new private manifests/index and a counts-only summary; no execution."""
    public = validate_design(design)
    if source_digest() != design["shared_contract"]["source_sha256"]:
        raise ValueError("source changed after planning; do not relabel a stale design")
    index = {key: deepcopy(value) for key, value in design.items() if key != "manifests"}
    encoded = {"paired-index-private.json": json.dumps(index, indent=2, sort_keys=True, allow_nan=False),
               "public-summary.json": json.dumps(public, indent=2, sort_keys=True, allow_nan=False)}
    for arm, manifest in design["manifests"].items():
        encoded[arm + "-manifest-private.json"] = json.dumps(manifest, indent=2, sort_keys=True, allow_nan=False)
    output = Path(output)
    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    for name, value in encoded.items():
        with (output / name).open("x", encoding="utf-8") as stream:
            stream.write(value + "\n")
        (output / name).chmod(0o600)
    return public


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--design-id", required=True)
    parser.add_argument("--environments", required=True)
    parser.add_argument("--factor", required=True, choices=FACTORS)
    parser.add_argument("--values", required=True, help="Comma-separated round counts OR analysis protocol names")
    parser.add_argument("--instances", type=int, default=5)
    parser.add_argument("--rounds", type=int, help="Shared count, only for snapshot-factor plans")
    parser.add_argument("--analysis-protocol", help="Shared protocol, only for rounds-factor plans")
    parser.add_argument("--closing-opportunities", type=int, default=2)
    parser.add_argument("--task-profile", default="open_discovery")
    parser.add_argument("--presentation-profile", default="full_description")
    parser.add_argument("--balanced-strata", default="")
    parser.add_argument("--seed-exclusions-file", help="explicit operator-only JSON world-seed exclusion list")
    parser.add_argument("--output", required=True, help="New plan directory; existing directories are never overwritten")
    args = parser.parse_args()
    exclusions = load_exclusions(args.seed_exclusions_file) if args.seed_exclusions_file else None
    values = [int(value) for value in args.values.split(",")] if args.factor == "rounds" else args.values.split(",")
    design = create_paired_design(args.design_id, args.environments.split(","), factor=args.factor, values=values,
        instances=args.instances, rounds=args.rounds, closing_opportunities=args.closing_opportunities,
        analysis_protocol=args.analysis_protocol, task_profile=args.task_profile,
        presentation_profile=args.presentation_profile, balanced_strata=args.balanced_strata.split(",") if args.balanced_strata else (),
        seed_exclusions=exclusions)
    print(json.dumps(write_design(design, args.output), sort_keys=True))


if __name__ == "__main__":
    main()
