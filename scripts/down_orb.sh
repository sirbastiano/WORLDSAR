#!/bin/bash
source /lustre/projects/1001/miniconda3/bin/activate esa-phisatnet

# Ensure the target directory exists
mkdir -p /lustre/projects/1001/rdelprete/WORLDSAR/.snap/PEORB

# Change to the WORLDSAR directory
cd /lustre/projects/1001/rdelprete/WORLDSAR

hf download WORLDSAR/Support "snap_userdir.tar.gz" --repo-type dataset --local-dir /lustre/projects/1001/rdelprete/WORLDSAR  --token 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
