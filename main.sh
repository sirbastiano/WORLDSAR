#!/bin/bash
#PBS -N worldsar
#PBS -q cpu_std
#PBS -l walltime=02:00:00
#PBS -l select=1:ncpus=192:mem=128g

set -euo pipefail

# ---- Paths (override if needed) ----
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
BASE_DIR="${BASE_DIR:-$(cd "${SCRIPT_DIR}/." && pwd -P)}"
DATA_DIR="${DATA_DIR:-${BASE_DIR}/phidown_data}"
PY_SCRIPT_DIR="${PY_SCRIPT_DIR:-${BASE_DIR}/pyscripts}"
SIF_IMAGE="${SIF_IMAGE:-${BASE_DIR}/sarpyx.sif}"

# Product selection: first positional arg, then PRODUCT env var.
PRODUCT_NAME="${1:-${PRODUCT:-}}"
if [[ -z "${PRODUCT_NAME}" ]]; then
  echo "ERROR: Product name is required." >&2
  echo "Usage: ${0##*/} <product_name>" >&2
  echo "Or set PRODUCT=<product_name>" >&2
  exit 2
fi
PRODUCT_NAME="$(basename "${PRODUCT_NAME}")"
PROD_PATH="${DATA_DIR}/${PRODUCT_NAME}"

OUTPUT_PATH="${OUTPUT_PATH:-${BASE_DIR}/OUT/worldsar_output}"
CUTS_OUTDIR="${CUTS_OUTDIR:-${BASE_DIR}/OUT/tiles}"
DB_DIR="${DB_DIR:-${BASE_DIR}/OUT/DB}"
SNAP_USER_DIR="${SNAP_USER_DIR:-${BASE_DIR}/.snap}"
# ---- Parameters ----
GPT_MEMORY="${GPT_MEMORY:-64G}"
GPT_PARALLELISM="${GPT_PARALLELISM:-164}"
GPT_TIMEOUT="${GPT_TIMEOUT:-3600}"
WORKSPACE_PREFIX="${WORKSPACE_PREFIX:-/work}"
# SNAP userdir stores cache/config; GPT binary location is independent.
GPT_PATH="${GPT_PATH:-gpt}"
GRID_PATH="${GRID_PATH:-${WORKSPACE_PREFIX}/grid/grid_10km.geojson}"
GRID_HOST_DIR="${GRID_HOST_DIR:-}"

# ---- Basic validation ----
[[ -d "${DATA_DIR}" ]]     || { echo "ERROR: DATA_DIR not found: ${DATA_DIR}" >&2; exit 2; }
[[ -d "${PY_SCRIPT_DIR}" ]] || { echo "ERROR: PY_SCRIPT_DIR not found: ${PY_SCRIPT_DIR}" >&2; exit 2; }
[[ -f "${SIF_IMAGE}" ]]  || { echo "ERROR: SIF_IMAGE not found: ${SIF_IMAGE}" >&2; exit 2; }
[[ -d "${PROD_PATH}" ]]  || { echo "ERROR: PROD_PATH not found (SAFE dir): ${PROD_PATH}" >&2; exit 2; }
[[ -d "${SNAP_USER_DIR}" ]] || { echo "ERROR: SNAP_USER_DIR not found: ${SNAP_USER_DIR}" >&2; exit 2; }

FALLBACK_OUTPUT_ROOT="${BASE_DIR}/outputs"
use_fallback_outputs() {
  OUTPUT_PATH="${FALLBACK_OUTPUT_ROOT}/worldsar_output"
  CUTS_OUTDIR="${FALLBACK_OUTPUT_ROOT}/tiles"
  DB_DIR="${FALLBACK_OUTPUT_ROOT}/DB"
}

configured_outputs_resolved=1
for out_path in "${OUTPUT_PATH}" "${CUTS_OUTDIR}" "${DB_DIR}"; do
  if [[ -L "${out_path}" && ! -e "${out_path}" ]]; then
    echo "WARN: unresolved output symlink: ${out_path} -> $(readlink "${out_path}" || echo "<unknown>")" >&2
    configured_outputs_resolved=0
  fi
done
if [[ "${configured_outputs_resolved}" -eq 0 ]]; then
  echo "WARN: using fallback output root: ${FALLBACK_OUTPUT_ROOT}" >&2
  use_fallback_outputs
fi

if ! mkdir -p "${OUTPUT_PATH}" "${CUTS_OUTDIR}" "${DB_DIR}"; then
  if [[ "${OUTPUT_PATH}" != "${FALLBACK_OUTPUT_ROOT}/worldsar_output" || \
        "${CUTS_OUTDIR}" != "${FALLBACK_OUTPUT_ROOT}/tiles" || \
        "${DB_DIR}" != "${FALLBACK_OUTPUT_ROOT}/DB" ]]; then
    echo "WARN: configured output paths are not writable/valid. Falling back to ${FALLBACK_OUTPUT_ROOT}" >&2
    use_fallback_outputs
    mkdir -p "${OUTPUT_PATH}" "${CUTS_OUTDIR}" "${DB_DIR}"
  else
    echo "ERROR: failed to create fallback output directories under ${FALLBACK_OUTPUT_ROOT}" >&2
    exit 2
  fi
fi

if [[ -z "${GRID_HOST_DIR}" ]]; then
  GRID_HOST_DIR="${OUTPUT_PATH}/grid"
fi
mkdir -p "${GRID_HOST_DIR}"

CONTAINER_RUNTIME="${CONTAINER_RUNTIME:-apptainer}"
if ! command -v "${CONTAINER_RUNTIME}" >/dev/null 2>&1; then
  if [[ "${CONTAINER_RUNTIME}" == "apptainer" ]] && command -v singularity >/dev/null 2>&1; then
    echo "WARN: apptainer not found. Falling back to singularity." >&2
    CONTAINER_RUNTIME="singularity"
  else
    echo "ERROR: container runtime not found: ${CONTAINER_RUNTIME}" >&2
    if [[ "${CONTAINER_RUNTIME}" == "apptainer" ]]; then
      echo "ERROR: singularity also not found." >&2
    fi
    exit 2
  fi
fi

if ! "${CONTAINER_RUNTIME}" exec "${SIF_IMAGE}" bash -lc "[ -x \"${GPT_PATH}\" ] || command -v \"${GPT_PATH}\" >/dev/null 2>&1"; then
  if "${CONTAINER_RUNTIME}" exec "${SIF_IMAGE}" bash -lc "command -v gpt >/dev/null 2>&1"; then
    echo "WARN: GPT_PATH not found in container (${GPT_PATH}). Falling back to 'gpt' from PATH." >&2
    GPT_PATH="gpt"
  else
    echo "ERROR: GPT executable not found in container. Requested GPT_PATH=${GPT_PATH}" >&2
    exit 2
  fi
fi

echo "BASE_DIR=${BASE_DIR}"
echo "DATA_DIR=${DATA_DIR}"
echo "SCRIPT_DIR=${SCRIPT_DIR}"
echo "SIF_IMAGE=${SIF_IMAGE}"
echo "PROD_PATH=${PROD_PATH}"
echo "OUTPUT_PATH=${OUTPUT_PATH}"
echo "CUTS_OUTDIR=${CUTS_OUTDIR}"
echo "DB_DIR=${DB_DIR}"
echo "SNAP_USER_DIR=${SNAP_USER_DIR}"
echo "GRID_HOST_DIR=${GRID_HOST_DIR}"
echo "GRID_PATH=${GRID_PATH}"
echo "CONTAINER_RUNTIME=${CONTAINER_RUNTIME}"

# ---- Run ----
# apptainer run --writable-tmpfs \
"${CONTAINER_RUNTIME}" run \
  -B "${PY_SCRIPT_DIR}:${WORKSPACE_PREFIX}/scripts" \
  -B "${DATA_DIR}:${WORKSPACE_PREFIX}/data" \
  -B "${OUTPUT_PATH}:${WORKSPACE_PREFIX}/output" \
  -B "${CUTS_OUTDIR}:${WORKSPACE_PREFIX}/cuts" \
  -B "${DB_DIR}:${WORKSPACE_PREFIX}/db" \
  -B "${GRID_HOST_DIR}:${WORKSPACE_PREFIX}/grid" \
  -B "${SNAP_USER_DIR}:${WORKSPACE_PREFIX}/.snap" \
  "${SIF_IMAGE}" \
  python "${WORKSPACE_PREFIX}/scripts/worldsar.py" \
    --input "${WORKSPACE_PREFIX}/data/${PRODUCT_NAME}" \
    --output "${WORKSPACE_PREFIX}/output" \
    --cuts-outdir "${WORKSPACE_PREFIX}/cuts" \
    --gpt-path "${GPT_PATH}" \
    --grid-path "${GRID_PATH}" \
    --db-dir "${WORKSPACE_PREFIX}/db" \
    --gpt-memory "${GPT_MEMORY}" \
    --gpt-parallelism "${GPT_PARALLELISM}" \
    --gpt-timeout "${GPT_TIMEOUT}" 
