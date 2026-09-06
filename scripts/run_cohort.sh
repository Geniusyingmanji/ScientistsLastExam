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

if [[ "$ALGORITHM" != "greedy_rewrite" ]]; then
  echo "cohort evidence is supported only for greedy_rewrite because other backends lack durable receipt verification" >&2
  exit 2
fi

valid_component () {
  [[ "$1" =~ ^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$ ]]
}

valid_component "$COHORT" || {
  echo "invalid cohort name: use a bounded canonical path component" >&2
  exit 2
}
for mode in "${MODES[@]}"; do
  case "$mode" in
    normal|none|shuffled|score_only|delayed_replay|selection_blind) ;;
    *) echo "invalid feedback mode: $mode" >&2; exit 2 ;;
  esac
done
IFS=',' read -r -a SEED_LIST <<< "$SEEDS"
[[ ${#SEED_LIST[@]} -gt 0 ]] || {
  echo "invalid seed: at least one canonical integer is required" >&2
  exit 2
}
for seed in "${SEED_LIST[@]}"; do
  [[ "$seed" =~ ^(0|[1-9][0-9]{0,9})$ ]] || {
    echo "invalid seed: use a bounded canonical non-negative integer" >&2
    exit 2
  }
done
for task_spec in "$@"; do
  task_id="${task_spec%%:*}"
  task_alias="${task_spec##*:}"
  [[ "$task_id" == "$task_alias" ]] && task_alias="${task_id##*/}"
  valid_component "$task_alias" || {
    echo "invalid task alias: use a bounded canonical path component" >&2
    exit 2
  }
done

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
failures=0

# Resolve every task-specific trusted evaluator before any run process can
# reach a model. Only its path-free descriptor crosses the shell boundary.
declare -A TRUSTED_RUNTIME_RECORDS
if [[ -f "$ROOT/sle/evaluate.py" ]]; then
  for task_spec in "$@"; do
    task_id="${task_spec%%:*}"
    if [[ -z "${TRUSTED_RUNTIME_RECORDS[$task_id]:-}" ]]; then
      TRUSTED_RUNTIME_RECORDS[$task_id]="$(python3 - "$ROOT" "$task_id" <<'PY'
import json
import sys
from pathlib import Path

root, task_id = sys.argv[1:]
sys.path.insert(0, root)
from sle.evaluate import resolve_trusted_runtime
from sle.registry import find_task

spec = find_task(task_id, include_uncertified=True)
runtime = resolve_trusted_runtime(spec.task_dir)
print(json.dumps(runtime.descriptor, allow_nan=False, sort_keys=True, separators=(",", ":")))
PY
)" || {
        echo "trusted evaluator runtime unavailable for $task_id" >&2
        exit 2
      }
    fi
  done
fi

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
  local dir="$1" task="$2" mode="$3" seed="$4" trusted_runtime="${5:-}"
  [[ -f "$dir/run_manifest.json" && -f "$dir/summary.json" \
     && -f "$dir/.cohort_request_sha256" ]] || return 1
  [[ "$(<"$dir/.cohort_request_sha256")" == "$(request_digest "$task" "$mode" "$seed")" ]] \
    || return 1
  python3 - "$dir" "$task" "$mode" "$seed" "$ALGORITHM" "$BUDGET" "$ROOT" "$CONFIG" "$trusted_runtime" <<'PY'
import json
import sys
from pathlib import Path

directory, task, mode, seed, algorithm, budget, root, config, runtime_json = sys.argv[1:]
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
    from sle.frontier import frontier_binding
    from sle.registry import find_task

    spec = find_task(task, include_uncertified=True)
    expected_bindings = {
        "llm_condition_sha256": llm_condition_sha256(load_llm_client(config)),
        "task_contract_sha256": task_contract_sha256(spec),
        "task_package_sha256": task_package_sha256(spec),
        "runtime_source_sha256": runtime_source_sha256(),
    }
    expected_bindings.update(frontier_binding(spec))
    if any(manifest.get(key) != value for key, value in expected_bindings.items()):
        raise SystemExit(1)
    if runtime_json:
        expected_runtime = json.loads(runtime_json)
        if manifest.get("trusted_evaluator_runtime") != expected_runtime:
            raise SystemExit(1)
    if (root_path / "sle/run_verification.py").is_file():
        from sle.run_verification import verify_run
        verified = verify_run(
            Path(directory),
            expected_budget=int(budget),
            expected_trusted_runtime_sha256=(
                expected_runtime["fingerprint_sha256"] if runtime_json else None
            ),
        )
        if runtime_json and verified.get(
            "trusted_evaluator_runtime_sha256"
        ) != expected_runtime["fingerprint_sha256"]:
            raise SystemExit(1)
PY
}

resolved_run_target () {
  python3 - "$ROOT/runs/$COHORT" "$1" <<'PY'
import sys
from pathlib import Path

cohort_root = Path(sys.argv[1]).resolve()
raw_target = Path(sys.argv[2])
target = raw_target.resolve()
if (
    raw_target.is_symlink()
    or raw_target.parent.resolve() != cohort_root
    or target.parent != cohort_root
):
    raise SystemExit(1)
print(target)
PY
}

run_one () {
  local task="$1" short="$2" mode="$3" seed="$4"
  local name="${short}_${mode}_s${seed}"
  local dir="$ROOT/runs/$COHORT/$name"
  local lock="$LOCK_ROOT/$name.lock"
  local trusted_runtime="${TRUSTED_RUNTIME_RECORDS[$task]:-}"

  if run_is_complete "$dir" "$task" "$mode" "$seed" "$trusted_runtime"; then
    echo "skip  $short $mode s$seed (already complete)"
    return 0
  fi
  if [[ -e "$dir/run_manifest.json" || -e "$dir/summary.json" \
        || -e "$dir/evaluation_ledger" ]]; then
    echo "CONFLICT $short $mode s$seed (bound run artifacts do not verify)"
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
    if run_is_complete "$dir" "$task" "$mode" "$seed" "$trusted_runtime"; then
      echo "skip  $short $mode s$seed (already complete)"
      exit 0
    fi
    if [[ -e "$dir/run_manifest.json" || -e "$dir/summary.json" \
          || -e "$dir/evaluation_ledger" ]]; then
      echo "CONFLICT $short $mode s$seed (bound run artifacts do not verify)"
      exit 1
    fi

    # Safe now: the kernel lock is held, so no concurrent driver is writing into this directory.
    local reset_target
    if ! reset_target="$(resolved_run_target "$dir")"; then
      echo "CONFLICT $short $mode s$seed (unsafe run target)"
      exit 1
    fi
    rm -rf -- "$reset_target"
    local log="$ROOT/logs/${COHORT}_${short}_${mode}_s${seed}.log"
    if python3 -m sle run --task "$task" --algorithm "$ALGORITHM" \
        --feedback-mode "$mode" --budget "$BUDGET" --seed "$seed" --allow-uncertified \
        --llm-config "$CONFIG" --workdir "$dir" > "$log" 2>&1 \
        && [[ -f "$dir/run_manifest.json" && -f "$dir/summary.json" ]]; then
      request_digest "$task" "$mode" "$seed" > "$dir/.cohort_request_sha256"
      if run_is_complete "$dir" "$task" "$mode" "$seed" "$trusted_runtime"; then
        echo "done  $short $mode s$seed"
      else
        echo "CONFLICT $short $mode s$seed (new run artifacts do not verify)"
        exit 1
      fi
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
              "$task" "$mode" "$seed" "${TRUSTED_RUNTIME_RECORDS[$task]:-}"; then
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
      ( flock 9 && run_is_complete "$dir" "$task" "$mode" "$seed" \
          "${TRUSTED_RUNTIME_RECORDS[$task]:-}" ) 9>"$lock" \
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
