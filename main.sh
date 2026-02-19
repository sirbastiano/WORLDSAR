#!/bin/bash
#PBS -N worldsar
#PBS -q cpu_std
#PBS -l walltime=12:00:00
#PBS -l select=1:ncpus=192:mem=384g

set -euo pipefail

# ---- Paths (edit if needed) ----
BASE_DIR="/lustre/projects/1001/rdelprete/WORLDSAR"
DATA_DIR="${BASE_DIR}/phidown_data"
SCRIPT_DIR="${BASE_DIR}/pyscripts"
SIF_IMAGE="${BASE_DIR}/sarpyx.sif"

PROD_PATH="${DATA_DIR}/S1A_S3_SLC__1SDV_20160820T171616_20160820T171644_012687_013EFB_B6D5.SAFE"
PRODUCT_NAME="$(basename "${PROD_PATH}")"

OUTPUT_PATH="/lustre/scratch/1001/rdelprete/worldsar_output"
CUTS_OUTDIR="/lustre/scratch/1001/rdelprete/tiles"
DB_DIR="/lustre/scratch/1001/rdelprete/DB"
SNAP_USER_DIR="/lustre/projects/1001/rdelprete/WORLDSAR/.snap"
# ---- Parameters ----
GPT_MEMORY="64G"
GPT_PARALLELISM="164"
GPT_TIMEOUT="3600"

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

[[ -d "${DATA_DIR}" ]]   || { echo "ERROR: DATA_DIR not found: ${DATA_DIR}" >&2; exit 2; }
[[ -d "${SCRIPT_DIR}" ]] || { echo "ERROR: SCRIPT_DIR not found: ${SCRIPT_DIR}" >&2; exit 2; }
[[ -f "${SIF_IMAGE}" ]]  || { echo "ERROR: SIF_IMAGE not found: ${SIF_IMAGE}" >&2; exit 2; }
[[ -d "${PROD_PATH}" ]]  || { echo "ERROR: PROD_PATH not found (SAFE dir): ${PROD_PATH}" >&2; exit 2; }
[[ -d "${SNAP_USER_DIR}" ]] || { echo "ERROR: SNAP_USER_DIR not found: ${SNAP_USER_DIR}" >&2; exit 2; }

mkdir -p "${OUTPUT_PATH}" "${CUTS_OUTDIR}" "${DB_DIR}"

# ---- Run ----
apptainer run --writable-tmpfs \
  -B "${SCRIPT_DIR}:/workspace/scripts" \
  -B "${DATA_DIR}:/workspace/data" \
  -B "${OUTPUT_PATH}:/workspace/output" \
  -B "${CUTS_OUTDIR}:/workspace/cuts" \
  -B "${DB_DIR}:/workspace/db" \
  -B "${SNAP_USER_DIR}:/workspace/.snap" \
  "${SIF_IMAGE}" \
  python /workspace/scripts/worldsar.py \
    --input "/workspace/data/${PRODUCT_NAME}" \
    --output "/workspace/output" \
    --cuts-outdir "/workspace/cuts" \
    --gpt-path "/workspace/snap12/bin/gpt" \
    --grid-path "/workspace/grid/grid_10km.geojson" \
    --db-dir "/workspace/db" \
    --gpt-memory "${GPT_MEMORY}" \
    --gpt-parallelism "${GPT_PARALLELISM}" \
    --gpt-timeout "${GPT_TIMEOUT}"