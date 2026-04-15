#!/bin/bash
#PBS -N subap_plot
#PBS -q cpu_std
#PBS -l walltime=11:30:00
#PBS -l select=1:ncpus=8:mem=32g
#PBS -j oe

"""
example qsub command:
qsub -q cpu_std \                                                                            
  -v INPUT_ROOT="/lustre/projects/1001/rdelprete/WORLDSAR/OUT/worldsar_output/IW1",FEATURES_ROOT="/lustre/scratch/1001/rdelprete/worldsar_subap_features",OUTPUT_ROOT="/lustre/scratch/1001/rdelprete/worldsar_subap_figures",PREVIEW_SIZE=1024,ZOOM_SIZE=1024,CONDA_ENV=phidown,CONDA_ACTIVATE=/lustre/projects/1001/miniconda3/bin/activate \
  /lustre/projects/1001/rdelprete/WORLDSAR/scripts/plot_subap_products_cpu_job.sh

"""

set -euo pipefail

PROJECT_ROOT="/lustre/projects/1001/rdelprete/WORLDSAR"
CONDA_ENV="${CONDA_ENV:-phidown}"
CONDA_ACTIVATE="${CONDA_ACTIVATE:-/lustre/projects/1001/miniconda3/bin/activate}"

INPUT_ROOT="${INPUT_ROOT:-${PROJECT_ROOT}/OUT/worldsar_output/IW1}"
FEATURES_ROOT="${FEATURES_ROOT:-/lustre/scratch/1001/rdelprete/worldsar_subap_features}"
OUTPUT_ROOT="${OUTPUT_ROOT:-/lustre/scratch/1001/rdelprete/worldsar_subap_figures}"
PREVIEW_SIZE="${PREVIEW_SIZE:-1024}"
ZOOM_SIZE="${ZOOM_SIZE:-1024}"
INTENSITY_PMIN="${INTENSITY_PMIN:-2}"
INTENSITY_PMAX="${INTENSITY_PMAX:-98}"
PY_SCRIPT="${PROJECT_ROOT}/pyscripts/src/plot_subap_products.py"

RUN_ROOT="${PROJECT_ROOT}/OUT/subap_plot_runs"
RUN_NAME="subap_plots_$(date +%Y%m%d_%H%M%S)"
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
[[ -d "${FEATURES_ROOT}" ]] || { echo "ERROR: features root not found: ${FEATURES_ROOT}" >&2; exit 1; }

mkdir -p "${OUTPUT_ROOT}"
export PYTHONUNBUFFERED=1

{
    echo "PBS_JOBID=${PBS_JOBID:-unknown}"
    echo "PBS_QUEUE=${PBS_QUEUE:-unknown}"
    echo "PBS_O_WORKDIR=${PBS_O_WORKDIR:-unknown}"
    echo "HOSTNAME=$(hostname)"
    echo "START_TIME=$(date)"
    echo "INPUT_ROOT=${INPUT_ROOT}"
    echo "FEATURES_ROOT=${FEATURES_ROOT}"
    echo "OUTPUT_ROOT=${OUTPUT_ROOT}"
    echo "PREVIEW_SIZE=${PREVIEW_SIZE}"
    echo "ZOOM_SIZE=${ZOOM_SIZE}"
    echo "INTENSITY_PMIN=${INTENSITY_PMIN}"
    echo "INTENSITY_PMAX=${INTENSITY_PMAX}"
    echo "CONDA_ENV=${CONDA_ENV}"
} > "${RUN_DIR}/job_info.txt"

env | sort > "${RUN_DIR}/env_snapshot.txt"

CMD=(
    "${PYTHON_BIN}" "${PY_SCRIPT}"
    --input-root "${INPUT_ROOT}"
    --features-root "${FEATURES_ROOT}"
    --output-root "${OUTPUT_ROOT}"
    --preview-size "${PREVIEW_SIZE}"
    --zoom-size "${ZOOM_SIZE}"
    --intensity-pmin "${INTENSITY_PMIN}"
    --intensity-pmax "${INTENSITY_PMAX}"
)

printf '%q ' "${CMD[@]}" > "${RUN_DIR}/command.sh"
printf '\n' >> "${RUN_DIR}/command.sh"
chmod +x "${RUN_DIR}/command.sh"

"${CMD[@]}" 2>&1 | tee "${RUN_DIR}/plot_subap_products.log"

echo "END_TIME=$(date)" >> "${RUN_DIR}/job_info.txt"
echo "Done. Output: ${OUTPUT_ROOT}" | tee -a "${RUN_DIR}/plot_subap_products.log"
