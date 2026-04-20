# s2_alignment.py

Standalone Sentinel-2 alignment script: search, download, and crop S2 products onto a fixed-size grid aligned to [MajorTOM](https://huggingface.co/Major-TOM) cell IDs.

Each output tile is a gzip-compressed HDF5 file with all requested S2 bands stacked into a single `(bands, 1000, 1000)` array at 10 m resolution, georeferenced by an affine transform and CRS.


## Pipeline overview

The script runs five sequential stages:

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│ 1. Grid      │ ──▶ │ 2. Search    │ ──▶ │ 3. Download  │ ──▶ │ 4. Crop &    │ ──▶ │ 5. Write     │
│    setup     │     │    & rank    │     │              │     │    reproject │     │    H5 + DB   │
└──────────────┘     └──────────────┘     └──────────────┘     └──────────────┘     └──────────────┘
```


### Stage 1 — Grid setup

**What**: Build a WGS84 polygon (footprint) for each requested MajorTOM cell ID.

**How**: The MajorTOM grid divides the globe into ~10 km × 10 km cells. Latitude rows are evenly spaced along the pole-to-pole arc; longitude columns are evenly spaced along each latitude's parallel (so the number of columns per row varies with latitude). Each cell ID like `130U_447R` encodes a row index (130 steps up from the equator) and a column index (447 steps right of the prime meridian).

The script can resolve IDs in two ways:
- **GeoJSON grid file** (`--grid-geojson`): looks up pre-computed cell polygons. Fastest for large batches.
- **On-the-fly computation** (fallback): reconstructs the grid mathematically from `--grid-dist-km`.



### Stage 2 — Search & rank

**What**: Query the Copernicus Data Space Ecosystem (CDSE) for S2 products that overlap the union of all requested cells, within a time window around `--timestamp`.

**How**:
1. The union bounding box of all cell footprints becomes the Area of Interest (AOI), optionally expanded by `--aoi-margin-km`.
2. CDSE is queried via `phidown` for products matching the AOI, time window, product type (`--product-type`, default `S2MSI2A`), and cloud cover threshold (`--cloud-max`).
3. Results are ranked by:
   - **Time proximity** to the target timestamp (primary sort).
   - **Cloud cover** percentage (secondary sort, lower is better; unknown cloud is allowed by default).
4. Products outside the `--cloud-min` / `--cloud-max` range are filtered out.


### Stage 3 — Download

**What**: Download ranked S2 products one at a time via S3 (using `s5cmd`).

**How**: For each product (up to `--max-products`), the full `.SAFE` package is downloaded to `--download-dir`. The script then discovers band rasters inside `IMG_DATA/`, preferring the finest available resolution copy for each band (R10m > R20m > R60m).

**Early exit**: If `--stop-when-all-covered` (default) and every requested cell has been written, processing stops without downloading further products.


### Stage 4 — Crop & reproject

This is the core geometric step. For each (product, cell) pair:

#### 4a. Coverage check

Before cropping, the script verifies that the S2 product actually covers the cell. It projects the cell polygon into the product CRS, intersects it with the product extent, and computes the fraction of the cell that contains valid (non-nodata) pixels. Cells below `--min-id-coverage-ratio` (default 1.0 = full coverage required) are skipped.

#### 4b. Output grid construction

The cell polygon (a rectangle in WGS84) is projected into the product's native UTM CRS. Due to meridian convergence, this becomes a **parallelogram**, not a rectangle. The output grid is defined as:

- **Shape**: the **Axis-Aligned Bounding Box** (AABB) of the projected parallelogram.
- **Dimensions**: forced to `target_pixels × target_pixels` (= `grid_dist_km * 1000 / native_res` = 1000 × 1000 for a 10 km grid at 10 m).
- **Transform**: north-up affine (no rotation).

This approach (rather than the tighter Minimum Rotated Rectangle) ensures exact, consistent pixel dimensions across all tiles and a north-up orientation compatible with any downstream tool.

#### 4c. Reprojection

Each S2 band is reprojected from its native grid onto the output grid using **bilinear resampling** (`rasterio.warp.reproject`). Source nodata values (typically 0 for S2) are mapped to NaN in the output. The output array is pre-filled with NaN, so areas not covered by the source product remain NaN.

The first band (reference band, chosen by priority B02 > B03 > B04 > B08) defines the output grid. All subsequent bands reuse the same `ref_shape`, `ref_transform`, and `ref_crs`.

#### 4d. Area sanity check

After building the output grid, `s2_grid_area_metrics` compares the grid's footprint area (pixel_size × n_pixels) against the true projected cell area. If the relative error exceeds `--max-grid-area-relative-error` (default 5%), the tile is skipped. This guards against pathological cases near UTM zone boundaries.

#### 4e. Quality filters

- **All-NaN check**: tiles where the entire stack is NaN are rejected.
- **Non-zero pixel ratio**: tiles where the fraction of finite non-zero pixels is below `--min-nonzero-pixel-ratio` (default 5%) are rejected. This catches tiles that fall on S2 swath edges or are dominated by padding.


### Stage 5 — Write H5 + metadata

Each surviving tile is saved as `<crops-dir>/<ID>.h5`:

| Dataset/Attribute | Content |
|---|---|
| `data` | `float32` array, shape `(n_bands, 1000, 1000)`, gzip-compressed |
| `band_names` | 1D array of band tokens (e.g. `B02`, `B03`, …, `B8A`) |
| `transform` (attr) | 6-element affine transform tuple |
| `crs` (attr) | CRS string (e.g. `EPSG:32637`) |

A per-product Parquet metadata file is also written to `<crops-dir>/DB/`, recording mission, product name, acquisition time, and the list of covered IDs. After all products are processed, per-product Parquets are merged into `all_products_core_metadata.parquet`.


---


## Why same pixel count (1000×1000) but different areas?

All tiles have exactly 1000 × 1000 pixels by construction (`target_pixels` is forced). But each tile covers a slightly different ground area because:

1. A MajorTOM cell is defined as a rectangle in **WGS84 (lat/lon)**. In lat/lon, every cell at the same latitude row has the same angular extent.

2. When that cell is projected into **UTM (metres)**, the AABB size in metres depends on two things:
   - **Meridian convergence**: UTM grid north diverges from true north away from the central meridian. A WGS84 rectangle becomes a tilted parallelogram, and its AABB is wider than the parallelogram itself. The further the cell is from the UTM zone's central meridian, the larger the tilt and the wider the AABB.
   - **Scale distortion**: UTM is a conformal projection; the scale factor varies with position within the zone.

3. Since the pixel count is fixed at 1000 × 1000 but the AABB ground extent varies per tile, the **pixel spacing adapts per tile**. For example:

   | Tile | AABB (m) | Pixel spacing | Area (km²) |
   |------|----------|--------------|------------|
   | 130U_445R | 10065 × 10003 | 10.065 × 10.003 | 100.68 |
   | 130U_447R | 10073 × 10010 | 10.073 × 10.010 | 100.83 |
   | 130U_448R | 10076 × 10014 | 10.076 × 10.014 | 100.91 |

   All three cells have the same angular size in WGS84, but their projected AABBs differ by tens of metres depending on where in the UTM zone the cell falls.

The deviation from the nominal 10 m pixel spacing is small (< 1% near the equator, up to ~2% at 45° latitude). Every tile stores its own affine transform, so downstream code always knows the exact ground location of each pixel.


---


## Design choices

| Choice | Rationale |
|---|---|
| **AABB** instead of Minimum Rotated Rectangle (MRR) | MRR produces a rotated affine (non-zero shear terms), which breaks downstream tools that assume north-up grids. MRR also under-sizes one dimension, giving non-square tiles (e.g. 994 × 1000). AABB is north-up, fully contains the cell, and is the standard approach used by ESA SNAP. |
| **Forced `target_pixels`** | Without it, `ceil(extent / native_res)` gives tiles that differ by a few pixels (e.g. 1000 × 1001 vs 1007 × 1000). Forcing both dimensions to 1000 guarantees uniform tensor shapes for batched ML training. |
| **No geometry mask** on AABB corners | The AABB is slightly larger than the actual cell parallelogram. The extra corner pixels contain real S2 imagery (from neighboring cells). Masking them to NaN would make it impossible to achieve 100% valid-pixel coverage, which is needed for strict quality thresholds. The exact cell boundary is recoverable from the cell ID + grid parameters if needed downstream. |
| **Bilinear resampling** | Standard for continuous-valued optical imagery. S2 reflectance values are smooth enough that bilinear is appropriate. Nearest-neighbor would introduce blocky artifacts; cubic adds ringing near sharp edges. |
| **Per-band reprojection** | S2 L2A bands come at different native resolutions (10m, 20m, 60m). Each band is reprojected from its own native grid onto the shared 10m output grid. The reference band (finest resolution, e.g. B02) defines the grid; coarser bands are upsampled by bilinear interpolation. |
| **`max-grid-area-relative-error` default = 5%** | The AABB is inherently larger than the parallelogram (up to ~4% at 45° latitude). The 5% default allows all normal tiles while catching pathological cases (e.g. tiles spanning UTM zone boundaries). |
| **Cloud ranking, not hard filtering** | Products are sorted by time proximity first, then cloud cover. This prefers temporally closer acquisitions even if slightly cloudier, which is usually the right trade-off for temporal matching with SAR. |


---


## Usage

```bash
python s2_alignment.py \
    --timestamp 2025-11-22T02:46:35Z \
    --ids-file common_majortom_ids_nisar_s1.txt \
    --download-dir /path/to/downloads \
    --crops-dir /path/to/crops \
    --bands all \
    --product-type S2MSI2A \
    --time-window-days 10 \
    --cloud-max 80 \
    --max-products 3 \
    --s5cfg .s5cfg
```


## CLI reference

| Argument | Default | Description |
|---|---|---|
| `--timestamp` | *(required)* | Target acquisition time (ISO 8601) |
| `--time-window-days` | 10 | Search window width in days (centered on timestamp) |
| `--ids` / `--ids-file` | — | MajorTOM IDs (comma-separated or one per line) |
| `--grid-dist-km` | 10 | Grid cell spacing in km |
| `--grid-geojson` | `grid_10km.geojson` | Pre-computed grid GeoJSON (optional) |
| `--buffer-ratio` | 0 | Expand each cell footprint by this fraction |
| `--aoi-margin-km` | 0 | Expand the search AOI bounding box (km) |
| `--download-dir` | *(required)* | Where to download S2 products |
| `--crops-dir` | *(required)* | Where to write output H5 tiles |
| `--s5cfg` | `.s5cfg` | s5cmd credentials file |
| `--bands` | `all` | Band selection: `all` or comma list (e.g. `B02,B03,B04`) |
| `--product-type` | `S2MSI2A` | CDSE product type filter |
| `--top` | max(max_products, 100) | Max search results from CDSE |
| `--max-products` | 1 | Max products to download and process |
| `--cloud-min` / `--cloud-max` | 0 / 100 | Cloud cover filter range (%) |
| `--reject-unknown-cloud` | off | Drop products with unknown cloud cover |
| `--min-id-coverage-ratio` | 1.0 | Min fraction of cell covered by product |
| `--min-nonzero-pixel-ratio` | 0.05 | Min fraction of non-zero finite pixels |
| `--max-grid-area-relative-error` | 0.05 | Max relative area mismatch (AABB vs cell) |
| `--stop-when-all-covered` | on | Stop after all IDs are covered |
| `--process-all-products` | off | Process all ranked products regardless |
| `--overwrite` | off | Overwrite existing H5 files |
| `--delete-downloaded-product` | off | Remove downloaded .SAFE after processing |
