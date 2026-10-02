"""python -m env: frozen scientific pilot cohorts and reports."""
import argparse
import json
from pathlib import Path

from .microecology.agent import save_json
from .task_profiles import TASK_PROFILE_NAMES


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    freeze = commands.add_parser("freeze")
    freeze.add_argument("--cohort", required=True)
    freeze.add_argument("--environments", required=True, help="comma-separated environment names")
    freeze.add_argument("--instances", type=int, default=5)
    freeze.add_argument("--rounds", type=int, default=16)
    freeze.add_argument("--exploration-rounds", type=int, default=14)
    freeze.add_argument("--task-profile", default="open_discovery", choices=TASK_PROFILE_NAMES)
    freeze.add_argument("--presentation-profile", default="full_description", choices=("full_description", "apparatus_only"))
    freeze.add_argument("--balanced-strata", default="", help="comma-separated selected environments with trusted operator strata")
    freeze.add_argument("--analysis-protocol", default="legacy", choices=("legacy", "sle-analysis-snapshots-0.1"),
                        help="explicit candidate model-snapshot API version; legacy keeps the original interface")
    freeze.add_argument("--seed-exclusions-file", help="explicit operator-only JSON world-seed exclusion list")
    freeze.add_argument("--output", required=True)
    run = commands.add_parser("run")
    run.add_argument("--manifest", required=True)
    run.add_argument("--config", required=True)
    run.add_argument("--campaign-root", required=True)
    run.add_argument("--workers", type=int, default=8)
    run.add_argument("--rpm", type=int, default=60)
    report = commands.add_parser("report")
    report.add_argument("cohort_directory")
    args = parser.parse_args()
    if args.command == "freeze":
        from .campaign import create_manifest
        from .seed_exclusions import load_exclusions, public_summary
        exclusions = load_exclusions(args.seed_exclusions_file) if args.seed_exclusions_file else None
        output = Path(args.output)
        if output.exists():
            raise ValueError("manifest already exists; do not overwrite a frozen cohort")
        manifest = create_manifest(args.cohort, args.environments.split(","), args.instances, args.rounds, args.exploration_rounds, args.task_profile, args.presentation_profile, args.balanced_strata.split(",") if args.balanced_strata else (), args.analysis_protocol, seed_exclusions=exclusions)
        output.parent.mkdir(parents=True, exist_ok=True)
        save_json(output, manifest)
        summary = {"cohort": manifest["cohort"], "episodes": len(manifest["instances"]),
                   "source_sha256": manifest["source_sha256"], "max_api_attempts": manifest["planned_max_api_attempts"]}
        if exclusions is not None:
            summary["seed_exclusions"] = public_summary(exclusions)
        print(json.dumps(summary))
    elif args.command == "run":
        from .campaign import run_cohort
        run_cohort(args.manifest, args.config, args.campaign_root, workers=args.workers, rpm=args.rpm)
    else:
        from .reporting import render_report
        render_report(Path(args.cohort_directory))


if __name__ == "__main__":
    main()
