#!/usr/bin/env bash
# Run a seed-paired cohort of tasks, resumably and safely under concurrency.
#
# Why this is a repository script rather than a scratch file. The Claude cohort was launched from
# two ad-hoc /tmp drivers that each held their own whole-script lock. Locks named after the script
# do not exclude a *different* script, both driver lists contained LowThrustTransfer, and each
# began its work with `rm -rf` on the run directory. Two runs therefore deleted each other's
# output: three of thirty-six runs ended up without a run_manifest.json, and since every report in
# this repository keys off that manifest, those runs were silently absent from the comparison
# rather than reported as failures.
#
# Two things here prevent a repeat:
#
#   the lock is per run directory, so two drivers that happen to share a task serialise on the
#   run they collide over instead of on their own names, and
#
#   a run counts as finished when its manifest exists - the same file the readers require. The old
#   guard accepted "trajectory.jsonl has at least 13 lines", which is true of a run whose manifest
#   was destroyed, so a resume skipped exactly the runs that needed redoing.
#
# The paired structure matters for the same reason it does in the evolvability gap: `normal` and
# `selection_blind` must run at the same seed and the same budget, so they are launched together
# and waited on together.
#
# Usage:
#   scripts/run_cohort.sh --cohort claude --config conf/llm/local.claude.yaml \
#       --seeds 0,1,2 --budget 12 Spectroscopy/NMRSpectrumFitting:nmr Astro/X:x
#
#   --only-missing   restrict to runs that have no manifest (repairs a partial cohort)
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COHORT=""; CONFIG=""; SEEDS="0,1,2"; BUDGET=12; ALGORITHM="greedy_rewrite"; ONLY_MISSING=0
MODES=("selection_blind" "normal")

while [[ $# -gt 0 ]]; do
  case "$1" in
    --cohort) COHORT="$2"; shift 2 ;;
    --config) CONFIG="$2"; shift 2 ;;
    --seeds) SEEDS="$2"; shift 2 ;;
    --budget) BUDGET="$2"; shift 2 ;;
    --algorithm) ALGORITHM="$2"; shift 2 ;;
    --only-missing) ONLY_MISSING=1; shift ;;
    --) shift; break ;;
    -*) echo "unknown flag: $1" >&2; exit 2 ;;
    *) break ;;
  esac
done

[[ -n "$COHORT" && -n "$CONFIG" && $# -gt 0 ]] || {
  echo "usage: $0 --cohort NAME --config PATH [--seeds 0,1,2] [--budget N] [--only-missing] TASK:SHORT..." >&2
  exit 2
}

# The key is never read from a file or a flag, only from the environment, and it is never echoed.
if [[ -z "${ANTHROPIC_API_KEY:-}" && "$CONFIG" == *claude* ]]; then
  echo "ANTHROPIC_API_KEY is not set; export it before running (it is a shared key: never commit it)" >&2
  exit 2
fi

mkdir -p "$ROOT/runs/$COHORT" "$ROOT/logs"
IFS=',' read -r -a SEED_LIST <<< "$SEEDS"
failures=0

run_one () {
  local task="$1" short="$2" mode="$3" seed="$4"
  local dir="$ROOT/runs/$COHORT/${short}_${mode}_s${seed}"
  local lock="$dir.lock"

  # Finished means the manifest is there, because that is what the reports require.
  if [[ -f "$dir/run_manifest.json" ]]; then
    echo "skip  $short $mode s$seed (already complete)"
    return 0
  fi
  # mkdir is the atomic primitive here; -p would succeed on an existing directory and defeat it.
  if ! mkdir "$lock" 2>/dev/null; then
    echo "busy  $short $mode s$seed (another driver holds it)"
    return 0
  fi
  trap 'rmdir "$lock" 2>/dev/null' RETURN

  # Safe now: the lock is held, so no concurrent driver is writing into this directory.
  rm -rf "$dir"
  local log="$ROOT/logs/${COHORT}_${short}_${mode}_s${seed}.log"
  if python3 -m frontier_science run --task "$task" --algorithm "$ALGORITHM" \
      --feedback-mode "$mode" --budget "$BUDGET" --seed "$seed" --allow-uncertified \
      --llm-config "$CONFIG" --workdir "$dir" > "$log" 2>&1 \
      && [[ -f "$dir/run_manifest.json" ]]; then
    echo "done  $short $mode s$seed"
  else
    # Report it rather than letting a missing manifest look like a run that was never requested.
    echo "FAIL  $short $mode s$seed -- see $log"
    tail -3 "$log" | sed 's/^/        /'
    return 1
  fi
}

for spec in "$@"; do
  task="${spec%%:*}"; short="${spec##*:}"
  [[ "$task" == "$short" ]] && short="${task##*/}"
  (
    for seed in "${SEED_LIST[@]}"; do
      pids=()
      for mode in "${MODES[@]}"; do
        if [[ "$ONLY_MISSING" == 1 \
              && -f "$ROOT/runs/$COHORT/${short}_${mode}_s${seed}/run_manifest.json" ]]; then
          continue
        fi
        run_one "$task" "$short" "$mode" "$seed" &
        pids+=($!)
      done
      # Budget-matched pairing: the two arms of a seed finish together before the next seed starts.
      for pid in ${pids[@]+"${pids[@]}"}; do wait "$pid" || true; done
    done
    echo "==    $short finished"
  ) &
done
wait

echo "########## $COHORT done ##########"
# A cohort that silently lost runs is the failure this script exists to prevent, so count them.
for spec in "$@"; do
  task="${spec%%:*}"; short="${spec##*:}"
  [[ "$task" == "$short" ]] && short="${task##*/}"
  for seed in "${SEED_LIST[@]}"; do
    for mode in "${MODES[@]}"; do
      [[ -f "$ROOT/runs/$COHORT/${short}_${mode}_s${seed}/run_manifest.json" ]] \
        || { echo "MISSING $short $mode s$seed"; failures=$((failures + 1)); }
    done
  done
done
[[ "$failures" == 0 ]] && echo "all runs have a manifest" || echo "$failures run(s) missing a manifest"
exit 0
