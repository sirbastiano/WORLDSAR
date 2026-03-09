#!/usr/bin/env bash
set -euo pipefail

# Config
ENV_NAME="${ENV_NAME:-phidown}"   # cambia esto al nombre real de tu entorno
IN_DIR="${1:-/lustre/projects/1001/rdelprete/WORLDSAR/OUT/tiles}"
OUT_DIR="${2:-/lustre/projects/1001/rdelprete/WORLDSAR/OUT/srsd_patches}"
PATCH_SIZE="${PATCH_SIZE:-96}"
GROUP="${GROUP:-bands}"

LOG_DIR="${LOG_DIR:-${OUT_DIR%/}/logs}"
mkdir -p "$OUT_DIR" "$LOG_DIR"

TS="$(date +%Y%m%dT%H%M%S)"
LOG_FILE="${LOG_DIR}/prep_patches_${TS}.log"

# Limit BLAS thread explosion (critical on HPC)
export OPENBLAS_NUM_THREADS="${OPENBLAS_NUM_THREADS:-1}"
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-1}"
export MKL_NUM_THREADS="${MKL_NUM_THREADS:-1}"
export NUMEXPR_NUM_THREADS="${NUMEXPR_NUM_THREADS:-1}"
export VECLIB_MAXIMUM_THREADS="${VECLIB_MAXIMUM_THREADS:-1}"

# Activate conda robustly (same pattern you used)
source /lustre/projects/1001/miniconda3/bin/activate "$ENV_NAME"

# Sanity check: ensure python is from the env
PYBIN="$(command -v python3 || command -v python)"
if [[ -z "$PYBIN" ]]; then
  echo "ERROR: python not found after activating env: $ENV_NAME" | tee -a "$LOG_FILE" >&2
  exit 1
fi

{
  echo "IN_DIR    : $IN_DIR"
  echo "OUT_DIR   : $OUT_DIR"
  echo "PATCH_SIZE: $PATCH_SIZE"
  echo "GROUP     : $GROUP"
  echo "ENV_NAME  : $ENV_NAME"
  echo "PYTHON    : $PYBIN"
  echo "PYTHON_V  : $($PYBIN -V 2>&1)"
  echo "OPENBLAS_NUM_THREADS: $OPENBLAS_NUM_THREADS"
  echo "OMP_NUM_THREADS     : $OMP_NUM_THREADS"
  echo "LOG_FILE  : $LOG_FILE"
  echo ""
} | tee -a "$LOG_FILE"

CMD=( "$PYBIN" ./pyscripts/prep_patches_from_h5.py
  --in_dir "$IN_DIR"
  --out_dir "$OUT_DIR"
  --patch_size "$PATCH_SIZE"
  --group "$GROUP"
)

echo "Running:" | tee -a "$LOG_FILE"
printf '  %q' "${CMD[@]}" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

"${CMD[@]}" 2>&1 | tee -a "$LOG_FILE"