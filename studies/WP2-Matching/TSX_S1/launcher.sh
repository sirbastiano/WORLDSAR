#!/bin/bash

# Launcher script for TSX-S1 matching search
# This script calls the search_tsx_s1_matches.py with configured parameters



SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_SCRIPT="${SCRIPT_DIR}/search_tsx_s1_matches.py"

# Check if script exists
if [ ! -f "$PYTHON_SCRIPT" ]; then
    echo "Error: Python script not found at ${PYTHON_SCRIPT}"
    exit 1
fi

# Run the search with specified parameters
python /Users/roberto.delprete/Library/CloudStorage/OneDrive-ESA/Desktop/Repos/WORLDSAR/studies/WP2/search_tsx_s1_matches.py \
    --db-path "/Users/roberto.delprete/Library/CloudStorage/OneDrive-ESA/Desktop/Repos/WORLDSAR/DB/footprints_TSX/TSX_TSM_SSC_archive_index.csv" \
    --output-path "/Users/roberto.delprete/Library/CloudStorage/OneDrive-ESA/Desktop/Repos/WORLDSAR/DB/output_tsx_s1/tsx_s1_EW_matches.parquet" \
    --spatial-threshold 0.85 \
    --threshold-days 7 \
    --chunk-size 500

echo "Search completed successfully!"