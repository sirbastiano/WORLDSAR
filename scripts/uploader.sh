#!/bin/bash

source /lustre/projects/1001/miniconda3/bin/activate esa-phisatnet

hf upload-large-folder "WORLDSAR/S1Toy" /lustre/projects/1001/rdelprete/WORLDSAR/OUT/tiles/IW1/ --repo-type=dataset --num-workers 1 
hf upload "WORLDSAR/Database" /lustre/projects/1001/rdelprete/WORLDSAR/OUT/DB/ --repo-type=dataset