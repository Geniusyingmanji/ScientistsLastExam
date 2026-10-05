"""Frozen 12-world evaluation and allowlisted live reporting.

This is a new campaign, never a rescore or retry of the historical cohorts.
Private manifests, model configurations and episode artifacts stay off the site.
"""
import argparse
import copy
import concurrent.futures
from datetime import datetime, timezone
import hashlib
import json
import multiprocessing
import os
from pathlib import Path
import secrets
from statistics import mean
import time
import tempfile

from .analysis_api import PROTOCOL as SNAPSHOT_PROTOCOL
from .campaign import _run_one
from .ledger import CampaignLedger
from .registry import load_world
from .runner import DEFAULT_LIMITS, source_digest
from .scoring import canonical_hash

ENVIRONMENTS = ("microecology", "coupled_oscillators", "reaction_kinetics", "heat_transport",
                "gene_regulation", "ising_spin", "hysteresis_material", "molecular_forces",
                "climate_response", "catalyst_aging", "field_ecology", "phase_equilibria")
LIMITS = dict(DEFAULT_LIMITS, rounds=16, exploration_rounds=14, experiments=48,
              experiment_units=30000, analysis_active_seconds=180, wall_seconds=3600,
              verification_reserve_seconds=300)
DECODING = dict(wire="chat", reasoning_effort="medium", max_output_tokens=8000,
                chat_max_tokens_field="max_completion_tokens", temperature=None,
                stream=False, timeout_seconds=180)
EXTENDED_BUDGET = dict(max_output_tokens=16000, timeout_seconds=900, wall_seconds=14400)


def utc():
    return datetime.now(timezone.utc).isoformat()


def write(path, value, *, new=False):
    path = Path(path)
    data = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    if new:
        with path.open("x") as handle:
            handle.write(data)
        path.chmod(0o600)
    else:
        fd, temporary = tempfile.mkstemp(prefix=".pending-", dir=str(path.parent))
        tmp = Path(temporary)
        try:
            with os.fdopen(fd, "w") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            tmp.replace(path)
        finally:
            if tmp.exists():
                tmp.unlink()


def freeze(root, exclusions, commit):
    from .unified_scoring import PROTOCOL, score_contract
    from .unified_panels import generate_panel
    root = Path(root)
    root.mkdir(mode=0o700, parents=True, exist_ok=False)
    excluded = json.loads(Path(exclusions).read_text())
    used = set(excluded["seeds"]) | {7, 46, 1439, 8743}
    instances = []
    for cluster in range(1, 4):
        for name in ENVIRONMENTS:
            for _ in range(4096):
                seed = secrets.randbelow(2**31)
                if seed not in used:
                    break
            else:
                raise ValueError("seed sampling exhausted")
            used.add(seed)
            world, _ = load_world(name, seed)
            panel_seed = secrets.randbelow(2**31)
            panel_hashes = {kind: canonical_hash(generate_panel(world, panel_seed, kind, LIMITS["panel_count"]))
                            for kind in ("conditions", "interventions")}
            for repeat in (1, 2):
                instances.append(dict(episode_id="unified-%s-i%d-r%d" % (name, cluster, repeat),
                                      cohort="unified12-v1", environment=name, world_seed=seed,
                                      panel_seed=panel_seed, panel_hashes=panel_hashes,
                                      confirmation_key=secrets.token_hex(16), task_profile="open_discovery",
                                      presentation_profile="full_description", analysis_protocol=SNAPSHOT_PROTOCOL,
                                      scoring_protocol=PROTOCOL, instance_index=cluster, repeat_index=repeat))
    instances.sort(key=lambda r: (r["instance_index"], r["repeat_index"], ENVIRONMENTS.index(r["environment"])))
    manifest = dict(schema="sle-unified-campaign-1", protocol=PROTOCOL, created_at=utc(),
                    source_commit=commit, source_sha256=source_digest(), score_contract=score_contract(),
                    limits=LIMITS, instances=instances, decoding=DECODING, model="gpt-5.6-sol",
                    planned_max_api_attempts=72*16, automatic_retries=0, replacement_episodes=0,
                    workers=8, rpm=60, seed_exclusion_sha256=canonical_hash(excluded),
                    seed_exclusion_count=len(excluded["seeds"]),
                    seed_exclusion_coverage=excluded.get("coverage", "known saved manifests only"),
                    aggregation="Each closed episode contributes its score or zero on failure; six episodes per environment; 12 environments equal. Also report model-only means excluding infrastructure failures.",
                    repeated_instance_policy="Two runs share the same hidden world and private prediction panels; independent exploration and claim measurement keys. Three independent clusters per environment.",
                    scope="Unified functional prediction/effect verification pilot; not a calibrated discovery-depth score or contamination-resistance proof.")
    manifest["manifest_sha256"] = canonical_hash(manifest)
    write(root/"manifest-private.json", manifest, new=True)
    write(root/"seed-exclusions-private.json", excluded, new=True)
    (root/"episodes").mkdir(mode=0o700)
    CampaignLedger(root/"attempts.sqlite", limit=72*16)
    export(root)
    return {"episodes": len(instances), "api_cap": 72*16, "manifest_sha256": manifest["manifest_sha256"]}


def load_manifest(root):
    value = json.loads((Path(root)/"manifest-private.json").read_text())
    if value["manifest_sha256"] != canonical_hash({k:v for k,v in value.items() if k != "manifest_sha256"}):
        raise ValueError("manifest hash mismatch")
    return value


def freeze_paired(root, reference_root, reference_source, config, commit, transport_pilot=None, client_pilot=None,
                  *, budget_profile="reference", prior_campaign=None, readiness_probe=None):
    """Replay a completed GPT reference design with a separately frozen model.

    No scientific file may change. Episode identifiers also remain fixed: this
    pairs observation-index noise and claim confirmation randomness across models.
    All outputs and ledgers live in a new directory, never in the reference.
    """
    from sle.llm import LLMConfig
    reference_root, reference_source = Path(reference_root), Path(reference_source)
    reference = load_manifest(reference_root)
    public = json.loads((reference_root / "public-progress.json").read_text())
    if reference["model"] != "gpt-5.6-sol" or public["status"] != "completed" or public["settled_episodes"] != 72:
        raise ValueError("paired reference must be the complete 72-run GPT campaign")
    if source_digest(reference_source) != reference["source_sha256"]:
        raise ValueError("reference source does not match its frozen digest")
    current = Path(__file__).resolve().parents[1]
    allowed = {"env/campaign.py", "env/unified_campaign.py", "sle/llm.py"}
    def files(base):
        return {str(p.relative_to(base)): p.read_bytes() for pkg in ("env", "sle")
                for p in (base / pkg).rglob("*.py")}
    before, after = files(reference_source), files(current)
    changed = sorted(k for k in before.keys() | after.keys() if before.get(k) != after.get(k))
    if set(changed) - allowed:
        raise ValueError("paired comparison changed scientific source: " + str(changed))
    raw = json.loads(Path(config).read_text())
    cfg = LLMConfig.from_dict(raw.get("llm", raw))
    if cfg.model not in ("deepseek-v4-pro", "deepseek-v4-pro-0813"):
        raise ValueError("this paired campaign requires the requested DeepSeek V4 Pro")
    decoding = dict(reference["decoding"], model=cfg.model, reasoning_effort="high",
                    chat_max_tokens_field="max_tokens", temperature=None, chat_reasoning_fallback=False,
                    stream=cfg.stream, chat_empty_response_as_text=cfg.stream)
    if budget_profile not in ("reference", "extended-output-v1"):
        raise ValueError("unknown prospective budget profile")
    budget_change = None
    previous = None
    if budget_profile == "extended-output-v1":
        if not cfg.stream or prior_campaign is None:
            raise ValueError("extended budget requires streaming and a preserved stopped campaign")
        if readiness_probe is None:
            raise ValueError("extended budget requires its completed unscored readiness probe")
        probe_path = Path(readiness_probe)
        probe = json.loads(probe_path.read_text())
        if (probe.get("scored") is not False or probe.get("attempts") != 1
                or probe.get("status") != "eof" or probe.get("max_tokens") != 16000
                or probe.get("sse_valid") is not True
                or probe.get("deadline_seconds") != 965 or probe.get("visible_characters", 0) <= 0
                or not isinstance(probe.get("terminal_seconds"), (int, float))
                or not 0 <= probe["terminal_seconds"] <= 965):
            raise ValueError("readiness probe did not return a complete visible response within its budget")
        prior_path = Path(prior_campaign) / "public-progress.json"
        prior = json.loads(prior_path.read_text())
        if (prior["status"] != "stopped_infrastructure" or prior["model"] != cfg.model
                or prior.get("comparison", {}).get("reference_manifest_sha256") != reference["manifest_sha256"]
                or prior.get("limits") != reference["limits"]
                or prior.get("decoding", {}).get("max_output_tokens") != 8000):
            raise ValueError("extended budget predecessor must be the stopped reference-budget comparison")
        previous = dict(public_sha256=hashlib.sha256(prior_path.read_bytes()).hexdigest(),
                        manifest_sha256=prior["manifest_sha256"], settled=prior["settled_episodes"],
                        calls=prior["ledger"]["started_attempts"],
                        policy="immutable earlier cohort; no scores, attempts or submissions are merged")
        budget_change = dict(profile=budget_profile, equal_budget=False,
                             fields={k: {"reference": reference["limits" if k == "wall_seconds" else "decoding"][k],
                                         "candidate": v} for k, v in EXTENDED_BUDGET.items()},
                             interpretation="same scientific tasks and scoring, different output and time budgets; descriptive system comparison, not an equal-budget model ranking")
        budget_change["readiness_probe"] = dict(sha256=hashlib.sha256(probe_path.read_bytes()).hexdigest(),
                                                scored=False, attempts=1, sse_valid=True, terminal_seconds=probe["terminal_seconds"],
                                                visible_characters=probe["visible_characters"])
        decoding.update({k: v for k, v in EXTENDED_BUDGET.items() if k != "wall_seconds"})
    if {k: getattr(cfg, k) for k in decoding} != decoding:
        raise ValueError("paired configuration differs from the declared adapter")
    pilot = None
    if cfg.stream:
        if transport_pilot is None:
            raise ValueError("streaming comparison must bind its failed nonstream transport pilot")
        pilot_path = Path(transport_pilot) / "public-progress.json"
        prior = json.loads(pilot_path.read_text())
        if prior["status"] != "stopped_infrastructure" or prior["model"] != cfg.model:
            raise ValueError("invalid transport pilot")
        pilot = {"public_sha256": hashlib.sha256(pilot_path.read_bytes()).hexdigest(),
                 "status": prior["status"], "settled": prior["settled_episodes"],
                 "calls": prior["ledger"]["started_attempts"],
                 "infrastructure_failures": sum(bool(e["infrastructure_failure"]) for e in prior["episodes"]),
                 "policy": "preserved separately; never merged with or repaired by this new streaming campaign"}
    root = Path(root)
    root.mkdir(mode=0o700, parents=True, exist_ok=False)
    manifest = copy.deepcopy(reference)
    manifest.update(created_at=utc(), model=cfg.model, decoding=decoding,
                    source_commit=commit, source_sha256=source_digest(),
                    comparison={"reference_model": reference["model"],
                                "reference_manifest_sha256": reference["manifest_sha256"],
                                "reference_source_commit": reference["source_commit"],
                                "reference_public_sha256": hashlib.sha256((reference_root / "public-progress.json").read_bytes()).hexdigest(),
                                "changed_source_files": changed,
                                "paired_on": "world, panels, episode observation-index noise, claim confirmation keys, limits, order",
                                "decoding_difference": "GPT medium/max_completion_tokens vs DeepSeek high/max_tokens; both 8000 cap, native effort not equivalent",
                                "transport": {"reference_stream": reference["decoding"]["stream"], "candidate_stream": cfg.stream},
                                "empty_output_policy": "empty visible replies consume one invalid-action turn, matching nonstream chat; no reasoning fallback or retry",
                                "interpretation": "paired end-to-end comparison; three independent instances per environment, not six; service/model/workflow effects are not causally separated"})
    if budget_change:
        manifest["limits"]["wall_seconds"] = EXTENDED_BUDGET["wall_seconds"]
        manifest["comparison"].update(budget_change=budget_change, previous_stopped_campaign=previous,
                                     paired_on="world, panels, episode observation-index noise, claim confirmation keys, scientific action budgets, order",
                                     decoding_difference="GPT medium/max_completion_tokens/8000 vs DeepSeek high/max_tokens/16000; native effort and output/time budgets differ",
                                     interpretation=budget_change["interpretation"])
    if pilot is not None:
        manifest["comparison"]["transport_pilot"] = pilot
    if client_pilot is not None:
        prior_path = Path(client_pilot) / "public-progress.json"
        prior = json.loads(prior_path.read_text())
        if prior["status"] != "stopped_infrastructure" or prior["model"] != cfg.model:
            raise ValueError("invalid client classification pilot")
        manifest["comparison"]["client_pilot"] = {
            "public_sha256": hashlib.sha256(prior_path.read_bytes()).hexdigest(),
            "settled": prior["settled_episodes"], "calls": prior["ledger"]["started_attempts"],
            "policy": "preserved separately; old streaming client misclassified reasoning-only completed responses as transport errors"}
    manifest.pop("manifest_sha256")
    manifest["manifest_sha256"] = canonical_hash(manifest)
    write(root / "manifest-private.json", manifest, new=True)
    (root / "episodes").mkdir(mode=0o700)
    CampaignLedger(root / "attempts.sqlite", limit=manifest["planned_max_api_attempts"])
    export(root)
    return {"episodes": len(manifest["instances"]), "model": cfg.model,
            "manifest_sha256": manifest["manifest_sha256"]}


def export(root):
    root = Path(root)
    manifest = load_manifest(root)
    ledger = CampaignLedger(root/"attempts.sqlite").summary()
    rows, groups = [], {}
    for item in manifest["instances"]:
        directory = root/"episodes"/item["episode_id"]
        report_path = directory/"report.json"
        report = json.loads(report_path.read_text()) if report_path.exists() else {}
        settled = (directory/"closed.json").is_file()
        status = report.get("status", "running" if directory.exists() else "pending")
        score = float(report.get("score") or 0.) if settled else None
        parts = (report.get("subscores") or {}) if settled else {}
        row = dict(episode_id=item["episode_id"], environment=item["environment"],
                   instance_index=item["instance_index"], repeat_index=item["repeat_index"],
                   status=status, settled=settled, completed=bool(settled and report.get("model_completed")),
                   infrastructure_failure=report.get("infrastructure_failure"), score=score,
                   condition_score=float(parts.get("conditions", 0)) if settled else None,
                   intervention_score=float(parts.get("interventions", 0)) if settled else None,
                   claim_score=float(parts.get("claims", 0)) if settled else None,
                   requests=ledger["attempts_by_episode"].get(item["episode_id"], 0),
                   observations=report.get("experiment_count", 0), stop_reason=report.get("stop_reason"),
                   provider_reported_models=report.get("provider_reported_models", []),
                   verified_nonzero_effects=report.get("verified_nonzero_effects", 0),
                   score_protocol=report.get("scoring_protocol", report.get("score_protocol")),
                   report_sha256=hashlib.sha256(report_path.read_bytes()).hexdigest() if settled else None)
        rows.append(row)
    for name in ENVIRONMENTS:
        all_rows = [r for r in rows if r["environment"] == name]
        closed = [r for r in all_rows if r["settled"]]
        healthy = [r for r in closed if not r["infrastructure_failure"]]
        full = len(closed) == 6
        groups[name] = dict(planned=6, started=sum(r["status"] != "pending" for r in all_rows),
                            settled=len(closed), completed=sum(r["completed"] for r in closed),
                            failed=sum(not r["completed"] for r in closed),
                            infrastructure_failures=sum(bool(r["infrastructure_failure"]) for r in closed),
                            scored_runs=len(closed), discoveries=[],
                            model_only_score_mean=mean(r["score"] for r in healthy) if full and healthy else None,
                            **{k:mean(r[k] for r in closed) if full else None
                               for k in ("condition_score", "intervention_score", "claim_score")})
        groups[name]["score_mean"] = mean(r["score"] for r in closed) if full else None
    closed_count = sum(r["settled"] for r in rows)
    state = json.loads((root/"state.json").read_text()) if (root/"state.json").exists() else {}
    result = dict(schema="sle-unified-public-1", protocol=manifest["protocol"], model=manifest["model"],
                  source_commit=manifest["source_commit"], source_sha256=manifest["source_sha256"],
                  manifest_sha256=manifest["manifest_sha256"], updated_at=utc(),
                  status="completed" if closed_count==72 else state.get("status", "frozen"),
                  planned_episodes=72, settled_episodes=closed_count, call_cap_per_episode=16,
                  ledger={k:ledger[k] for k in ("attempt_limit","started_attempts","remaining_attempts","status_counts")},
                  by_environment=groups, episodes=rows, score_policy=manifest["score_contract"],
                  total_score=mean(v["score_mean"] for v in groups.values()) if closed_count==72 else None,
                  denominator_policy=manifest["aggregation"], limits=manifest["limits"],
                  repeated_instance_policy=manifest["repeated_instance_policy"], scope=manifest["scope"])
    if "comparison" in manifest:
        result["comparison"] = manifest["comparison"]
        result["decoding"] = manifest["decoding"]
    write(root/"public-progress.json", result)
    return result


def run(root, config):
    from sle.llm import LLMConfig
    from .unified_scoring import score_contract
    root = Path(root).resolve()
    manifest = load_manifest(root)
    if manifest["source_sha256"] != source_digest():
        raise ValueError("source changed after freeze")
    if manifest["score_contract"] != score_contract():
        raise ValueError("score changed after freeze")
    raw = json.loads(Path(config).read_text())
    cfg = LLMConfig.from_dict(raw.get("llm", raw))
    if cfg.model != manifest["model"] or {k:getattr(cfg,k) for k in manifest["decoding"]} != manifest["decoding"]:
        raise ValueError("model/decoding differs from frozen protocol")
    if CampaignLedger(root/"attempts.sqlite").summary()["started_attempts"] != 0 or any((root/"episodes").iterdir()):
        raise ValueError("no implicit replacement/resume")
    write(root/"started.json", {"started_at":utc(), "manifest_sha256":manifest["manifest_sha256"]}, new=True)
    write(root/"state.json", {"status":"running", "started_at":utc()})
    context = multiprocessing.get_context("spawn")
    for batch in (manifest["instances"][:12], manifest["instances"][12:]):
        with concurrent.futures.ProcessPoolExecutor(max_workers=manifest["workers"], mp_context=context) as pool:
            pending = {pool.submit(_run_one, item, manifest["limits"], str(root/"episodes"/item["episode_id"]),
                                   str(Path(config).resolve()), str(root/"attempts.sqlite"), manifest["workers"],
                                   manifest["rpm"], manifest["source_sha256"], manifest["decoding"]):item for item in batch}
            while pending:
                finished, _ = concurrent.futures.wait(pending, timeout=30, return_when=concurrent.futures.FIRST_COMPLETED)
                for future in finished:
                    item = pending.pop(future)
                    directory = root/"episodes"/item["episode_id"]
                    directory.mkdir(exist_ok=True)
                    try:
                        outcome = future.result()
                    except Exception as exc:
                        # Exception messages can contain credentials or paths; retain only class publicly.
                        outcome = dict(episode_id=item["episode_id"], environment=item["environment"],
                                       status="failed", score=None, model_completed=False,
                                       infrastructure_failure="worker_or_dispatch_failure", stop_reason=type(exc).__name__)
                        write(directory/"report.json", outcome)
                    write(directory/"closed.json", dict(closed_at=utc(), outcome=outcome), new=True)
                    print(json.dumps(outcome, ensure_ascii=False), flush=True)
                export(root)
        snapshot = export(root)
        if len(batch)==12 and sum(r["infrastructure_failure"] is not None for r in snapshot["episodes"] if r["settled"])>=3:
            write(root/"state.json", {"status":"stopped_infrastructure", "reason":"at least three infrastructure failures in the first twelve fixed episodes", "updated_at":utc()})
            export(root)
            return
    write(root/"state.json", {"status":"completed", "completed_at":utc()})
    snapshot = export(root)
    print(json.dumps({"status":snapshot["status"],"total_score":snapshot["total_score"],"ledger":snapshot["ledger"]}),flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("freeze", "freeze-paired", "run", "export"))
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--exclusions", type=Path)
    parser.add_argument("--commit")
    parser.add_argument("--config", type=Path)
    parser.add_argument("--reference-root", type=Path)
    parser.add_argument("--reference-source", type=Path)
    parser.add_argument("--transport-pilot", type=Path)
    parser.add_argument("--client-pilot", type=Path)
    parser.add_argument("--budget-profile", choices=("reference", "extended-output-v1"), default="reference")
    parser.add_argument("--prior-campaign", type=Path)
    parser.add_argument("--readiness-probe", type=Path)
    args = parser.parse_args()
    if args.action == "freeze":
        if not args.exclusions or not args.commit:
            parser.error("freeze requires --exclusions and --commit")
        print(json.dumps(freeze(args.root,args.exclusions,args.commit)))
    elif args.action == "freeze-paired":
        if not all((args.reference_root, args.reference_source, args.config, args.commit)):
            parser.error("freeze-paired requires --reference-root, --reference-source, --config and --commit")
        print(json.dumps(freeze_paired(args.root, args.reference_root, args.reference_source, args.config, args.commit, args.transport_pilot, args.client_pilot,
                                      budget_profile=args.budget_profile, prior_campaign=args.prior_campaign, readiness_probe=args.readiness_probe)))
    elif args.action == "run":
        if not args.config:
            parser.error("run requires --config")
        run(args.root,args.config)
    else:
        data = export(args.root)
        print(json.dumps({"status":data["status"],"settled":data["settled_episodes"],"ledger":data["ledger"]}))


if __name__ == "__main__":
    main()
