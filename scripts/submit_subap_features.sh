#!/bin/bash
#PBS -N subap_feats
#PBS -q cpu_std
#PBS -l walltime=02:00:00
#PBS -l select=1:ncpus=8:mem=32g
#PBS -j oe

set -euo pipefail

PROJECT_ROOT="/lustre/projects/1001/rdelprete/WORLDSAR"
PBS_SCRIPT="${PROJECT_ROOT}/scripts/subap_features_cpu_job.sh"

QUEUE="${QUEUE:-cpu_std}"
INPUT_ROOT="${INPUT_ROOT:-${PROJECT_ROOT}/OUT/worldsar_output/IW1}"
OUTPUT_ROOT="${OUTPUT_ROOT:-/lustre/scratch/1001/rdelprete/worldsar_subap_features}"
WIN_SIZE="${WIN_SIZE:-5}"
CONDA_ENV="${CONDA_ENV:-phidown}"
CONDA_ACTIVATE="${CONDA_ACTIVATE:-/lustre/projects/1001/miniconda3/bin/activate}"

if [[ ! -f "${PBS_SCRIPT}" ]]; then
    echo "ERROR: PBS script not found: ${PBS_SCRIPT}" >&2
    exit 1
fi

QSUB_VARS=(
    "INPUT_ROOT=${INPUT_ROOT}"
    "OUTPUT_ROOT=${OUTPUT_ROOT}"
    "WIN_SIZE=${WIN_SIZE}"
    "CONDA_ENV=${CONDA_ENV}"
    "CONDA_ACTIVATE=${CONDA_ACTIVATE}"
)

QSUB_VARS_STR="$(IFS=,; echo "${QSUB_VARS[*]}")"

echo "Submitting subap feature job to ${QUEUE}"
echo "INPUT_ROOT=${INPUT_ROOT}"
echo "OUTPUT_ROOT=${OUTPUT_ROOT}"
echo "WIN_SIZE=${WIN_SIZE}"

qsub \
  -q "${QUEUE}" \
  -v "${QSUB_VARS_STR}" \
  "${PBS_SCRIPT}"
