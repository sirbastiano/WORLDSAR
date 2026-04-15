#!/bin/bash
set -euo pipefail

PROJECT_ROOT="/lustre/projects/1001/rdelprete/WORLDSAR"
PY_SCRIPT="${PROJECT_ROOT}/pyscripts/src/plot_subap_products.py"

INPUT_ROOT="${INPUT_ROOT:-${PROJECT_ROOT}/OUT/worldsar_output}"
FEATURES_ROOT="${FEATURES_ROOT:-/lustre/scratch/1001/rdelprete/worldsar_subap_features}"
OUTPUT_ROOT="${OUTPUT_ROOT:-/lustre/scratch/1001/rdelprete/worldsar_subap_figures}"
PREVIEW_SIZE="${PREVIEW_SIZE:-1024}"
ZOOM_SIZE="${ZOOM_SIZE:-1024}"
INTENSITY_PMIN="${INTENSITY_PMIN:-2}"
INTENSITY_PMAX="${INTENSITY_PMAX:-98}"
PYTHON_BIN="${PYTHON_BIN:-python3}"

if [[ ! -f "${PY_SCRIPT}" ]]; then
    echo "ERROR: Python script not found: ${PY_SCRIPT}"
    exit 1
fi

mkdir -p "${OUTPUT_ROOT}"

echo "========================================"
echo "Plot WorldSAR subap products"
echo "INPUT_ROOT    = ${INPUT_ROOT}"
echo "FEATURES_ROOT = ${FEATURES_ROOT}"
echo "OUTPUT_ROOT   = ${OUTPUT_ROOT}"
echo "PREVIEW_SIZE  = ${PREVIEW_SIZE}"
echo "ZOOM_SIZE     = ${ZOOM_SIZE}"
echo "INT_PMIN      = ${INTENSITY_PMIN}"
echo "INT_PMAX      = ${INTENSITY_PMAX}"
echo "PYTHON_BIN    = ${PYTHON_BIN}"
echo "========================================"

"${PYTHON_BIN}" "${PY_SCRIPT}" \
    --input-root "${INPUT_ROOT}" \
    --features-root "${FEATURES_ROOT}" \
    --output-root "${OUTPUT_ROOT}" \
    --preview-size "${PREVIEW_SIZE}" \
    --zoom-size "${ZOOM_SIZE}" \
    --intensity-pmin "${INTENSITY_PMIN}" \
    --intensity-pmax "${INTENSITY_PMAX}"
