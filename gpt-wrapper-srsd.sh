#!/bin/bash
set -euo pipefail

apptainer exec \
  -B /lustre/projects/1001/rdelprete:/lustre/projects/1001/rdelprete \
  -B /lustre/scratch/1001/rdelprete:/lustre/scratch/1001/rdelprete \
  /lustre/projects/1001/rdelprete/WORLDSAR/sarpyx.sif \
  /usr/local/bin/gpt "$@"
