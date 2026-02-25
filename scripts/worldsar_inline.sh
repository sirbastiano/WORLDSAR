#!/bin/bash
set -euo pipefail

INPUT="${1:-}"
OUTPUT="${2:-}"

if [ -z "${INPUT}" ] || [ -z "${OUTPUT}" ]; then
	echo "Usage: $0 <input_product> <output_base_dir>"
	exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
PROJECT_DIR="${PROJECT_DIR:-$(cd "${SCRIPT_DIR}/.." && pwd -P)}"
SOURCE_SCRIPT="${SOURCE_SCRIPT:-${PROJECT_DIR}/service/service.sh}"
CONDA_ENV="${CONDA_ENV:-worldsar}"
TILES_OUTDIR="${TILES_OUTDIR:-${PROJECT_DIR}/output_worldsar/TILES}"
DB_DIR="${DB_DIR:-${PROJECT_DIR}/output_worldsar/DB}"
GRID_PATH="${GRID_PATH:-${PROJECT_DIR}/srp/grid_10km.geojson}"
GPT_PATH="${GPT_PATH:-${PROJECT_DIR}/.snap/bin/gpt}"
SCHED_USER="${SCHED_USER:-${USER}}"
QSUB_QUEUE="${QSUB_QUEUE:-cpu_std}"
MEM_GB="${MEM_GB:-128g}"
NCPUS="${NCPUS:-192}"
WALLTIME="${WALLTIME:-00:45:00}"
PARALLELISM="${PARALLELISM:-190}"
MEMORY="${MEMORY:-90G}"

if [ ! -f "${SOURCE_SCRIPT}" ]; then
	echo "ERROR: source script not found: ${SOURCE_SCRIPT}" >&2
	exit 2
fi

qsub -N worldsar \
     -q "${QSUB_QUEUE}" \
     -l walltime="${WALLTIME}" \
     -l select=1:ncpus="${NCPUS}":mem="${MEM_GB}" \
     << EOF
#!/bin/bash

source "${SOURCE_SCRIPT}"
conda activate "${CONDA_ENV}"

sarpyx worldsar -i "$INPUT" \
                -o "$OUTPUT" \
                --product-wkt "POLYGON ((14.902315 40.806198, 15.325664 42.425392, 12.229127 42.824463, 11.885658 41.205784, 14.902315 40.806198))" \
                --prod-mode S1TOPS \
                --cuts-outdir "${TILES_OUTDIR}" \
                --grid-path "${GRID_PATH}" \
                --db-dir "${DB_DIR}" \
                --gpt-path "${GPT_PATH}" \
                --gpt-parallelism "${PARALLELISM}" \
                --gpt-memory "${MEMORY}" 

EOF

watch -n 1 qstat -u "${SCHED_USER}"
