#!/bin/bash

PYTHON="/Data_large/SARGFM/srp/.venv/bin/python3"
$PYTHON /Data_large/SARGFM/pyscripts/main.py \
        --product_path /Data_large/SARGFM/data/1_data/S1A_IW_SLC__1SDV_20240503T031928_20240503T031942_053701_0685FB_670F.SAFE \
        --output_dir /Data_large/SARGFM/data/2_processed \
        --cuts_outdir /Data_large/SARGFM/data/3_cuts \
        --product_wkt 'POLYGON ((32.633476 -26.831511, 32.865452 -25.984432, 30.373695 -25.393059, 30.122793 -26.234951, 32.633476 -26.831511))'