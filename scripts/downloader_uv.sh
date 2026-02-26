#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
PROJECT_DIR="${PROJECT_DIR:-$(cd "${SCRIPT_DIR}/.." && pwd -P)}"
PHIDOWN_DATA_DIR="${PHIDOWN_DATA_DIR:-${PROJECT_DIR}/phidown_data}"
PHIDOWN_CFG="${PHIDOWN_CFG:-${SCRIPT_DIR}/.s5cfg}"

source "${PROJECT_DIR}/.venv/bin/activate"

mkdir -p "${PHIDOWN_DATA_DIR}"
PRODUCT="${PRODUCT:-${1:?Usage: $0 <product_name>}}"

python -m phidown --name "${PRODUCT}" -o "${PHIDOWN_DATA_DIR}/" -c "${PHIDOWN_CFG}"
