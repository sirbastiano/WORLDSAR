# WORLDSAR Guide

This guide is aligned with the current `Makefile` and `main.sh` in this repo.

## 1. Prerequisites

- Linux environment with `bash`
- `apptainer` (or compatible Singularity runtime)
- `hf` CLI (Hugging Face CLI)
- `curl`
- For cluster mode only: `qsub`/PBS commands available

## 2. Repository Setup

From repo root:

```bash
cd /shared/home/rdelprete/PythonProjects/AgenticWork/worldsar_guide/WORLDSAR
```

Optional Python environment setup:

```bash
uv sync
```

## 3. Required Runtime Assets

### 3.1 SIF container

Use one of:

```bash
make pull-sif
```

or (local `.tmp` cache mode):

```bash
make pull-sif-generic
```

### 3.2 SNAP userdir (`.snap`)

The Makefile now supports:

```bash
make pull-snap
```

This downloads:

- `https://huggingface.co/datasets/WORLDSAR/Support/resolve/main/snap_userdir.tar.gz`

Then extracts `.snap` into project root and cleans temporary download artifacts.

`make run` and `make run-vm` now automatically require and bootstrap `.snap` via `ensure-snap`.

### 3.3 DEM note

DEM needs to be downloaded only if you do not have internet access.
If internet is available at runtime, SNAP can fetch DEM data as needed.

## 4. Input Product

Put your `.SAFE` product under `./phidown_data`, or download with:

```bash
make down PRODUCT=<product_name>.SAFE
```

`PRODUCT` passed to `make run` / `make run-vm` can be either:

- the `.SAFE` directory name, or
- a full path to the `.SAFE` directory

`main.sh` normalizes it to the basename and resolves it under `./phidown_data`.

## 5. Running

### 5.1 Local VM run (no PBS)

```bash
make run-vm PRODUCT=<product_name>.SAFE
```

Example:

```bash
make run-vm PRODUCT=/shared/home/rdelprete/PythonProjects/AgenticWork/worldsar_guide/WORLDSAR/phidown_data/S1A_S3_SLC__1SDV_20151229T152825_20151229T152844_009258_00D5C6_F1C9.SAFE
```

### 5.2 Cluster run (PBS/qsub)

```bash
make run PRODUCT=<product_name>.SAFE
```

## 6. Monitoring and Logs

Cluster mode:

```bash
make status
make logs
```

## 7. Useful Cleanup

```bash
make clean
make clean-logs
make clean-snap-artifacts
```

`make clean-snap-artifacts` removes temporary SNAP download/extract files under `./.tmp/snap`.
