For running the WORLDSAR processing on the cluster, use the following command:


cd /lustre/projects/1001/rdelprete/logs && qsub /lustre/projects/1001/rdelprete/service/apptainer_worlsar.sh 


# Next steps:

1) Upload .snap with orbit files to HF support
2) Download .snap in WORLDSAR project folder
3) Bind mount .snap in apptainer_worlsar.sh at /workspace/.snap
4) Bnd mount the COPDEM and DEM files in apptainer_worlsar.sh at /workspace/.snap/auxdata/dem/'Copernicus 30m Global DEM'