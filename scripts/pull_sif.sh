#!/bin/bash
# Activate conda environment
source /lustre/projects/1001/miniconda3/bin/activate
conda activate esa-phisatnet
hf download WORLDSAR/support sarpyx.sif --repo-type dataset --local-dir /lustre/projects/1001/rdelprete/WORLDSAR