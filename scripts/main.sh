#!/bin/bash

PROD='/Data_large/SARGFM/data/1_data/BIOMASS/bio_s3_dgm__1s_20251106t221201_20251106t221221_c_g___m___c___t____f159_lut.nc'
MODE='BIOMASS'



PYTHON="/Data_large/SARGFM/srp/.venv/bin/python3"
$PYTHON /Data_large/SARGFM/pyscripts/main.py \
        --product_path ${PROD} \
        --prod_mode ${MODE} \
        --output_dir /Data_large/SARGFM/data/2_processed \
        --cuts_outdir /Data_large/SARGFM/data/3_cuts \
        --product_wkt 'POLYGON ((32.633476 -26.831511, 32.865452 -25.984432, 30.373695 -25.393059, 30.122793 -26.234951, 32.633476 -26.831511))'