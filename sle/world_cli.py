"""Run a first virtual world without model credentials or paid API calls."""
from __future__ import annotations

import argparse
import json
from pathlib import Path



def _save(directory, name, value):
    path = directory / name
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    path.chmod(0o600)


def command(args):
    from .world_session import WorldSession, replay_report
    if args.world_command == "describe":
        print(json.dumps(WorldSession().describe(), ensure_ascii=False, indent=2))
        return 0
    if args.world_command == "replay":
        print(json.dumps(replay_report(json.loads(Path(args.report).read_text())), indent=2))
        return 0
    from .scientific_episode import prepare_output, parse_json
    if Path(args.output_dir).exists():
        raise ValueError("world output directory already exists; choose a new directory")
    directory = prepare_output(args.output_dir)
    session = WorldSession(args.seed, budget=args.budget)
    demo = None
    try:
        if args.world_command == "demo":
            from .microecology_demo import run_demo, render_demo
            demo = run_demo(session)
            _save(directory, "demo.json", demo)
            render_demo(demo, directory)
        elif args.interactive:
            import sys
            print(json.dumps(session.describe(), ensure_ascii=False), flush=True)
            for line in sys.stdin:
                try:
                    request = parse_json(line)
                    response = session.step(request)
                except (ValueError, TypeError):
                    response = {"ok": False, "error": "invalid_json"}
                print(json.dumps(response, ensure_ascii=False), flush=True)
                if session.state in ("completed", "infrastructure_error", "budget_exhausted"):
                    break
        elif args.program:
            # The existing fail-closed Linux sandbox is the sole path for candidate code.
            from .secure_eval import CandidateProxy
            worker = CandidateProxy(Path(args.program).resolve(), "solve", timeout_s=args.timeout)
            try:
                worker(session.describe(), lambda request: session.step(request))
            finally:
                worker.close()
        else:
            actions = parse_json(Path(args.actions).read_text(encoding="utf-8"))
            if not isinstance(actions, list) or len(actions) > 1000:
                raise ValueError("actions must be an array of at most 1000 requests")
            for action in actions:
                response = session.step(action)
                if not response.get("ok"):
                    raise ValueError("action failed: " + response["error"])
    finally:
        _save(directory, "public-report.json", session.report())
        _save(directory, "operator-report.json", session.report(private=True))
    summary = {"world": "Microecology", "state": session.state, "output_dir": str(directory),
               "resources": session.report()["resources"], "model_api_calls": 0}
    if demo:
        summary["selected_channel"] = demo["selected_channel"]
        summary["results"] = [{k: r[k] for k in ("claim_id", "status", "mean_difference")} for r in demo["verification"]["results"]]
    summary["kind"] = "session_summary"
    print(json.dumps(summary, ensure_ascii=False, indent=None if getattr(args, "interactive", False) else 2))
    return 1 if session.state in ("infrastructure_error", "budget_exhausted") else 0


def add_parser(sub):
    root = sub.add_parser("world", help="run the Microecology virtual-world prototype")
    commands = root.add_subparsers(dest="world_command", required=True)
    commands.add_parser("describe", help="show public tools and claim protocol").set_defaults(fn=command)
    replay = commands.add_parser("replay", help="replay a private operator report")
    replay.add_argument("report")
    replay.set_defaults(fn=command)
    for name in ("demo", "run"):
        parser = commands.add_parser(name)
        parser.set_defaults(fn=command)
        parser.add_argument("--seed", type=int, default=7, help="operator-only world seed")
        parser.add_argument("--budget", type=int, default=1200)
        parser.add_argument("--output-dir", required=True, help="new private output directory outside Git checkouts")
        if name == "run":
            source = parser.add_mutually_exclusive_group(required=True)
            source.add_argument("--interactive", action="store_true", help="JSONL stdin/stdout")
            source.add_argument("--actions", help="JSON array of public actions")
            source.add_argument("--program", help="solve(description, act); Linux sandbox required")
            parser.add_argument("--timeout", type=float, default=300)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m sle.world_cli")
    sub = parser.add_subparsers(dest="command", required=True)
    add_parser(sub)
    args = parser.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
