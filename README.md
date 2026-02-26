## Quick start (relative paths)

From repository root:

```bash
make pull-sif
make run PRODUCT=<product_name>           # VM (default)
```

Optional custom overrides:

```bash
WORLDSAR_MODE=hpc make run PRODUCT=<product_name_or_path> \
  WORLDSAR_MODE=hpc SIF_IMAGE=./cache/sarpyx.sif MAIN_SCRIPT=main.sh LOG_DIR=./logs PBS_USER=$USER
```

- Local VM mode: `make run PRODUCT=<product_name_or_path>` (default mode)
- Cluster mode: `WORLDSAR_MODE=hpc make run PRODUCT=<product_name_or_path>`

### Manual alternatives

Download SIF image:

```bash
bash scripts/pull_sif.sh
```

Download support assets:

```bash
bash scripts/down_orb.sh
```

Download a product by name:

```bash
make down PRODUCT=S1A_IW_SLC__...
```

### Queue helpers

```bash
make status
make logs
```

### Upload outputs

```bash
bash scripts/uploader.sh
```

### Notes

- The `.snap` folder should be available in the repository root (or configured via `SNAP_USER_DIR` in `main.sh`/`Makefile` flows).
- `main.sh` and `scripts/worldsar_inline.sh` now use repository-relative defaults and overridable environment variables.
