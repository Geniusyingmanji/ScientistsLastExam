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
#   a run counts as finished only when both its manifest and terminal summary exist. The manifest
#   is written before baseline evaluation, so it proves attribution but not completion.
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
#   --modes          comma-separated feedback modes; default is both arms. Open-loop
#                    saturation scans pass selection_blind only so a climbing control
#                    does not also buy an unpaired feedback arm.
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
    --modes) IFS=',' read -r -a MODES <<< "$2"; shift 2 ;;
    --only-missing) ONLY_MISSING=1; shift ;;
    --) shift; break ;;
    -*) echo "unknown flag: $1" >&2; exit 2 ;;
    *) break ;;
  esac
done

[[ -n "$COHORT" && -n "$CONFIG" && $# -gt 0 && ${#MODES[@]} -gt 0 ]] || {
  echo "usage: $0 --cohort NAME --config PATH [--seeds 0,1,2] [--budget N] [--modes selection_blind,normal] [--only-missing] TASK:SHORT..." >&2
  exit 2
}

# The key is never read from a file or a flag, only from the environment, and it is never echoed.
if [[ -z "${ANTHROPIC_API_KEY:-}" && "$CONFIG" == *claude* ]]; then
  echo "ANTHROPIC_API_KEY is not set; export it before running (it is a shared key: never commit it)" >&2
  exit 2
fi

# Locks live outside the cohort tree. Put beside the run directories they guard, they are picked
# up by the `runs/*/*` globs every report in this repository uses, and the first repair run had a
# lock directory reported as a run missing its manifest.
LOCK_ROOT="$ROOT/.locks/$COHORT"
mkdir -p "$ROOT/runs/$COHORT" "$ROOT/logs" "$LOCK_ROOT"
IFS=',' read -r -a SEED_LIST <<< "$SEEDS"
failures=0

request_digest () {
  local task="$1" mode="$2" seed="$3"
  local config_digest
  if [[ -f "$CONFIG" ]]; then
    config_digest="$(sha256sum "$CONFIG" | awk '{print $1}')"
  else
    config_digest="missing:$CONFIG"
  fi
  printf '%s\n' "$task" "$mode" "$seed" "$ALGORITHM" "$BUDGET" "$config_digest" \
    | sha256sum | awk '{print $1}'
}

run_is_complete () {
  local dir="$1" task="$2" mode="$3" seed="$4"
  [[ -f "$dir/run_manifest.json" && -f "$dir/summary.json" \
     && -f "$dir/.cohort_request_sha256" ]] || return 1
  [[ "$(<"$dir/.cohort_request_sha256")" == "$(request_digest "$task" "$mode" "$seed")" ]] \
    || return 1
  python - "$dir" "$task" "$mode" "$seed" "$ALGORITHM" "$BUDGET" "$ROOT" "$CONFIG" <<'PY'
import json
import sys
from pathlib import Path

directory, task, mode, seed, algorithm, budget, root, config = sys.argv[1:]
try:
    manifest = json.loads((Path(directory) / "run_manifest.json").read_text())
    summary = json.loads((Path(directory) / "summary.json").read_text())
except (OSError, json.JSONDecodeError):
    raise SystemExit(1)
expected_manifest = {
    "task_id": task,
    "feedback_mode": mode,
    "seed": int(seed),
    "algorithm": algorithm,
}
expected_summary = {**expected_manifest, "budget": int(budget)}
if any(manifest.get(key) != value for key, value in expected_manifest.items()):
    raise SystemExit(1)
if any(summary.get(key) != value for key, value in expected_summary.items()):
    raise SystemExit(1)

# A completed cell is evidence about one frozen task, runtime, and model condition. The
# lightweight script tests copy this file without the package, so the identity check is enabled
# whenever this is a real checkout and otherwise the artifact/request checks above still run.
root_path = Path(root)
if (root_path / "sle").is_dir():
    sys.path.insert(0, str(root_path))
    from sle.algorithms.common import (
        llm_condition_sha256,
        runtime_source_sha256,
        task_contract_sha256,
        task_package_sha256,
    )
    from sle.config import load_llm_client
    from sle.registry import find_task

    spec = find_task(task, include_uncertified=True)
    expected_bindings = {
        "llm_condition_sha256": llm_condition_sha256(load_llm_client(config)),
        "task_contract_sha256": task_contract_sha256(spec),
        "task_package_sha256": task_package_sha256(spec),
        "runtime_source_sha256": runtime_source_sha256(),
    }
    if any(manifest.get(key) != value for key, value in expected_bindings.items()):
        raise SystemExit(1)
PY
}

run_one () {
  local task="$1" short="$2" mode="$3" seed="$4"
  local name="${short}_${mode}_s${seed}"
  local dir="$ROOT/runs/$COHORT/$name"
  local lock="$LOCK_ROOT/$name.lock"

  if run_is_complete "$dir" "$task" "$mode" "$seed"; then
    echo "skip  $short $mode s$seed (already complete)"
    return 0
  fi
  if [[ -f "$dir/run_manifest.json" && -f "$dir/summary.json" ]]; then
    echo "CONFLICT $short $mode s$seed (terminal artifacts do not match requested cell)"
    return 1
  fi
  # `flock` locks the open inode atomically and the kernel releases it if the driver dies. This
  # has no empty-pid acquisition window and no stale-lock takeover race. Keep the lock file: an
  # unlink/recreate cycle would let two processes lock different inodes for the same run.
  (
    if ! flock -n 9; then
      echo "busy  $short $mode s$seed"
      exit 0
    fi
    # Another driver may have completed the cell between the optimistic check above and this
    # lock acquisition. Re-check under the lock before touching the run directory.
    if run_is_complete "$dir" "$task" "$mode" "$seed"; then
      echo "skip  $short $mode s$seed (already complete)"
      exit 0
    fi
    if [[ -f "$dir/run_manifest.json" && -f "$dir/summary.json" ]]; then
      echo "CONFLICT $short $mode s$seed (terminal artifacts do not match requested cell)"
      exit 1
    fi

    # Safe now: the kernel lock is held, so no concurrent driver is writing into this directory.
    rm -rf "$dir"
    local log="$ROOT/logs/${COHORT}_${short}_${mode}_s${seed}.log"
    if python3 -m sle run --task "$task" --algorithm "$ALGORITHM" \
        --feedback-mode "$mode" --budget "$BUDGET" --seed "$seed" --allow-uncertified \
        --llm-config "$CONFIG" --workdir "$dir" > "$log" 2>&1 \
        && [[ -f "$dir/run_manifest.json" && -f "$dir/summary.json" ]]; then
      request_digest "$task" "$mode" "$seed" > "$dir/.cohort_request_sha256"
      echo "done  $short $mode s$seed"
    else
      # Report it rather than letting a missing manifest look like a run that was never requested.
      echo "FAIL  $short $mode s$seed -- see $log"
      tail -3 "$log" | sed 's/^/        /'
      exit 1
    fi
  ) 9>"$lock"
}

for spec in "$@"; do
  task="${spec%%:*}"; short="${spec##*:}"
  [[ "$task" == "$short" ]] && short="${task##*/}"
  (
    for seed in "${SEED_LIST[@]}"; do
      pids=()
      for mode in "${MODES[@]}"; do
        if [[ "$ONLY_MISSING" == 1 ]] && run_is_complete \
              "$ROOT/runs/$COHORT/${short}_${mode}_s${seed}" \
              "$task" "$mode" "$seed"; then
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
      name="${short}_${mode}_s${seed}"
      dir="$ROOT/runs/$COHORT/$name"
      lock="$LOCK_ROOT/$name.lock"
      # A concurrent driver may have reported this cell as busy and returned from run_one.
      # Check terminal evidence only after that driver releases the same per-cell lock.
      ( flock 9 && run_is_complete "$dir" "$task" "$mode" "$seed" ) 9>"$lock" \
        || { echo "INCOMPLETE $short $mode s$seed"; failures=$((failures + 1)); }
    done
  done
done
if [[ "$failures" == 0 ]]; then
  echo "all runs have terminal artifacts"
  exit 0
fi
echo "$failures run(s) incomplete"
exit 1
