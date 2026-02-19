#!/bin/bash
source /lustre/projects/1001/miniconda3/bin/activate phidown


python -m phidown --name "$1" -o /lustre/projects/1001/rdelprete/WORLDSAR/phidown_data/ -c /lustre/projects/1001/rdelprete/service/.s5cfg