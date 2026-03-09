#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd -P)"

DATA_DIR="${DATA_DIR:-${REPO_DIR}/phidown_data}"
LOG_DIR="${LOG_DIR:-${REPO_DIR}/logs_worldsar_submit}"
mkdir -p "$LOG_DIR"

# ---- Time configuration ----
GPT_TIMEOUT="${GPT_TIMEOUT:-84600}"     # seconds
PBS_WALLTIME="${PBS_WALLTIME:-23:30:00}"

# ---- HPC resources ----
HPC_GPT_MEMORY="${HPC_GPT_MEMORY:-128G}"
HPC_GPT_PARALLELISM="${HPC_GPT_PARALLELISM:-164}"
HPC_PBS_QUEUE="${HPC_PBS_QUEUE:-cpu_std}"
HPC_PBS_SELECT="${HPC_PBS_SELECT:-select=1:ncpus=192:mem=100g}"

# Optional throttle (0 = submit all immediately)
MAX_IN_FLIGHT="${MAX_IN_FLIGHT:-0}"
SLEEP_SEC="${SLEEP_SEC:-30}"

count_jobs() {
  qstat -u "$USER" 2>/dev/null | awk 'NR>2 {c++} END{print c+0}' || echo 0
}

echo "========================================"
echo "WorldSAR batch submission"
echo "DATA_DIR             = $DATA_DIR"
echo "GPT_TIMEOUT          = $GPT_TIMEOUT sec"
echo "PBS_WALLTIME         = $PBS_WALLTIME"
echo "HPC_GPT_MEMORY       = $HPC_GPT_MEMORY"
echo "HPC_GPT_PARALLELISM  = $HPC_GPT_PARALLELISM"
echo "HPC_PBS_QUEUE        = $HPC_PBS_QUEUE"
echo "HPC_PBS_SELECT       = $HPC_PBS_SELECT"
echo "MAX_IN_FLIGHT        = $MAX_IN_FLIGHT"
echo "========================================"

shopt -s nullglob

found=0

for safe_path in "${DATA_DIR}"/*.SAFE; do
  found=1
  prod="$(basename "$safe_path")"
  log="${LOG_DIR}/${prod}.log"

  if [[ "$MAX_IN_FLIGHT" -gt 0 ]]; then
    while true; do
      running="$(count_jobs)"
      if [[ "$running" -lt "$MAX_IN_FLIGHT" ]]; then
        break
      fi
      echo "[WAIT] $running jobs running (limit $MAX_IN_FLIGHT)"
      sleep "$SLEEP_SEC"
    done
  fi

  echo "[SUBMIT] $prod"

  (
    cd "$REPO_DIR"

    WORLDSAR_MODE=hpc make run \
      "PRODUCT=$prod" \
      "GPT_TIMEOUT=$GPT_TIMEOUT" \
      "PBS_WALLTIME=$PBS_WALLTIME" \
      "HPC_GPT_MEMORY=$HPC_GPT_MEMORY" \
      "HPC_GPT_PARALLELISM=$HPC_GPT_PARALLELISM" \
      "HPC_PBS_QUEUE=$HPC_PBS_QUEUE" \
      "HPC_PBS_SELECT=$HPC_PBS_SELECT"

  ) 2>&1 | tee "$log"

done

if [[ "$found" -eq 0 ]]; then
  echo "ERROR: no SAFE directories found in $DATA_DIR" >&2
  exit 2
fi

echo
echo "All jobs submitted."
echo "Submission logs in: $LOG_DIR"