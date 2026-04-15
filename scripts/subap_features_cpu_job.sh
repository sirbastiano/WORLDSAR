#!/bin/bash
#PBS -N subap_feat
#PBS -q cpu_std
#PBS -l walltime=23:30:00
#PBS -l select=1:ncpus=16:mem=64g
#PBS -j oe

set -euo pipefail

PROJECT_ROOT="/lustre/projects/1001/rdelprete/WORLDSAR"
CONDA_ENV="${CONDA_ENV:-phidown}"
CONDA_ACTIVATE="${CONDA_ACTIVATE:-/lustre/projects/1001/miniconda3/bin/activate}"

INPUT_ROOT="${INPUT_ROOT:-${PROJECT_ROOT}/OUT/worldsar_output/IW1}"
OUTPUT_ROOT="${OUTPUT_ROOT:-/lustre/scratch/1001/rdelprete/worldsar_subap_features}"
WIN_SIZE="${WIN_SIZE:-5}"
PY_SCRIPT="${PROJECT_ROOT}/pyscripts/src/compute_subap_features.py"

RUN_ROOT="${PROJECT_ROOT}/OUT/subap_feature_runs"
RUN_NAME="subap_features_$(date +%Y%m%d_%H%M%S)"
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

{
    echo "PBS_JOBID=${PBS_JOBID:-unknown}"
    echo "PBS_QUEUE=${PBS_QUEUE:-unknown}"
    echo "PBS_O_WORKDIR=${PBS_O_WORKDIR:-unknown}"
    echo "HOSTNAME=$(hostname)"
    echo "START_TIME=$(date)"
    echo "INPUT_ROOT=${INPUT_ROOT}"
    echo "OUTPUT_ROOT=${OUTPUT_ROOT}"
    echo "WIN_SIZE=${WIN_SIZE}"
    echo "CONDA_ENV=${CONDA_ENV}"
} > "${RUN_DIR}/job_info.txt"

env | sort > "${RUN_DIR}/env_snapshot.txt"

CMD=(
    "${PYTHON_BIN}" "${PY_SCRIPT}"
    --input-root "${INPUT_ROOT}"
    --output-root "${OUTPUT_ROOT}"
    --win-size "${WIN_SIZE}"
)

printf '%q ' "${CMD[@]}" > "${RUN_DIR}/command.sh"
printf '\n' >> "${RUN_DIR}/command.sh"
chmod +x "${RUN_DIR}/command.sh"

"${CMD[@]}" 2>&1 | tee "${RUN_DIR}/compute_subap_features.log"

echo "END_TIME=$(date)" >> "${RUN_DIR}/job_info.txt"
echo "Done. Output: ${OUTPUT_ROOT}" | tee -a "${RUN_DIR}/compute_subap_features.log"
