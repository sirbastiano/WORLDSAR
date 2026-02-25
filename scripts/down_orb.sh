#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
PROJECT_DIR="${PROJECT_DIR:-$(cd "${SCRIPT_DIR}/.." && pwd -P)}"
CONDA_ACTIVATE_SCRIPT="${CONDA_ACTIVATE_SCRIPT:-}"
CONDA_ENV="${CONDA_ENV:-esa-phisatnet}"
SNAP_ASSETS="${SNAP_ASSETS:-snap_userdir.tar.gz}"
SIF_REPO="${SIF_REPO:-WORLDSAR/Support}"
HF_TOKEN="${HF_TOKEN:-}"

if [ -n "${CONDA_ACTIVATE_SCRIPT}" ] && [ -f "${CONDA_ACTIVATE_SCRIPT}" ]; then
	source "${CONDA_ACTIVATE_SCRIPT}"
	conda activate "${CONDA_ENV}"
fi

# Ensure the target directory exists
mkdir -p "${PROJECT_DIR}/.snap/PEORB"

# Change to project directory
cd "${PROJECT_DIR}"

if [ -n "${HF_TOKEN}" ]; then
	hf download "${SIF_REPO}" "${SNAP_ASSETS}" --repo-type dataset --local-dir "${PROJECT_DIR}" --token "${HF_TOKEN}"
else
	hf download "${SIF_REPO}" "${SNAP_ASSETS}" --repo-type dataset --local-dir "${PROJECT_DIR}"
fi
