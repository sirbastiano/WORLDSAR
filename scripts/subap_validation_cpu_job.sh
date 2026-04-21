#!/bin/bash
#PBS -N subap_valid
#PBS -q cpu_std
#PBS -l walltime=08:00:00
#PBS -l select=1:ncpus=16:mem=64g
#PBS -j oe

set -euo pipefail

PROJECT_ROOT="/lustre/projects/1001/rdelprete/WORLDSAR"
CONDA_ENV="${CONDA_ENV:-phidown}"
CONDA_ACTIVATE="${CONDA_ACTIVATE:-/lustre/projects/1001/miniconda3/bin/activate}"

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
PY_SCRIPT="${PROJECT_ROOT}/pyscripts/src/validate_subap_configuration.py"

RUN_ROOT="${PROJECT_ROOT}/OUT/subap_validation_runs"
RUN_NAME="subap_validation_$(date +%Y%m%d_%H%M%S)"
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
[[ -f "${PY_SCRIPT}" ]] || { echo "ERROR: Python script not found: ${PY_SCRIPT}" >&2; exit 1; }
[[ -d "${INPUT_ROOT}" ]] || { echo "ERROR: input root not found: ${INPUT_ROOT}" >&2; exit 1; }

mkdir -p "${OUTPUT_ROOT}"
export PYTHONUNBUFFERED=1
export OPENBLAS_NUM_THREADS="${OPENBLAS_NUM_THREADS:-1}"
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-1}"
export MKL_NUM_THREADS="${MKL_NUM_THREADS:-1}"
export NUMEXPR_NUM_THREADS="${NUMEXPR_NUM_THREADS:-1}"

{
    echo "PBS_JOBID=${PBS_JOBID:-unknown}"
    echo "PBS_QUEUE=${PBS_QUEUE:-unknown}"
    echo "PBS_O_WORKDIR=${PBS_O_WORKDIR:-unknown}"
    echo "HOSTNAME=$(hostname)"
    echo "START_TIME=$(date)"
    echo "INPUT_ROOT=${INPUT_ROOT}"
    echo "OUTPUT_ROOT=${OUTPUT_ROOT}"
    echo "SUBAP_COUNTS=${SUBAP_COUNTS}"
    echo "CONFIG_MODE=${CONFIG_MODE}"
    echo "WIN_SIZES=${WIN_SIZES}"
    echo "BASE_MODE=${BASE_MODE}"
    echo "INCLUDE_AGGREGATE=${INCLUDE_AGGREGATE}"
    echo "SAMPLES_PER_LOOKSET=${SAMPLES_PER_LOOKSET}"
    echo "PATCH_SIZE=${PATCH_SIZE}"
    echo "MAX_PIXELS_PER_BLOCK=${MAX_PIXELS_PER_BLOCK}"
    echo "MAX_PRODUCTS=${MAX_PRODUCTS}"
    echo "CONDA_ENV=${CONDA_ENV}"
} > "${RUN_DIR}/job_info.txt"

env | sort > "${RUN_DIR}/env_snapshot.txt"

CMD=(
    "${PYTHON_BIN}" "${PY_SCRIPT}"
    --input-root "${INPUT_ROOT}"
    --output-root "${OUTPUT_ROOT}"
    --config-mode "${CONFIG_MODE}"
    --win-sizes "${WIN_SIZES}"
    --base-mode "${BASE_MODE}"
    --samples-per-lookset "${SAMPLES_PER_LOOKSET}"
    --patch-size "${PATCH_SIZE}"
    --max-pixels-per-block "${MAX_PIXELS_PER_BLOCK}"
)

if [[ -n "${SUBAP_COUNTS}" ]]; then
    CMD+=(--subap-counts "${SUBAP_COUNTS}")
fi

if [[ "${INCLUDE_AGGREGATE}" == "1" || "${INCLUDE_AGGREGATE}" == "true" ]]; then
    CMD+=(--include-aggregate)
fi

if [[ -n "${MAX_PRODUCTS}" ]]; then
    CMD+=(--max-products "${MAX_PRODUCTS}")
fi

printf '%q ' "${CMD[@]}" > "${RUN_DIR}/command.sh"
printf '\n' >> "${RUN_DIR}/command.sh"
chmod +x "${RUN_DIR}/command.sh"

"${CMD[@]}" 2>&1 | tee "${RUN_DIR}/subap_validation.log"

echo "END_TIME=$(date)" >> "${RUN_DIR}/job_info.txt"
echo "Done. Output: ${OUTPUT_ROOT}" | tee -a "${RUN_DIR}/subap_validation.log"
