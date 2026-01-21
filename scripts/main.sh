#!/bin/bash

PROD=$1
WKT=$2
# WKT='POLYGON ((32.633476 -26.831511, 32.865452 -25.984432, 30.373695 -25.393059, 30.122793 -26.234951, 32.633476 -26.831511))'

# TODO: define function for mode selection based on product name pattern. To be fixed later.
# e.g., if product name contains 'S1STRIP', set MODE='S1', etc. (S1C_S5_RAW__0SDH_20250419T054935_20250419T055001_001958_003E3F_5CF3.SAFE)
# e.g., if product name contains 'TSX', set MODE='TSX', etc. (TSX1_SAR__MGD_SE___SM_S_SRA_20220523T052620_20220523T052628)
# e.g., if product name contains 'BIOM', set MODE='BM', etc. 
MODE='S1TOPS' # [S1TOPS, S1STRIP, BM, TSX, NISAR, CSG]


#----------------------------------------------------------
# Load environment variables from .env file:
BASE_DIR="$(cd "$(dirname "$(dirname "$0")")" && pwd)"
if [ -f "${BASE_DIR}/.env" ]; then
        source "${BASE_DIR}/.env"
fi

#----------------------------------------------------------
clear
echo "======================================================================================================================="
echo " __        __   ___    ____   _       ____    ____      _      ____  "
echo " \\ \\      / /  / _ \\  |  _ \\ | |     |  _ \\  / ___|    / \\    |  _ \\ "
echo "  \\ \\ /\\ / /  | | | | | |_) || |     | | | | \\___ \\   / _ \\   | |_) |"
echo "   \\ V  V /   | |_| | |  _ < | |___  | |_| |  ___) | / ___ \\  |  _ < "
echo "    \\_/\\_/     \\___/  |_| \\_\\|_____| |____/  |____/ /_/   \\_\\ |_| \\_\\"
echo "======================================================================================================================="
echo "======================================         DATA PROCESSOR       ==================================================="
echo "======================================================================================================================="
echo ""
echo "Using virtual environment at: ${VENV_PATH}"
echo "Using GPT at: ${GPT_PATH}"
echo "Output directory: ${OUTPUT_DIR}"
echo "Output cuts directory: ${OUTPUT_CUTS_DIR}"
echo "Scripts directory: ${SCRIPTS_DIR}"
echo "DB directory: ${DB_DIR}"
echo "Bash dir: ${SCRIPTS_DIR}"
echo "Python scripts dir: ${PYSCRIPTS_DIR}"
echo "Product mode: ${MODE}"
echo "Upload repo: ${UPLOAD_REPO}"
echo "DB Upload repo: ${DB_UPLOAD_REPO}"
echo ""
echo "======================================================================================================================="


PYTHON="${VENV_PATH}/bin/python"
OUTPUT=$($PYTHON ${PYSCRIPTS_DIR}/main.py \
        --product_path "${PROD}" \
        --prod_mode "${MODE}" \
        --output_dir "${OUTPUT_DIR}" \
        --cuts_outdir "${OUTPUT_CUTS_DIR}" \
        --product_wkt "${WKT}")
echo "======================================          END PROCESSOR       ==================================================="
echo "======================================================================================================================="

if [ $? -eq 0 ]; then
    echo "Execution successful."
    echo "Output:"
    echo "$OUTPUT"
    # Upload to HF
    echo "======================================================================================================================="
    echo "======================================        UPLOADING              =================================================="
    echo "======================================================================================================================="
    source "${SCRIPTS_DIR}/utility/up.sh" "${UPLOAD_REPO}" "${OUTPUT_CUTS_DIR}"
    source "${SCRIPTS_DIR}/utility/up.sh" "${DB_UPLOAD_REPO}" "${DB_DIR}"
    echo "======================================================================================================================="
    echo "======================================        FINALISING              ==================================================="
    echo "======================================================================================================================="

else
    echo "Execution failed."
    echo "Output:"
    echo "$OUTPUT"
fi