#!/bin/bash
set -euo pipefail

PROJECT_ROOT="/lustre/projects/1001/rdelprete/WORLDSAR"
PY_SCRIPT="${PROJECT_ROOT}/pyscripts/src/validate_subap_configuration.py"

INPUT_ROOT="${INPUT_ROOT:-${PROJECT_ROOT}/OUT/worldsar_output}"
OUTPUT_ROOT="${OUTPUT_ROOT:-/lustre/scratch/1001/rdelprete/worldsar_subap_validation}"
CONFIG_MODE="${CONFIG_MODE:-available}"
SUBAP_COUNTS="${SUBAP_COUNTS:-}"
WIN_SIZES="${WIN_SIZES:-3,5,7}"
BASE_MODE="${BASE_MODE:-iq}"
INCLUDE_AGGREGATE="${INCLUDE_AGGREGATE:-0}"
SAMPLES_PER_LOOKSET="${SAMPLES_PER_LOOKSET:-8}"
PATCH_SIZE="${PATCH_SIZE:-128}"
MAX_PRODUCTS="${MAX_PRODUCTS:-}"
PYTHON_BIN="${PYTHON_BIN:-python3}"

export OPENBLAS_NUM_THREADS="${OPENBLAS_NUM_THREADS:-1}"
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-1}"
export MKL_NUM_THREADS="${MKL_NUM_THREADS:-1}"
export NUMEXPR_NUM_THREADS="${NUMEXPR_NUM_THREADS:-1}"

if [[ ! -f "${PY_SCRIPT}" ]]; then
    echo "ERROR: Python script not found: ${PY_SCRIPT}"
    exit 1
fi

mkdir -p "${OUTPUT_ROOT}"

echo "========================================"
echo "Validate WorldSAR subap configuration"
echo "INPUT_ROOT          = ${INPUT_ROOT}"
echo "OUTPUT_ROOT         = ${OUTPUT_ROOT}"
echo "SUBAP_COUNTS        = ${SUBAP_COUNTS}"
echo "CONFIG_MODE         = ${CONFIG_MODE}"
echo "WIN_SIZES           = ${WIN_SIZES}"
echo "BASE_MODE           = ${BASE_MODE}"
echo "INCLUDE_AGGREGATE   = ${INCLUDE_AGGREGATE}"
echo "SAMPLES_PER_LOOKSET = ${SAMPLES_PER_LOOKSET}"
echo "PATCH_SIZE          = ${PATCH_SIZE}"
echo "PYTHON_BIN          = ${PYTHON_BIN}"
echo "OPENBLAS_NUM_THREADS = ${OPENBLAS_NUM_THREADS}"
echo "========================================"

CMD=(
    "${PYTHON_BIN}" "${PY_SCRIPT}"
    --input-root "${INPUT_ROOT}"
    --output-root "${OUTPUT_ROOT}"
    --config-mode "${CONFIG_MODE}"
    --win-sizes "${WIN_SIZES}"
    --base-mode "${BASE_MODE}"
    --samples-per-lookset "${SAMPLES_PER_LOOKSET}"
    --patch-size "${PATCH_SIZE}"
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

"${CMD[@]}"
