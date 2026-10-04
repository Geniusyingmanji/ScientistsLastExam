"""Explicit frozen cohorts and process-level episode concurrency."""
import concurrent.futures
import json
import multiprocessing
import os
import re
import secrets
import sys
import time
from pathlib import Path

from sle.llm import LLMConfig
from .ledger import CampaignLedger
from .microecology.agent import save_json
from .registry import ENVIRONMENTS, load_world
from .runner import DEFAULT_LIMITS, run_episode, source_digest
from .scoring import canonical_hash, score_contract
from .transport import CampaignClient
from .task_profiles import get_task_profile
from .presentation_profiles import get_presentation_profile
from .analysis_api import PROTOCOL as SNAPSHOT_PROTOCOL, contract as snapshot_contract
from .seed_exclusions import (COHORT_PROTOCOL, LEGACY_RESERVED, MAX_WORLD_SEED_DRAWS,
                              exclusion_binding, strict_json_loads, validate_manifest_binding)


def create_manifest(cohort, names, instances=5, rounds=16, exploration_rounds=14, task_profile="open_discovery", presentation_profile="full_description", balanced_strata=(), analysis_protocol="legacy", seed_exclusions=None):
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,63}", cohort):
        raise ValueError("invalid cohort identifier")
    if not names or len(set(names)) != len(names) or any(n not in ENVIRONMENTS for n in names):
        raise ValueError("unknown or repeated environment")
    if type(instances) is not int or not 1 <= instances <= 30:
        raise ValueError("instances must be 1..30")
    if not 3 <= rounds <= 32 or not 1 <= exploration_rounds <= rounds-2:
        raise ValueError("rounds must leave at least 2 submission opportunities")
    if analysis_protocol not in ("legacy", SNAPSHOT_PROTOCOL):
        raise ValueError("unsupported analysis protocol")
    if (not isinstance(balanced_strata, (list, tuple)) or
            any(not isinstance(name, str) or name not in names for name in balanced_strata) or
            len(set(balanced_strata)) != len(balanced_strata)):
        raise ValueError("balanced strata must explicitly name distinct selected environments")
    binding = exclusion_binding(seed_exclusions)
    excluded = binding.get("seed_exclusions", {}).get("environments", {})
    limits = dict(DEFAULT_LIMITS, rounds=rounds, exploration_rounds=exploration_rounds)
    profile = get_task_profile(task_profile)
    presentation = get_presentation_profile(presentation_profile, task_profile=profile)
    for name in names:
        get_presentation_profile(presentation_profile, name)
    rows = []
    for index in range(instances):
        for name in names:
            reserved = set(LEGACY_RESERVED) | set(excluded.get(name, [])) | {r["world_seed"] for r in rows}
            remaining_draws = MAX_WORLD_SEED_DRAWS

            def draw_world_seed():
                nonlocal remaining_draws
                while remaining_draws:
                    remaining_draws -= 1
                    seed = secrets.randbelow(2**31)
                    if seed not in reserved:
                        return seed
                raise ValueError("bounded world-seed sampling exhausted before cohort freeze")

            world_seed = draw_world_seed()
            panel_seed = secrets.randbelow(2**31)
            world, _ = load_world(name, world_seed)
            stratum = None
            if name in balanced_strata:
                labels = getattr(world, "operator_strata", ())
                if not labels or not all(isinstance(label, str) for label in labels) or not callable(getattr(world, "operator_stratum", None)):
                    raise ValueError("environment does not declare trusted operator strata")
                stratum = labels[index % len(labels)]
                for attempt in range(128):
                    if world.operator_stratum() == stratum:
                        break
                    world_seed = draw_world_seed()
                    world, _ = load_world(name, world_seed)
                else:
                    raise ValueError("bounded stratum sampling exhausted before cohort freeze")
            row = {"episode_id": "%s-%s-%02d" % (cohort, name, index+1),
                   "cohort": cohort, "environment": name, "world_seed": world_seed,
                   "panel_seed": panel_seed, "confirmation_key": secrets.token_hex(16), "task_profile": task_profile,
                   "presentation_profile": presentation_profile, "analysis_protocol": analysis_protocol}
            if stratum is not None:
                row["operator_sampling_stratum"] = stratum
            if binding:
                row["seed_exclusions_sha256"] = binding["seed_exclusions_sha256"]
            row["panel_hashes"] = {kind: canonical_hash(world.panel(panel_seed, kind, limits["panel_count"]))
                                   for kind in ("conditions", "interventions")}
            rows.append(row)
    import numpy, scipy
    manifest = {"protocol": COHORT_PROTOCOL if binding else "sle-pilot-cohort-0.4", "cohort": cohort, "created_unix": time.time(),
            "analysis_protocol": analysis_protocol,
            "analysis_contract": snapshot_contract() if analysis_protocol == SNAPSHOT_PROTOCOL else None,
            "presentation_profile": presentation,
            "sampling_policy": {"balanced_strata_environments": list(balanced_strata),
                                "allocation": "Cycle declared operator strata in instance order; counts differ by at most one. Unlisted worlds use unrestricted random instances. Strata never enter the public problem."},
            "task_profile": profile, "runtime": {"python": sys.version, "numpy": numpy.__version__, "scipy": scipy.__version__},
            "source_sha256": source_digest(), "score_contract": score_contract(), "limits": limits,
            "reserved_development_world_seeds": list(LEGACY_RESERVED),
            "environments": names, "instances": rows, "planned_max_api_attempts": len(rows)*rounds,
            "requested_model": "gpt-5.6-sol", "decoding": {
                "wire": "chat", "reasoning_effort": "medium", "max_output_tokens": 8000,
                "chat_max_tokens_field": "max_completion_tokens", "temperature": None,
                "stream": False, "timeout_seconds": 180},
            "discovery_depth": "separate evidence audit; no model-name or hidden-recipe rubric"}
    manifest.update(binding)
    validate_manifest_binding(manifest)
    return manifest


def _run_one(instance, limits, directory, config_path, ledger_path, workers, rpm, expected_source, expected_decoding):
    # Spawned process, never start the sandbox's preexec_fn from a thread pool.
    os.environ.update(OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1", MKL_NUM_THREADS="1")
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=False)
    save_json(directory/"started.json", {"episode_id": instance["episode_id"], "environment": instance["environment"],
                                       "cohort": instance["cohort"], "started_unix": time.time()})
    if source_digest() != expected_source:
        raise ValueError("source changed after cohort freeze")
    raw = json.loads(Path(config_path).read_text(encoding="utf-8"))
    config = LLMConfig.from_dict(raw.get("llm", raw))
    if config.model != expected_decoding.get("model", "gpt-5.6-sol"):
        raise ValueError("campaign model differs from frozen configuration")
    if {k: getattr(config, k) for k in expected_decoding} != expected_decoding:
        raise ValueError("actual decoding differs from frozen protocol")
    client = CampaignClient(config, directory, CampaignLedger(ledger_path), instance["episode_id"],
                            max_attempts=limits["rounds"], active_limit=workers, rpm=rpm)
    report = run_episode(instance, limits, directory, client)
    return {k: report[k] for k in ("episode_id", "environment", "status", "score", "stop_reason", "experiment_count")}


def run_cohort(manifest_path, config_path, campaign_root, *, workers=8, rpm=60):
    manifest = strict_json_loads(Path(manifest_path).read_text(encoding="utf-8"))
    validate_manifest_binding(manifest)
    if not 1 <= workers <= 16 or not 1 <= rpm <= 120:
        raise ValueError("workers must be 1..16 and rpm 1..120")
    if manifest["source_sha256"] != source_digest():
        raise ValueError("source changed after cohort manifest freeze")
    if manifest["score_contract"] != score_contract():
        raise ValueError("scoring contract changed after manifest freeze")
    analysis_protocol = manifest.get("analysis_protocol", "legacy")
    if analysis_protocol not in ("legacy", SNAPSHOT_PROTOCOL):
        raise ValueError("unsupported frozen analysis protocol")
    expected_analysis = snapshot_contract() if analysis_protocol == SNAPSHOT_PROTOCOL else None
    if manifest.get("analysis_contract") != expected_analysis:
        raise ValueError("analysis contract changed after manifest freeze")
    if any(row.get("analysis_protocol", "legacy") != analysis_protocol for row in manifest["instances"]):
        raise ValueError("instance analysis protocol differs from frozen cohort")
    root = Path(campaign_root)
    ledger = CampaignLedger(root/"campaign-ledger.sqlite")
    directory = root/manifest["cohort"]
    directory.mkdir(exist_ok=False)
    save_json(directory/"manifest-private.json", manifest)
    metadata = {"status": "running", "started_unix": time.time(), "workers": workers, "rpm": rpm,
                "planned_episodes": len(manifest["instances"]), "finished": [], "errors": []}
    save_json(directory/"campaign-status.json", metadata)
    if ledger.summary()["remaining_attempts"] < manifest["planned_max_api_attempts"]:
        raise ValueError("remaining shared attempt budget cannot cover this frozen cohort")
    (directory/"episodes").mkdir()
    context = multiprocessing.get_context("spawn")
    with concurrent.futures.ProcessPoolExecutor(max_workers=workers, mp_context=context) as pool:
        future_ids = {pool.submit(_run_one, row, manifest["limits"], str(directory/"episodes"/row["episode_id"]),
                                  str(Path(config_path).resolve()), str(root/"campaign-ledger.sqlite"), workers, rpm,
                                  manifest["source_sha256"], manifest["decoding"]): row["episode_id"]
                      for row in manifest["instances"]}
        for future in concurrent.futures.as_completed(future_ids):
            try:
                item = future.result()
                metadata["finished"].append(item)
                print(json.dumps(item, ensure_ascii=False), flush=True)
            except Exception as exc:
                item = {"episode_id": future_ids[future], "exception_type": type(exc).__name__}
                metadata["errors"].append(item)
                instance = next(r for r in manifest["instances"] if r["episode_id"] == item["episode_id"])
                failed_dir = directory/"episodes"/item["episode_id"]
                failed_dir.mkdir(exist_ok=True)
                if not (failed_dir/"started.json").exists():
                    save_json(failed_dir/"started.json", dict(item, environment=instance["environment"], stage="dispatch_failed"))
                prior = json.loads((failed_dir/"report.json").read_text()) if (failed_dir/"report.json").exists() else {}
                prior.update(dict(item, environment=instance["environment"], status="failed",
                             infrastructure_failure="worker_or_dispatch_failure", score=None,
                             model_completed=False, stop_reason=type(exc).__name__, cohort=manifest["cohort"]))
                save_json(failed_dir/"report.json", prior)
                print(json.dumps(item), flush=True)
            metadata["ledger"] = ledger.summary()
            save_json(directory/"campaign-status.json", metadata)
    metadata.update(status="completed", finished_unix=time.time())
    save_json(directory/"campaign-status.json", metadata)
    from .reporting import render_report
    render_report(directory)
    return metadata
