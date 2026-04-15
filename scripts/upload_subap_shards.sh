#!/usr/bin/env bash
set -euo pipefail

OUTPUT_ROOT="${OUTPUT_ROOT:-/lustre/scratch/1001/rdelprete/srsd_patches/dataset_sm_subaps_sharded}"
HF_REPO="${HF_REPO:-juanfra54/subaps_s1sm_x96}"
HF_NUM_WORKERS="${HF_NUM_WORKERS:-1}"
HF_EXTRA_ARGS="${HF_EXTRA_ARGS:-}"

if [[ ! -d "${OUTPUT_ROOT}" ]]; then
  echo "ERROR: sharded dataset directory not found: ${OUTPUT_ROOT}" >&2
  echo "Run the PBS sharding job first on a compute node." >&2
  exit 1
fi

hf upload-large-folder "${HF_REPO}" "${OUTPUT_ROOT}" \
  --repo-type dataset \
  --num-workers "${HF_NUM_WORKERS}" \
  ${HF_EXTRA_ARGS}
