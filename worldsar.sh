#!/bin/bash
source /shared/home/rdelprete/PythonProjects/WORLDSAR/srp/.venv/bin/activate

sarpyx worldsar -i /shared/home/rdelprete/PythonProjects/WORLDSAR/data/1_data/S1TOPS/S1A_IW_SLC__1SDV_20240503T031928_20240503T031942_053701_0685FB_670F.SAFE \
                -o /shared/home/rdelprete/PythonProjects/WORLDSAR/data/2_processed \
                --cuts-outdir /shared/home/rdelprete/PythonProjects/WORLDSAR/data/3_cuts \
                --prod-mode S1TOPS \
                --gpt-path /shared/home/rdelprete/esa-snap/bin/gpt \
                --grid-path /shared/home/rdelprete/PythonProjects/WORLDSAR/support/grid_10km.geojson \
                --db-dir /shared/home/rdelprete/PythonProjects/WORLDSAR/data/DB \
                --product-wkt "POLYGON ((32.633476 -26.831511, 32.865452 -25.984432, 30.373695 -25.393059, 30.122793 -26.234951, 32.633476 -26.831511))"