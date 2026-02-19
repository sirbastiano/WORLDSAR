#!/bin/bash

INPUT=$1
OUTPUT=$2

qsub -N worldsar \
     -q cpu_std \
     -l walltime=00:45:00 \
     -l select=1:ncpus=192:mem=128g \
     << EOF
#!/bin/bash

source /lustre/projects/1001/rdelprete/service/service.sh
conda activate worldsar

sarpyx worldsar -i $INPUT \
                -o $OUTPUT \
                --product-wkt "POLYGON ((14.902315 40.806198, 15.325664 42.425392, 12.229127 42.824463, 11.885658 41.205784, 14.902315 40.806198))" \
                --prod-mode S1TOPS \
                --cuts-outdir /lustre/projects/1001/rdelprete/output_worldsar/TILES \
                --grid-path /lustre/projects/1001/rdelprete/srp/grid_10km.geojson \
                --db-dir /lustre/projects/1001/rdelprete/output_worldsar/DB \
                --gpt-path /lustre/home/u10010007/esa-snap/bin/gpt \
                --gpt-parallelism 190 \
                --gpt-memory 90G 

EOF

watch -n 1 qstat -u u10010007
