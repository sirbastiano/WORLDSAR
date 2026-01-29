#!/bin/bash
# Quick launcher to open TSX-S1 stack visualizations in browser.
#
# Usage:
#     ./open_visuals.sh          # Opens index.html
#     ./open_visuals.sh heatmap  # Opens coverage heatmap
#     ./open_visuals.sh temporal # Opens temporal frequency map

cp /Users/roberto.delprete/Library/CloudStorage/OneDrive-ESA/Desktop/Repos/WORLDSAR/studies/WP2-Matching/TSX_S1/visuals/*.html /Users/roberto.delprete/Library/CloudStorage/OneDrive-ESA/Desktop/Repos/WORLDSAR/docs/

VISUALS_DIR="/Users/roberto.delprete/Library/CloudStorage/OneDrive-ESA/Desktop/Repos/WORLDSAR/studies/WP2-Matching/TSX_S1/visuals"

case "${1:-index}" in
    heatmap|heat|coverage)
        open "${VISUALS_DIR}/tsx_s1_stack_heatmap.html"
        echo "Opening coverage heatmap..."
        ;;
    temporal|frequency|time)
        open "${VISUALS_DIR}/tsx_s1_temporal_frequency.html"
        echo "Opening temporal frequency map..."
        ;;
    index|summary|stats|*)
        open "${VISUALS_DIR}/index.html"
        echo "Opening statistics summary..."
        ;;
esac

