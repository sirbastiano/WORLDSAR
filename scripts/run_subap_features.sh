#!/bin/bash
set -euo pipefail

PROJECT_ROOT="/lustre/projects/1001/rdelprete/WORLDSAR"
PY_SCRIPT="${PROJECT_ROOT}/pyscripts/src/compute_subap_features.py"

INPUT_ROOT="${INPUT_ROOT:-${PROJECT_ROOT}/OUT/worldsar_output}"
OUTPUT_ROOT="${OUTPUT_ROOT:-/lustre/scratch/1001/rdelprete/worldsar_subap_features}"
WIN_SIZE="${WIN_SIZE:-5}"
PYTHON_BIN="${PYTHON_BIN:-python3}"

if [[ ! -f "${PY_SCRIPT}" ]]; then
    echo "ERROR: Python script not found: ${PY_SCRIPT}"
    exit 1
fi

mkdir -p "${OUTPUT_ROOT}"

echo "========================================"
echo "Compute WorldSAR subap features"
echo "INPUT_ROOT   = ${INPUT_ROOT}"
echo "OUTPUT_ROOT  = ${OUTPUT_ROOT}"
echo "WIN_SIZE     = ${WIN_SIZE}"
echo "PYTHON_BIN   = ${PYTHON_BIN}"
echo "========================================"

"${PYTHON_BIN}" "${PY_SCRIPT}" \
    --input-root "${INPUT_ROOT}" \
    --output-root "${OUTPUT_ROOT}" \
    --win-size "${WIN_SIZE}"
