#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="/lustre/projects/1001/rdelprete/WORLDSAR"
PBS_SCRIPT="${PROJECT_ROOT}/scripts/shard_subap_dataset_cpu_job.sh"

QUEUE="${QUEUE:-cpu_std}"
SOURCE_ROOT="${SOURCE_ROOT:-/lustre/scratch/1001/rdelprete/srsd_patches/dataset_sm_subaps}"
OUTPUT_ROOT="${OUTPUT_ROOT:-/lustre/scratch/1001/rdelprete/srsd_patches/dataset_sm_subaps_sharded}"
LIMIT_SHARDS="${LIMIT_SHARDS:-}"
OVERWRITE="${OVERWRITE:-1}"
SKIP_SCAN="${SKIP_SCAN:-0}"
CONDA_ENV="${CONDA_ENV:-phidown}"
CONDA_ACTIVATE="${CONDA_ACTIVATE:-/lustre/projects/1001/miniconda3/bin/activate}"

if [[ ! -f "${PBS_SCRIPT}" ]]; then
    echo "ERROR: PBS script not found: ${PBS_SCRIPT}" >&2
    exit 1
fi

QSUB_VARS=(
    "SOURCE_ROOT=${SOURCE_ROOT}"
    "OUTPUT_ROOT=${OUTPUT_ROOT}"
    "OVERWRITE=${OVERWRITE}"
    "SKIP_SCAN=${SKIP_SCAN}"
    "CONDA_ENV=${CONDA_ENV}"
    "CONDA_ACTIVATE=${CONDA_ACTIVATE}"
)

if [[ -n "${LIMIT_SHARDS}" ]]; then
    QSUB_VARS+=("LIMIT_SHARDS=${LIMIT_SHARDS}")
fi

QSUB_VARS_STR="$(IFS=,; echo "${QSUB_VARS[*]}")"

echo "Submitting sharding job to ${QUEUE}"
echo "SOURCE_ROOT=${SOURCE_ROOT}"
echo "OUTPUT_ROOT=${OUTPUT_ROOT}"

qsub \
  -q "${QUEUE}" \
  -v "${QSUB_VARS_STR}" \
  "${PBS_SCRIPT}"
