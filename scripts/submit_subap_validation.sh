#!/bin/bash
#PBS -N subap_valid
#PBS -q cpu_std
#PBS -l walltime=02:00:00
#PBS -l select=1:ncpus=8:mem=32g
#PBS -j oe

set -euo pipefail

PROJECT_ROOT="/lustre/projects/1001/rdelprete/WORLDSAR"
PBS_SCRIPT="${PROJECT_ROOT}/scripts/subap_validation_cpu_job.sh"

QUEUE="${QUEUE:-cpu_std}"
INPUT_ROOT="${INPUT_ROOT:-${PROJECT_ROOT}/OUT/worldsar_output/IW1}"
OUTPUT_ROOT="${OUTPUT_ROOT:-/lustre/scratch/1001/rdelprete/worldsar_subap_validation}"
CONFIG_MODE="${CONFIG_MODE:-available}"
SUBAP_COUNTS="${SUBAP_COUNTS:-}"
WIN_SIZES="${WIN_SIZES:-3,5,7}"
BASE_MODE="${BASE_MODE:-iq}"
INCLUDE_AGGREGATE="${INCLUDE_AGGREGATE:-0}"
SAMPLES_PER_LOOKSET="${SAMPLES_PER_LOOKSET:-8}"
PATCH_SIZE="${PATCH_SIZE:-128}"
MAX_PIXELS_PER_BLOCK="${MAX_PIXELS_PER_BLOCK:-2048}"
MAX_PRODUCTS="${MAX_PRODUCTS:-}"
CONDA_ENV="${CONDA_ENV:-phidown}"
CONDA_ACTIVATE="${CONDA_ACTIVATE:-/lustre/projects/1001/miniconda3/bin/activate}"

if [[ ! -f "${PBS_SCRIPT}" ]]; then
    echo "ERROR: PBS script not found: ${PBS_SCRIPT}" >&2
    exit 1
fi

QSUB_VARS=(
    "INPUT_ROOT=${INPUT_ROOT}"
    "OUTPUT_ROOT=${OUTPUT_ROOT}"
    "SUBAP_COUNTS=${SUBAP_COUNTS}"
    "CONFIG_MODE=${CONFIG_MODE}"
    "WIN_SIZES=${WIN_SIZES}"
    "BASE_MODE=${BASE_MODE}"
    "INCLUDE_AGGREGATE=${INCLUDE_AGGREGATE}"
    "SAMPLES_PER_LOOKSET=${SAMPLES_PER_LOOKSET}"
    "PATCH_SIZE=${PATCH_SIZE}"
    "MAX_PIXELS_PER_BLOCK=${MAX_PIXELS_PER_BLOCK}"
    "MAX_PRODUCTS=${MAX_PRODUCTS}"
    "CONDA_ENV=${CONDA_ENV}"
    "CONDA_ACTIVATE=${CONDA_ACTIVATE}"
)

QSUB_VARS_STR="$(IFS=,; echo "${QSUB_VARS[*]}")"

echo "Submitting subap validation job to ${QUEUE}"
echo "INPUT_ROOT=${INPUT_ROOT}"
echo "OUTPUT_ROOT=${OUTPUT_ROOT}"
echo "SUBAP_COUNTS=${SUBAP_COUNTS}"
echo "CONFIG_MODE=${CONFIG_MODE}"
echo "WIN_SIZES=${WIN_SIZES}"
echo "BASE_MODE=${BASE_MODE}"

qsub \
  -q "${QUEUE}" \
  -v "${QSUB_VARS_STR}" \
  "${PBS_SCRIPT}"
