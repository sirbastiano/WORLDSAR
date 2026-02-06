#!/bin/bash
source /shared/home/rdelprete/PythonProjects/WORLDSAR/srp/.venv/bin/activate

sarpyx worldsar -i /shared/home/rdelprete/PythonProjects/WORLDSAR/data/1_data/S1TOPS/S1C_IW_SLC__1SDV_20260131T051056_20260131T051123_006143_00C543_3B00.SAFE \
                -o /shared/home/rdelprete/PythonProjects/WORLDSAR/data/2_processed \
                --cuts-outdir /shared/home/rdelprete/PythonProjects/WORLDSAR/data/3_cuts \
                --prod-mode S1TOPS \
                --gpt-path /shared/home/rdelprete/esa-snap/bin/gpt \
                --grid-path /shared/home/rdelprete/PythonProjects/WORLDSAR/support/grid_10km.geojson \
                --db-dir /shared/home/rdelprete/PythonProjects/WORLDSAR/data/DB \
                --product-wkt "POLYGON ((14.902315 40.806198, 15.325664 42.425392, 12.229127 42.824463, 11.885658 41.205784, 14.902315 40.806198))"