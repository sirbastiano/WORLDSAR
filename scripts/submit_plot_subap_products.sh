#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="/lustre/projects/1001/rdelprete/WORLDSAR"
PBS_SCRIPT="${PROJECT_ROOT}/scripts/plot_subap_products_cpu_job.sh"

QUEUE="${QUEUE:-cpu_std}"
INPUT_ROOT="${INPUT_ROOT:-${PROJECT_ROOT}/OUT/worldsar_output/IW1}"
FEATURES_ROOT="${FEATURES_ROOT:-/lustre/scratch/1001/rdelprete/worldsar_subap_features}"
OUTPUT_ROOT="${OUTPUT_ROOT:-/lustre/scratch/1001/rdelprete/worldsar_subap_figures}"
PREVIEW_SIZE="${PREVIEW_SIZE:-1024}"
ZOOM_SIZE="${ZOOM_SIZE:-1024}"
INTENSITY_PMIN="${INTENSITY_PMIN:-2}"
INTENSITY_PMAX="${INTENSITY_PMAX:-98}"
CONDA_ENV="${CONDA_ENV:-phidown}"
CONDA_ACTIVATE="${CONDA_ACTIVATE:-/lustre/projects/1001/miniconda3/bin/activate}"

if [[ ! -f "${PBS_SCRIPT}" ]]; then
    echo "ERROR: PBS script not found: ${PBS_SCRIPT}" >&2
    exit 1
fi

QSUB_VARS=(
    "INPUT_ROOT=${INPUT_ROOT}"
    "FEATURES_ROOT=${FEATURES_ROOT}"
    "OUTPUT_ROOT=${OUTPUT_ROOT}"
    "PREVIEW_SIZE=${PREVIEW_SIZE}"
    "ZOOM_SIZE=${ZOOM_SIZE}"
    "INTENSITY_PMIN=${INTENSITY_PMIN}"
    "INTENSITY_PMAX=${INTENSITY_PMAX}"
    "CONDA_ENV=${CONDA_ENV}"
    "CONDA_ACTIVATE=${CONDA_ACTIVATE}"
)

QSUB_VARS_STR="$(IFS=,; echo "${QSUB_VARS[*]}")"

echo "Submitting subap plot job to ${QUEUE}"
echo "INPUT_ROOT=${INPUT_ROOT}"
echo "FEATURES_ROOT=${FEATURES_ROOT}"
echo "OUTPUT_ROOT=${OUTPUT_ROOT}"
echo "PREVIEW_SIZE=${PREVIEW_SIZE}"
echo "ZOOM_SIZE=${ZOOM_SIZE}"
echo "INTENSITY_PMIN=${INTENSITY_PMIN}"
echo "INTENSITY_PMAX=${INTENSITY_PMAX}"

qsub \
  -q "${QUEUE}" \
  -v "${QSUB_VARS_STR}" \
  "${PBS_SCRIPT}"
