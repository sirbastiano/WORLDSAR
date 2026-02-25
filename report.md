# Smoke Test Report: `make run-vm`

- Timestamp: `2026-02-25T18:49:43+00:00`
- Workspace: `/shared/home/rdelprete/PythonProjects/AgenticWork/worldsar_guide/WORLDSAR`
- Product tested: `/shared/home/rdelprete/PythonProjects/AgenticWork/worldsar_guide/WORLDSAR/phidown_data/S1A_S3_SLC__1SDV_20151229T152825_20151229T152844_009258_00D5C6_F1C9.SAFE`

## Command executed

```bash
make run-vm PRODUCT="/shared/home/rdelprete/PythonProjects/AgenticWork/worldsar_guide/WORLDSAR/phidown_data/S1A_S3_SLC__1SDV_20151229T152825_20151229T152844_009258_00D5C6_F1C9.SAFE"
```

## Outcome

Smoke test failed before processing began.

Observed terminal errors:

```text
mkdir: cannot create directory ‘./OUT/worldsar_output’: File exists
mkdir: cannot create directory ‘./OUT/tiles’: File exists
mkdir: cannot create directory ‘./OUT/DB’: File exists
make: *** [Makefile:99: run-vm] Error 1
```

## What failed (root cause)

- Failure occurs in `main.sh:56`, at:

```bash
mkdir -p "${OUTPUT_PATH}" "${CUTS_OUTDIR}" "${DB_DIR}"
```

- `OUT/worldsar_output`, `OUT/tiles`, and `OUT/DB` are symbolic links.
- Their targets are missing:
  - `/lustre/scratch/1001/rdelprete/worldsar_output`
  - `/lustre/scratch/1001/rdelprete/tiles`
  - `/lustre/scratch/1001/rdelprete/DB`
- Because these are broken symlinks (not valid directories), `mkdir -p` fails with `File exists`.

## Additional potential blocker

- `apptainer` is not available in this runtime (`apptainer: command not found`).
- This would likely cause the next failure after directory/symlink issues are resolved, because `main.sh` invokes `apptainer run` at `main.sh:60`.

## Notes

- Product discovery/validation reached the expected `.SAFE` directory path before failing, so the supplied product path itself was accepted.
- No code or configuration changes were applied; this report is observational only.
