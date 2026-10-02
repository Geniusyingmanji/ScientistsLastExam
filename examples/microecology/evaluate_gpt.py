"""Trusted operator launcher: one fresh three-instance GPT-5.6 evaluation campaign.

Run from the repository root with PYTHONPATH=. No model credentials are logged.
All started requests, including failures, count toward the 3 * 16 request cap.
An existing campaign directory cannot be resumed or silently run again.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path

import yaml

from sle.llm import LLMConfig
from sle.scientific_episode import prepare_output
from sle.world_agent import AuditedWorldClient, WorldAnalysis, run_agent, save_json
from sle.world_session import WorldSession, replay_report, source_binding


SEEDS = (1439, 2879, 4093)


def summarize(agent, public):
    results = (public.get("verification") or {}).get("results", [])
    forecasts = [r["forecast_evaluation"] for r in results if "forecast_evaluation" in r]
    n = len(forecasts)
    return {"state": public["state"], "stop_reason": agent["stop_reason"],
            "requested_model": agent["requested_model"], "reported_models": agent["provider_reported_models"],
            "api_attempts": agent["transport"]["attempts"], "failed_attempts": agent["transport"]["failed_attempts"],
            "elapsed_seconds": agent["elapsed_seconds"], "resources": public["resources"],
            "claim_count": len(results), "supported": sum(r["status"] == "prediction_supported" for r in results),
            "refuted": sum(r["status"] == "prediction_refuted" for r in results),
            "inconclusive": sum(r["status"] == "inconclusive" for r in results),
            "forecast_count": n, "forecast_covered": sum(f["covered"] for f in forecasts),
            "mean_forecast_width": sum(f["width"] for f in forecasts) / n if n else None,
            "mean_interval_score": sum(f["interval_score"] for f in forecasts) / n if n else None,
            "forecast_comparison_scope": "descriptive on agent-selected claims, not a common-task skill score",
            "results": results, "usage": agent["usage"],
            "known_response_usage_lower_bound": agent["known_response_usage_lower_bound"],
            "discovery_depth": None, "mechanism_certification": "unassessed"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--llm-config", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    if Path(args.output_dir).exists():
        raise ValueError("campaign directory already exists; no restart or quota reset allowed")
    root = prepare_output(args.output_dir)
    config = LLMConfig.from_dict(yaml.safe_load(Path(args.llm_config).read_text()) or {})
    if config.model != "gpt-5.6-sol":
        raise ValueError("this campaign is specifically for configured gpt-5.6-sol")
    if not 1 <= config.max_output_tokens <= 8000 or not 1 <= config.timeout_seconds <= 180:
        raise ValueError("configured request limits exceed this pilot's bounds")
    manifest = {"protocol": "microecology-gpt56-paired-effects-v2-pilot", "seeds": list(SEEDS),
                "instances": 3, "max_requests_per_instance": 16, "max_requests_total": 48,
                "exploration_rounds": 10, "experiment_units_per_instance": 800,
                "confirmation_units_per_instance": 4000, "wall_seconds_per_instance": 900,
                "automatic_retries": 0, "model": config.model,
                "reasoning_effort": config.reasoning_effort, "max_output_tokens": config.max_output_tokens,
                "wire": config.wire, "stream": config.stream, "timeout_seconds": config.timeout_seconds,
                "source_binding": source_binding(),
                "launcher_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                "world_scope": "same fixed mechanism family; independent parameter and anonymous-channel instances",
                "depth_status": "unassessed; no discovery score inferred from interval checks"}
    save_json(root / "campaign-manifest.json", manifest)
    entries = []
    for index, seed in enumerate(SEEDS, 1):
        directory = root / ("episode-%02d" % index)
        directory.mkdir(mode=0o700)
        save_json(root / "campaign-progress.json", {"started_episode": index, "episodes": entries})
        session = WorldSession(seed, budget=800, confirmation_budget=4000)
        analysis = None
        print(json.dumps({"episode": index, "event": "started"}), flush=True)
        try:
            analysis = WorldAnalysis(timeout_s=20)
            client = AuditedWorldClient(config, directory, max_attempts=16)
            agent = run_agent(session, client, directory, max_rounds=16, wall_seconds=900,
                              analysis=analysis, exploration_rounds=10, evaluation_profile="paired-effects-v2")
            public = session.report()
            result = {"episode": index, **summarize(agent, public)}
            replay = replay_report(session.report(private=True))
            save_json(directory / "replay-result.json", replay)
            result["replay"] = replay
        except Exception as exc:
            # No provider exception body or config enters the campaign report.
            result = {"episode": index, "state": "operator_error", "exception_type": type(exc).__name__}
        finally:
            if analysis is not None:
                analysis.close()
        entries.append(result)
        save_json(root / "campaign-progress.json", {"started_episode": index, "episodes": entries})
        print(json.dumps({"episode": index, "event": "finished", "state": result["state"],
                          "stop_reason": result.get("stop_reason"), "supported": result.get("supported"),
                          "claims": result.get("claim_count"), "attempts": result.get("api_attempts")}), flush=True)
    # Audit the durable started records, including a crash after an HTTP request.
    attempts = 0
    for directory in root.glob("episode-*"):
        ledger = directory / "model-transport.jsonl"
        if ledger.exists():
            attempts += sum(json.loads(line)["event"] == "started" for line in ledger.read_text().splitlines())
    assert attempts <= 48
    complete = sum(e["state"] == "completed" for e in entries)
    summary = {"protocol": manifest["protocol"], "instances_planned": 3, "instances_recorded": len(entries),
               "completed": complete, "started_model_requests": attempts, "max_model_requests": 48,
               "episodes": entries, "scientific_scope": manifest["world_scope"],
               "discovery_depth": None, "calibration": "three development instances, not a calibrated benchmark"}
    save_json(root / "campaign-report.json", summary)
    print(json.dumps({"campaign": "finished", "completed": complete, "instances": 3,
                      "requests": attempts, "output_dir": str(root)}), flush=True)
    return 0 if complete == 3 else 1


if __name__ == "__main__":
    raise SystemExit(main())
