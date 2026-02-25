# WORLDSAR Processor Guide (single-image, Makefile-focused)

This guide reflects the current repo structure and focuses on running one SAR scene with the least indirection.

## Current entrypoint used in this branch

Use:

- `pyscripts/worldsar.py` (current CLI)
- `main.sh` (PBS wrapper, cluster-oriented)
- `scripts/worldsar_inline.sh` (legacy wrapper, still PBS-oriented)

## What `worldsar.py` does for one image

For a single product it:

1. Infers mission mode (`S1TOPS`, `S1STRIP`, `TSX`, `CSG`, `BM`, `NISAR`) from filename.
2. Runs mission preprocessing with SNAP GPT.
3. Cuts tiles from the processed product with your grid polygon.
4. Builds tile metadata in a parquet file under DB output.

## New files you should know in this repo

- `scripts/pull_sif.sh` downloads the Apptainer/Singularity image (legacy helper).
- `scripts/down_orb.sh` downloads `.snap` support assets from HF.
- `Makefile` has convenience commands and now checks for the SIF image on `make run`.
- `.snap` is required for SNAP runtime assets (orbits, DEM caches, etc.).

## Required runtime files

From Hugging Face:

- `WORLDSAR/Support` includes `.snap` assets
  - orbit files (used by Apply-Orbit-File)
  - optional additional support files depending on your setup
  - URL: `https://huggingface.co/datasets/WORLDSAR/Support/tree/main`

Before running, download into a local folder and mount it as `<container_root>/.snap` inside the container.

## Minimum arguments you must provide (inside container)

You will pass these to `worldsar.py` directly:

- `--input <container_root>/input/<PRODUCT>`
- `--output <container_root>/output`
- `--cuts-outdir <container_root>/cuts`
- `--gpt-path <container_root>/.snap/bin/gpt`
- `--grid-path <container_root>/grid.geojson`
- `--db-dir <container_root>/db`
- `--snap-userdir <container_root>/.snap`

Optional but recommended:

- `--product-wkt "POLYGON (...)"`
  - required for non-Sentinel-1 inputs
  - for Sentinel-1, CLI can often infer it automatically
- `--gpt-memory 16G` (or higher)
- `--gpt-parallelism 8` (tune based on CPUs)
- `--gpt-timeout 3600`

## Makefile workflow (cluster-first)

Run commands from repo root.

1. Pull the SIF image (or let `make run` do it):

```bash
make pull-sif
```

2. Run and submit the job:

```bash
make run
```

`make run` behavior:

- Checks `$(SIF_IMAGE)` and downloads it if missing.
- Submits `main.sh` via `qsub`.

You can override defaults directly from CLI:

```bash
make run \
  SIF_IMAGE=./cache/sarpyx.sif \
  MAIN_SCRIPT=main.sh \
  LOG_DIR=./logs \
  PBS_USER=$USER
```

3. Monitor the queue/logs:

```bash
make status
make logs
```

4. Download products:

```bash
make down PRODUCT=S1A_IW_SLC__...
```

5. Cleanup:

```bash
make clean
make clean-logs
```

## No-PBS single-image reference run

If you need a manual local flow, keep paths relative:

```bash
export PROJECT_DIR=.
export INPUT_DIR=./data
export INPUT_NAME=YOUR_PRODUCT.SAFE   # e.g. S1C_IW_SLC__... .SAFE directory
export SIF_IMAGE=./sarpyx.sif
export SNAP_HOME=./.snap
export GRID_HOST=./grid_10km.geojson
export OUTPUT_DIR=./output/processed
export CUTS_DIR=./output/cuts
export DB_DIR=./output/db
export WORKDIR=/work

mkdir -p "$OUTPUT_DIR" "$CUTS_DIR" "$DB_DIR"

apptainer exec \
  --bind "$PROJECT_DIR:$WORKDIR/WORLDSAR" \
  --bind "$SNAP_HOME:$WORKDIR/.snap" \
  --bind "$GRID_HOST:$WORKDIR/grid.geojson:ro" \
  --bind "$INPUT_DIR:$WORKDIR/input:ro" \
  --bind "$OUTPUT_DIR:$WORKDIR/output" \
  --bind "$CUTS_DIR:$WORKDIR/cuts" \
  --bind "$DB_DIR:$WORKDIR/db" \
  "$SIF_IMAGE" \
  python "$WORKDIR/WORLDSAR/pyscripts/worldsar.py" \
    --input "$WORKDIR/input/$INPUT_NAME" \
    --output "$WORKDIR/output" \
    --cuts-outdir "$WORKDIR/cuts" \
    --gpt-path "$WORKDIR/.snap/bin/gpt" \
    --grid-path "$WORKDIR/grid.geojson" \
    --db-dir "$WORKDIR/db" \
    --snap-userdir "$WORKDIR/.snap" \
    --gpt-memory 16G \
    --gpt-parallelism 8 \
    --gpt-timeout 3600 \
    --product-wkt "POLYGON ((14.9 40.8, 15.3 42.4, 12.2 42.8, 11.9 41.2, 14.9 40.8))"
```

For Sentinel-1 you can usually remove `--product-wkt` and let `worldsar.py` extract it from metadata.

## Quick output checklist

After success:

- `OUTPUT_DIR` gets intermediate processed files (BEAM-DIMAP / GeoTIFF depending on mode).
- `CUTS_DIR/<product_id>/` contains one `.h5` file per tile.
- `DB_DIR` contains a parquet metadata table.

For `S1TOPS`, cutting is done per swath (`IW1`, `IW2`, `IW3`) under the cuts root.

## Legacy wrappers and why this guide uses direct call

- `main.sh` and `scripts/worldsar_inline.sh` are present and keep legacy wrappers, but their settings are now configurable.
- Running `pyscripts/worldsar.py` directly is safer and clearer for one-image, local testing.
- If you later move back to cluster mode, tune `main.sh` inputs and paths to match your environment.
