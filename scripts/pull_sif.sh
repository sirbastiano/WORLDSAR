#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
PROJECT_DIR="${PROJECT_DIR:-$(cd "${SCRIPT_DIR}/.." && pwd -P)}"
CONDA_ACTIVATE_SCRIPT="${CONDA_ACTIVATE_SCRIPT:-}"
CONDA_ENV="${CONDA_ENV:-esa-phisatnet}"
SIF_NAME="${SIF_NAME:-sarpyx.sif}"
SIF_REPO="${SIF_REPO:-WORLDSAR/support}"

if [ -n "${CONDA_ACTIVATE_SCRIPT}" ] && [ -f "${CONDA_ACTIVATE_SCRIPT}" ]; then
	source "${CONDA_ACTIVATE_SCRIPT}"
	conda activate "${CONDA_ENV}"
fi

hf download "${SIF_REPO}" "${SIF_NAME}" --repo-type dataset --local-dir "${PROJECT_DIR}"
