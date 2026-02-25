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

DEFAULT_PRODUCT="${DEFAULT_PRODUCT:-S1C_IW_SLC__1SDV_20251024T155554_20251024T155621_004706_0094C5_A05A.SAFE}"
PROD_PATH="${PROD_PATH:-${DATA_DIR}/${DEFAULT_PRODUCT}}"
PRODUCT_NAME="$(basename "${PROD_PATH}")"

OUTPUT_PATH="${OUTPUT_PATH:-${BASE_DIR}/OUT/worldsar_output}"
CUTS_OUTDIR="${CUTS_OUTDIR:-${BASE_DIR}/OUT/tiles}"
DB_DIR="${DB_DIR:-${BASE_DIR}/OUT/DB}"
SNAP_USER_DIR="${SNAP_USER_DIR:-${BASE_DIR}/.snap}"
# ---- Parameters ----
GPT_MEMORY="${GPT_MEMORY:-64G}"
GPT_PARALLELISM="${GPT_PARALLELISM:-164}"
GPT_TIMEOUT="${GPT_TIMEOUT:-3600}"
WORKSPACE_PREFIX="${WORKSPACE_PREFIX:-/work}"
GPT_PATH="${GPT_PATH:-${WORKSPACE_PREFIX}/.snap/bin/gpt}"
GRID_PATH="${GRID_PATH:-${WORKSPACE_PREFIX}/grid/grid_10km.geojson}"

# ---- Basic validation ----
echo "BASE_DIR=${BASE_DIR}"
echo "DATA_DIR=${DATA_DIR}"
echo "SCRIPT_DIR=${SCRIPT_DIR}"
echo "SIF_IMAGE=${SIF_IMAGE}"
echo "PROD_PATH=${PROD_PATH}"
echo "OUTPUT_PATH=${OUTPUT_PATH}"
echo "CUTS_OUTDIR=${CUTS_OUTDIR}"
echo "DB_DIR=${DB_DIR}"
echo "SNAP_USER_DIR=${SNAP_USER_DIR}"

[[ -d "${DATA_DIR}" ]]     || { echo "ERROR: DATA_DIR not found: ${DATA_DIR}" >&2; exit 2; }
[[ -d "${PY_SCRIPT_DIR}" ]] || { echo "ERROR: PY_SCRIPT_DIR not found: ${PY_SCRIPT_DIR}" >&2; exit 2; }
[[ -f "${SIF_IMAGE}" ]]  || { echo "ERROR: SIF_IMAGE not found: ${SIF_IMAGE}" >&2; exit 2; }
[[ -d "${PROD_PATH}" ]]  || { echo "ERROR: PROD_PATH not found (SAFE dir): ${PROD_PATH}" >&2; exit 2; }
[[ -d "${SNAP_USER_DIR}" ]] || { echo "ERROR: SNAP_USER_DIR not found: ${SNAP_USER_DIR}" >&2; exit 2; }

mkdir -p "${OUTPUT_PATH}" "${CUTS_OUTDIR}" "${DB_DIR}"

# ---- Run ----
# apptainer run --writable-tmpfs \
apptainer run \
  -B "${PY_SCRIPT_DIR}:${WORKSPACE_PREFIX}/scripts" \
  -B "${DATA_DIR}:${WORKSPACE_PREFIX}/data" \
  -B "${OUTPUT_PATH}:${WORKSPACE_PREFIX}/output" \
  -B "${CUTS_OUTDIR}:${WORKSPACE_PREFIX}/cuts" \
  -B "${DB_DIR}:${WORKSPACE_PREFIX}/db" \
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
