## Pre-requisites

```bash
#!/bin/bash

# Activate conda environment
source /lustre/projects/1001/miniconda3/bin/activate
conda activate esa-phisatnet

# Download WORLDSAR apptainer image
hf download WORLDSAR/support sarpyx.sif \
  --repo-type dataset \
  --local-dir /lustre/projects/1001/rdelprete/WORLDSAR
```

---

## Run WORLDSAR processing on the cluster

```bash
cd /lustre/projects/1001/rdelprete/logs && qsub /lustre/projects/1001/rdelprete/WORLDSAR/main.sh && watch -n 1 qstat -u u10010007
```

---

## Next steps

1. Upload the `.snap` folder (including orbit files) to HuggingFace `WORLDSAR/support`.
2. Download the `.snap` folder into:
   ```
   /lustre/projects/1001/rdelprete/WORLDSAR
   ```
3. Bind-mount `.snap` inside `apptainer_worlsar.sh` to:
   ```
   /workspace/.snap
   ```
4. Bind-mount COPDEM/DEM files inside `apptainer_worlsar.sh` to:
   ```
   /workspace/.snap/auxdata/dem/Copernicus 30m Global DEM
   ```
