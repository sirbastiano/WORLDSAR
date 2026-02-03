#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

VENV_PATH="${VENV_PATH:-/Users/roberto.delprete/Library/CloudStorage/OneDrive-ESA/Desktop/Repos/WORLDSAR/srp/.venv}"
SPATIAL_THRESHOLD=0.5
THRESHOLD_DAYS=160
S1_MODE=IW
S1_PRODUCT_TYPE=SLC
OVERLAP_THRESHOLD=0.5
MIN_PRODUCTS=1
MIN_DAYS=100

DB_PATH=""
OUTPUT_PATH=""
OUTPUT_DIR=""
DELIVERABLE_DIR=""
STACK_DIR=""
VISUALS_DIR=""
PUBLISH_DIR=""
UPDATE_PORTAL=0
SKIP_STEP0=0

usage() {
  cat <<'EOF'
Usage: ./run.sh [options]

Options:
  --venv PATH               Path to venv (default: srp/.venv)
  --spatial-threshold VAL   Step 1 spatial overlap threshold (default: 0.5)
  --threshold-days N        Step 1 temporal window in days (default: 60)
  --s1-mode MODE            Step 1 Sentinel-1 mode (default: IW)
  --s1-product-type TYPE    Step 1 product type (default: SLC)
  --db-path PATH            Step 1 NISAR CSV path (optional)
  --output-path PATH        Step 1 output parquet path (optional)

  --overlap-threshold VAL   Step 2 overlap threshold (default: 0.5)
  --min-products N          Step 2 min products per stack (default: 1)
  --min-days N              Step 2 min temporal span in days (default: 3)
  --output-dir PATH         Step 2 stack CSV output dir (optional)
  --deliverable-dir PATH    Step 2 deliverable dir (optional)

  --stack-dir PATH          Step 3 input stack dir (optional)
  --visuals-dir PATH        Step 3 output visuals dir (optional)
  --publish-dir PATH        Step 3 publish dir (optional)
  --update-portal           Step 3 update docs portal index (optional)

  --skip-step0              Skip NISAR catalog retrieval
  -h, --help                Show this help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --venv) VENV_PATH="$2"; shift 2 ;;
    --spatial-threshold) SPATIAL_THRESHOLD="$2"; shift 2 ;;
    --threshold-days) THRESHOLD_DAYS="$2"; shift 2 ;;
    --s1-mode) S1_MODE="$2"; shift 2 ;;
    --s1-product-type) S1_PRODUCT_TYPE="$2"; shift 2 ;;
    --db-path) DB_PATH="$2"; shift 2 ;;
    --output-path) OUTPUT_PATH="$2"; shift 2 ;;
    --overlap-threshold) OVERLAP_THRESHOLD="$2"; shift 2 ;;
    --min-products) MIN_PRODUCTS="$2"; shift 2 ;;
    --min-days) MIN_DAYS="$2"; shift 2 ;;
    --output-dir) OUTPUT_DIR="$2"; shift 2 ;;
    --deliverable-dir) DELIVERABLE_DIR="$2"; shift 2 ;;
    --stack-dir) STACK_DIR="$2"; shift 2 ;;
    --visuals-dir) VISUALS_DIR="$2"; shift 2 ;;
    --publish-dir) PUBLISH_DIR="$2"; shift 2 ;;
    --update-portal) UPDATE_PORTAL=1; shift ;;
    --skip-step0) SKIP_STEP0=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage; exit 1 ;;
  esac
done

if [[ ! -f "${VENV_PATH}/bin/activate" ]]; then
  echo "Venv not found at ${VENV_PATH}. Use --venv to set the correct path." >&2
  exit 1
fi

source "${VENV_PATH}/bin/activate"

cd "${SCRIPT_DIR}"

if [[ "${SKIP_STEP0}" -eq 0 ]]; then
  echo "Step 0: Retrieve NISAR products"
  python 0_retrieve_NISAR_products.py
else
  echo "Step 0: Skipped"
fi

echo "Step 1: Search for Sentinel-1 matches"
step1_cmd=(python 1_search_matches.py
  --spatial-threshold "${SPATIAL_THRESHOLD}"
  --threshold-days "${THRESHOLD_DAYS}"
  --s1-mode "${S1_MODE}"
  --s1-product-type "${S1_PRODUCT_TYPE}"
)
if [[ -n "${DB_PATH}" ]]; then
  step1_cmd+=(--db-path "${DB_PATH}")
fi
if [[ -n "${OUTPUT_PATH}" ]]; then
  step1_cmd+=(--output-path "${OUTPUT_PATH}")
fi
"${step1_cmd[@]}"

echo "Step 2: Build temporal stacks"
step2_cmd=(python 2_build_stacks.py
  --overlap-threshold "${OVERLAP_THRESHOLD}"
  --min-products "${MIN_PRODUCTS}"
  --min-days "${MIN_DAYS}"
)
if [[ -n "${OUTPUT_DIR}" ]]; then
  step2_cmd+=(--output-dir "${OUTPUT_DIR}")
fi
if [[ -n "${DELIVERABLE_DIR}" ]]; then
  step2_cmd+=(--deliverable-dir "${DELIVERABLE_DIR}")
fi
"${step2_cmd[@]}"

echo "Step 3: Visualize stacks"
step3_cmd=(python 3_visualize.py)
if [[ -n "${STACK_DIR}" ]]; then
  step3_cmd+=(--stack-dir "${STACK_DIR}")
fi
if [[ -n "${VISUALS_DIR}" ]]; then
  step3_cmd+=(--visuals-dir "${VISUALS_DIR}")
fi
if [[ -n "${PUBLISH_DIR}" ]]; then
  step3_cmd+=(--publish-dir "${PUBLISH_DIR}")
fi
if [[ "${UPDATE_PORTAL}" -eq 1 ]]; then
  step3_cmd+=(--update-portal)
fi
"${step3_cmd[@]}"

echo "Done."
