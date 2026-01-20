#!/bin/bash

PROD=$1
WKT=$2
# WKT='POLYGON ((32.633476 -26.831511, 32.865452 -25.984432, 30.373695 -25.393059, 30.122793 -26.234951, 32.633476 -26.831511))'

# TODO: define function for mode selection based on product name pattern. To be fixed later.
# e.g., if product name contains 'S1', set MODE='S1', etc.
# e.g., if product name contains 'TSX', set MODE='TSX', etc.
# e.g., if product name contains 'BIOM', set MODE='BM', etc.






MODE='TSX' # BM or S1 or TSX

# Load environment variables from .env file:
if [ -f .env ]; then
        export $(grep -v '^#' .env | xargs)
fi

# get filepath of current file 
CURRENT_FILE_PATH="$(realpath "$0")"
# go up one directory
BASE_DIR="$(dirname "$(dirname "$CURRENT_FILE_PATH")")"
# Scripts directory
SCRIPTS_DIR="${BASE_DIR}/pyscripts"

# Echoes 
# Pretty print environment details
echo "======================================================================================================================="
echo " __        __   ___    ____   _       ____    ____      _      ____  "
echo " \\ \\      / /  / _ \\  |  _ \\ | |     |  _ \\  / ___|    / \\    |  _ \\ "
echo "  \\ \\ /\\ / /  | | | | | |_) || |     | | | | \\___ \\   / _ \\   | |_) |"
echo "   \\ V  V /   | |_| | |  _ < | |___  | |_| |  ___) | / ___ \\  |  _ < "
echo "    \\_/\\_/     \\___/  |_| \\_\\|_____| |____/  |____/ /_/   \\_\\ |_| \\_\\"
echo "======================================================================================================================="
echo ""
echo "Using virtual environment at: ${venv_path}"
echo "Using GPT at: ${gpt_path}"
echo "Output directory: ${output_dir}"
echo "Output cuts directory: ${output_cuts_dir}"
echo "Scripts directory: ${SCRIPTS_DIR}"
echo "======================================================================================================================="



# PYTHON="${venv_path}/bin/python3"
# $PYTHON ${SCRIPTS_DIR}/main.py \
#         --product_path ${PROD} \
#         --prod_mode ${MODE} \
#         --output_dir ${output_dir} \
#         --cuts_outdir ${output_cuts_dir} \
#         --product_wkt ${WKT}