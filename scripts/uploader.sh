#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
PROJECT_DIR="${PROJECT_DIR:-$(cd "${SCRIPT_DIR}/.." && pwd -P)}"
CONDA_ACTIVATE_SCRIPT="${CONDA_ACTIVATE_SCRIPT:-}"
CONDA_ENV="${CONDA_ENV:-hf}"
TILES_DIR="${TILES_DIR:-${PROJECT_DIR}/OUT/tiles}"
DB_DIR="${DB_DIR:-${PROJECT_DIR}/OUT/DB}"

if [ -n "${CONDA_ACTIVATE_SCRIPT}" ] && [ -f "${CONDA_ACTIVATE_SCRIPT}" ]; then
	source "${CONDA_ACTIVATE_SCRIPT}"
	conda activate "${CONDA_ENV}"
fi

hf upload-large-folder "WORLDSAR/S1Toy" "${TILES_DIR}/" --repo-type=dataset --num-workers 1
hf upload "WORLDSAR/Database" "${DB_DIR}/" --repo-type=dataset
