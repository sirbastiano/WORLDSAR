

# WorldSAR
![WorldSAR](WorldSAR.png)
> High‑resolution, terrestrial‑scale intelligence derived from SAR acquisitions. WorldSAR is the geospatial force multiplier that links ESA Sentinel-1, TerraSAR-X, BIOMASS, and other SAR archives to detection, masking, and analytics workflows.

## Contents
- [Highlights](#highlights)
- [Architecture](#architecture)
- [Getting started](#getting-started)
- [Configuration & data access](#configuration--data-access)
- [Workflow examples](#workflow-examples)
- [Directory overview](#directory-overview)
- [Contributing](#contributing)
- [License](#license)

## Highlights
- **Unified SAR engine:** `sarpyx.snap.engine.GPT` wraps SNAP GPT binaries (40+ formats) with sensible defaults for Sentinel-1, COSMO-SkyMed, and mixed missions.
- **Operational-ready preprocessing:** Chains include debursting, calibration, multilooking, masking, thresholding, and bespoke object discrimination (CFAR) for maritime use cases.
- **Ship detection pipeline:** High-level routines orchestrate land masking plus adaptive thresholding and exports detections to CSV/Excel for rapid exploitation.
- **Tooling for automation:** Ready-to-use installers (`scripts/snap_installer`) and data preparation scripts let you spin up environments or iterate on experiments quickly.
- **Extensible stack:** Python notebooks, supporting scripts, and the SRP helper repo keep workflows modular and future contributions focused.

## Architecture
1. **Inference core (`sarpyx/snap/engine.py`):** Exposes PTO operations (calibration, multilook, subset, etc.) through class methods that update the internal product path for chaining.
2. **High-level CFAR helper:** Simplifies threshold sweeps and exports while enforcing cleanup of intermediate SNAP products when desired.
3. **Data acquisition & utilities:** Wrapper scripts around `phidown` (see `.s5cfg` template) and installer helpers for SNAP/GPT binaries ensure reproducible environments.
4. **Supporting notebooks & scripts:** Located under `notebooks`, `pyscripts`, and `scripts`, these demonstrate batch processing, ROI extraction, and automation scaffolds.

## Getting started
1. Clone this repository and the SRP helper (used for dependency management):
   ```bash
   git clone https://github.com/sirbastiano/WORLDSAR.git
   git clone https://github.com/sirbastiano/srp.git
   ```
2. Install SRP dependencies:
   ```bash
   cd srp
   pip install pdm
   pdm install
   ```
3. Install SNAP/GPT (see `scripts/snap_installer/install.sh` and [`snap.varfile`](scripts/snap_installer/snap.varfile) for expectations on locales, memory, and install path).
4. Return to this repo and start injecting SAR products into `WorldSAR` pipelines (e.g., place SAFE products inside `data/` or pass explicit paths to the `GPT` wrapper).

## Configuration & data access
- **`.s5cfg` (Phidown):** Create the file in your home directory to enable downloads. Replace placeholders with CDSE credentials.
  ```ini
  [default]
  aws_access_key_id = <your key>
  aws_secret_access_key = <your secret>
  aws_region = eu-central-1
  host_base = eodata.dataspace.copernicus.eu
  host_bucket = eodata.dataspace.copernicus.eu
  use_https = true
  check_ssl_certificate = true
  ```
- **AWS access:** Use CDSE portal to retrieve Sentinel-1 archives and feed them directly to the pipelines described below.
- **GPT path:** Override via `GPT(..., gpt_path='/path/to/gpt')` if automatic discovery fails.

## Workflow examples
1. **Preprocess Sentinel-1 for ship detection**
   - Deburst → Calibration → Import vector mask → Apply land mask → Adaptive thresholding → Object discrimination.
   - Exported product paths are returned from each method, enabling custom logging or cleanup (`sarpyx.utils.io.delProd`).
2. **Sweep CFAR thresholds**
   - Call the `CFAR` helper with multiple `Thresh` values to generate per-threshold Excel outputs and visualize detection sensitivity.
3. **Batch & ROI processing**
   - Iterate over products in `data/`, apply consistent chains, and subset ROIs with fixed window sizes (`Subset` with pixel or geographic coordinates).
4. **Advanced formats**
   - Switch `format='GeoTIFF'` or `format='BEAM-DIMAP'` in the `GPT` constructor to produce outputs that easily feed into downstream analytics.

See `docs/Snapflow_usage_example.md` for complete code snippets with chaining, error handling, and best practices.

## Directory overview
- `data/`: Sample/Sentinel data directories (create symbolic links or mount your archive here).
- `docs/`: Extended usage guides (Snapflow, examples, troubleshooting).
- `notebooks/` & `pyscripts/`: Jupyter notebooks and auxiliary scripts for experimentation and automation.
- `scripts/snap_installer/`: Installer helper that prepares SNAP/GPT prerequisites.
- `snap/`, `snap13/`: Reference SNAP binary bundles (do not edit; verify compatibility before upgrades).
- `srp/`: External skill repository used for dependency management.
- `support/`: Operational notes, templates, or helper files referenced by engineers in the loop.

## Contributing
WorldSAR thrives on domain expertise. Please:
1. Open issues for new datasets, feature requests, or unclear behavior.
2. Follow existing code patterns (class-based wrappers around SNAP operations).
3. Provide notebooks or script adjustments that keep pipelines reproducible.
4. Document any configuration changes in this README or the relevant `docs/` entry.

## License
WorldSAR is managed by the upstream maintainers; please follow the LICENSE file if present or consult the repository steward before redistribution.
