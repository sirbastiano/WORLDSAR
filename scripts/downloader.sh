#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
PROJECT_DIR="${PROJECT_DIR:-$(cd "${SCRIPT_DIR}/.." && pwd -P)}"
CONDA_ACTIVATE_SCRIPT="${CONDA_ACTIVATE_SCRIPT:-}"
CONDA_ENV="${CONDA_ENV:-phidown}"
PHIDOWN_DATA_DIR="${PHIDOWN_DATA_DIR:-${PROJECT_DIR}/phidown_data}"
PHIDOWN_CFG="${PHIDOWN_CFG:-${PROJECT_DIR}/service/.s5cfg}"

if [ -n "${CONDA_ACTIVATE_SCRIPT}" ] && [ -f "${CONDA_ACTIVATE_SCRIPT}" ]; then
	source "${CONDA_ACTIVATE_SCRIPT}"
	conda activate "${CONDA_ENV}"
fi

mkdir -p "${PHIDOWN_DATA_DIR}"
PRODUCT="${PRODUCT:-${1:?Usage: $0 <product_name>}}"

python -m phidown --name "${PRODUCT}" -o "${PHIDOWN_DATA_DIR}/" -c "${PHIDOWN_CFG}"
