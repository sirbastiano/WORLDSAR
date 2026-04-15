#!/bin/bash
#PBS -N shard_subap
#PBS -q cpu_std
#PBS -l walltime=23:30:00
#PBS -l select=1:ncpus=32:mem=128g
#PBS -j oe

set -euo pipefail

PROJECT_ROOT="/lustre/projects/1001/rdelprete/WORLDSAR"
CONDA_ENV="${CONDA_ENV:-phidown}"
CONDA_ACTIVATE="${CONDA_ACTIVATE:-/lustre/projects/1001/miniconda3/bin/activate}"

SOURCE_ROOT="${SOURCE_ROOT:-/lustre/scratch/1001/rdelprete/srsd_patches/dataset_sm_subaps}"
OUTPUT_ROOT="${OUTPUT_ROOT:-/lustre/scratch/1001/rdelprete/srsd_patches/dataset_sm_subaps_sharded}"
LIMIT_SHARDS="${LIMIT_SHARDS:-}"
OVERWRITE="${OVERWRITE:-1}"
SKIP_SCAN="${SKIP_SCAN:-0}"

SCRIPT_PATH="${PROJECT_ROOT}/scripts/shard_subap_dataset.py"
RUN_ROOT="${PROJECT_ROOT}/OUT/shard_runs"
RUN_NAME="subap_shard_$(date +%Y%m%d_%H%M%S)"
RUN_DIR="${RUN_ROOT}/${RUN_NAME}"
mkdir -p "${RUN_DIR}"

if [[ -n "${PBS_O_WORKDIR:-}" && -d "${PBS_O_WORKDIR}" ]]; then
    cd "${PBS_O_WORKDIR}"
else
    cd "${PROJECT_ROOT}"
fi

source "${CONDA_ACTIVATE}" "${CONDA_ENV}"
PYTHON_BIN="$(command -v python3 || command -v python)"
[[ -n "${PYTHON_BIN}" ]] || { echo "ERROR: python not found after activating ${CONDA_ENV}" >&2; exit 1; }
[[ -f "${SCRIPT_PATH}" ]] || { echo "ERROR: sharding script not found: ${SCRIPT_PATH}" >&2; exit 1; }
[[ -d "${SOURCE_ROOT}" ]] || { echo "ERROR: source dataset not found: ${SOURCE_ROOT}" >&2; exit 1; }

export PYTHONUNBUFFERED=1

{
    echo "PBS_JOBID=${PBS_JOBID:-unknown}"
    echo "PBS_QUEUE=${PBS_QUEUE:-unknown}"
    echo "PBS_O_WORKDIR=${PBS_O_WORKDIR:-unknown}"
    echo "HOSTNAME=$(hostname)"
    echo "START_TIME=$(date)"
    echo "SOURCE_ROOT=${SOURCE_ROOT}"
    echo "OUTPUT_ROOT=${OUTPUT_ROOT}"
    echo "LIMIT_SHARDS=${LIMIT_SHARDS}"
    echo "OVERWRITE=${OVERWRITE}"
    echo "SKIP_SCAN=${SKIP_SCAN}"
} > "${RUN_DIR}/job_info.txt"

env | sort > "${RUN_DIR}/env_snapshot.txt"

CMD=(
    "${PYTHON_BIN}" "${SCRIPT_PATH}"
    --source-root "${SOURCE_ROOT}"
    --output-root "${OUTPUT_ROOT}"
)

if [[ "${OVERWRITE}" == "1" ]]; then
    CMD+=(--overwrite)
fi

if [[ "${SKIP_SCAN}" == "1" ]]; then
    CMD+=(--skip-scan)
fi

if [[ -n "${LIMIT_SHARDS}" ]]; then
    CMD+=(--limit-shards "${LIMIT_SHARDS}")
fi

printf '%q ' "${CMD[@]}" > "${RUN_DIR}/command.sh"
printf '\n' >> "${RUN_DIR}/command.sh"
chmod +x "${RUN_DIR}/command.sh"

"${CMD[@]}" 2>&1 | tee "${RUN_DIR}/shard_subap_dataset.log"

echo "END_TIME=$(date)" >> "${RUN_DIR}/job_info.txt"
echo "Done. Output: ${OUTPUT_ROOT}" | tee -a "${RUN_DIR}/shard_subap_dataset.log"
