# NISAR-Sentinel-1 Matching Pipeline

This pipeline identifies and analyzes temporal stacks of NISAR GSLC products that have matching Sentinel-1 SLC acquisitions, enabling cross-mission SAR analysis.

## Overview

The workflow consists of 4 sequential Python scripts:

1. **`0_retrieve_NISAR_products.py`** - Retrieve NISAR GSLC product catalog
2. **`1_search_matches.py`** - Search for matching Sentinel-1 SLC products
3. **`2_build_stacks.py`** - Build temporal stacks from matches
4. **`3_visualize.py`** - Generate interactive visualizations

## Prerequisites

### Required Python Packages

```bash
pip install asf-search pandas shapely phidown networkx folium tqdm
```

## Usage

### Run the Full Sequence

Use the provided script to run all steps with configurable arguments:

```bash
./run.sh
```

**Common overrides:**

```bash
./run.sh \
  --spatial-threshold 0.6 \
  --threshold-days 30 \
  --min-products 2 \
  --min-days 7
```

**Notes:**
- Default venv: `/Users/roberto.delprete/Library/CloudStorage/OneDrive-ESA/Desktop/Repos/WORLDSAR/srp/.venv` (override with `--venv`)
- Use `--skip-step0` to reuse an existing `nisar_gslc_*.csv`
- See `./run.sh --help` for the full list of options

### Step 0: Retrieve NISAR Products

Searches for all available NISAR GSLC (Geocoded Single Look Complex) products and exports metadata to CSV.

```bash
python 0_retrieve_NISAR_products.py
```

**Output:**
- `nisar_gslc_YYYYMMDD_HHMMSS.csv` - Catalog with NISAR product metadata

**No arguments required** - produces timestamped CSV with all NISAR GSLC products.

---

### Step 1: Search for Sentinel-1 Matches

Finds Sentinel-1 SLC products that match NISAR acquisitions in space and time.

```bash
python 1_search_matches.py [OPTIONS]
```

**Options:**

| Flag | Default | Description |
|------|---------|-------------|
| `--db-path` | Latest `nisar_gslc_*.csv` | Path to NISAR CSV from step 0 |
| `--output-path` | `deliverable/nisar_s1_IW_matches.parquet` | Output parquet file path |
| `--spatial-threshold` | `0.6` | Minimum spatial overlap ratio (0-1) |
| `--threshold-days` | `30` | Temporal threshold in days |
| `--chunk-size` | `300` | Number of NISAR rows per processing chunk |
| `--s1-mode` | `IW` | Sentinel-1 mode (IW, EW, SM, WV) |
| `--s1-product-type` | `SLC` | Sentinel-1 product type |

**Examples:**

```bash
# Use defaults (IW mode, 30 days, 60% overlap)
python 1_search_matches.py

# Custom thresholds
python 1_search_matches.py --spatial-threshold 0.75 --threshold-days 14

# Search for EW mode products
python 1_search_matches.py --s1-mode EW --output-path deliverable/nisar_s1_EW_matches.parquet

# Process specific NISAR catalog
python 1_search_matches.py --db-path nisar_gslc_20260202_225309.csv
```

**Output:**
- `deliverable/nisar_s1_IW_matches.parquet` - Matched NISAR-S1 product pairs

**Processing:**
- Runs asynchronously with chunked processing
- Progress bars show search status
- Creates deliverable directory if needed

---

### Step 2: Build Temporal Stacks

Constructs temporal stacks by grouping spatially overlapping NISAR products and associates matching S1 products.

```bash
python 2_build_stacks.py [OPTIONS]
```

**Options:**

| Flag | Default | Description |
|------|---------|-------------|
| `--matches-path` | `deliverable/nisar_s1_IW_matches.parquet` | Input matches from step 1 |
| `--output-dir` | `output/` | Directory for individual stack CSV files |
| `--deliverable-dir` | `deliverable/` | Directory for summary outputs |
| `--overlap-threshold` | `0.6` | Minimum overlap ratio to connect products |
| `--min-products` | `2` | Minimum products per stack for summary |
| `--min-days` | `7` | Minimum temporal coverage (days) for summary |

**Examples:**

```bash
# Use defaults (7 days, 2+ products, 60% overlap)
python 2_build_stacks.py

# Stricter quality requirements
python 2_build_stacks.py --min-products 10 --min-days 730 --overlap-threshold 0.9

# Custom input/output paths
python 2_build_stacks.py \
  --matches-path deliverable/nisar_s1_EW_matches.parquet \
  --output-dir stacks_ew/
```

**Output:**
- `output/stack_0.csv`, `output/stack_1.csv`, ... - Individual stack files
- `deliverable/nisar_stacks_one_year.parquet` - Summary of stacks meeting `--min-products` / `--min-days`
- `deliverable/nisar_stacks_one_year.csv` - Same summary as CSV
- `deliverable/nisar_stacks_documentation.md` - Documentation of stack generation

**Stack Files Contain:**
- NISAR product identifiers and timestamps
- Matching S1 product information
- Temporal baseline between acquisitions
- Spatial coverage (WKT geometry)

---

### Step 3: Visualize Stacks

Generates interactive HTML maps and statistics dashboard.

```bash
python 3_visualize.py [OPTIONS]
```

**Options:**

| Flag | Default | Description |
|------|---------|-------------|
| `--stack-dir` | `output/` | Directory with stack CSV files |
| `--visuals-dir` | `visuals/` | Output directory for HTML files |
| `--publish-dir` | `None` | Optional: copy outputs to docs directory |
| `--update-portal` | Flag | Update `docs/index.html` with NISAR stats |
| `--portal-path` | `../../../docs/index.html` | Path to portal index file |

**Examples:**

```bash
# Generate visualizations locally
python 3_visualize.py

# Publish to docs folder for GitHub Pages
python 3_visualize.py --publish-dir ../../../docs --update-portal

# Custom directories
python 3_visualize.py \
  --stack-dir stacks_ew/ \
  --visuals-dir visuals_ew/
```

**Output:**
- `visuals/nisar_s1_index.html` - Statistics summary page
- `visuals/nisar_s1_stack_heatmap.html` - Density heatmap of stacks
- `visuals/nisar_s1_temporal_frequency.html` - Temporal frequency map

**Visualizations Include:**
- Interactive Folium maps with clickable markers
- Stack quality metrics (temporal coverage, product count)
- Centroid locations with popup statistics
- Color-coded markers by temporal span

---

## Complete Workflow Example

```bash
# Step 0: Get NISAR catalog
python 0_retrieve_NISAR_products.py

# Step 1: Find S1 matches (IW mode, 30-day window, 60% overlap)
python 1_search_matches.py

# Step 2: Build stacks (7+ days, 2+ products)
python 2_build_stacks.py

# Step 3: Visualize and publish
python 3_visualize.py --publish-dir ../../../docs --update-portal
```

## Output Directory Structure

```
S1_NISAR/
├── nisar_gslc_20260202_225309.csv        # Step 0 output
├── deliverable/
│   ├── nisar_s1_IW_matches.parquet       # Step 1 output
│   ├── nisar_stacks_one_year.parquet     # Step 2 summary
│   ├── nisar_stacks_one_year.csv
│   └── NISAR_STACKS_README.md
├── output/
│   ├── stack_0.csv                        # Step 2 individual stacks
│   ├── stack_1.csv
│   └── ...
└── visuals/
    ├── nisar_s1_index.html                # Step 3 visualizations
    ├── nisar_s1_stack_heatmap.html
    └── nisar_s1_temporal_frequency.html
```

## Key Parameters Explained

### Spatial Threshold (Step 1)
- **Range:** 0.0 to 1.0
- **Default:** 0.6 (60% overlap)
- **Effect:** Minimum overlap between NISAR and S1 footprints (intersection area / min footprint area)
- **Higher values:** Stricter matching, fewer results
- **Lower values:** More permissive, potentially less relevant matches

### Temporal Threshold (Step 1)
- **Units:** Days
- **Default:** 30 days
- **Effect:** Maximum time difference between NISAR and S1 acquisitions
- **Search window:** Expands ±(threshold/2) around each NISAR acquisition

### Overlap Threshold (Step 2)
- **Range:** 0.0 to 1.0
- **Default:** 0.6 (60% overlap)
- **Effect:** Minimum overlap between NISAR products to group into same stack (intersection / min footprint area)
- **Purpose:** Ensures spatial coherence within temporal stacks

### Minimum Products/Days (Step 2)
- **Filters:** Which stacks appear in summary outputs
- **Does not delete:** All stacks saved to `output/` regardless
- **Purpose:** Focus on high-quality temporal series

## Troubleshooting

### "No NISAR CSV found"
Run step 0 first: `python 0_retrieve_NISAR_products.py`



### "Module not found"
Install dependencies:
```bash
pip install asf-search pandas shapely phidown networkx folium tqdm
```

### Empty results (Step 1)
- Relax thresholds: `--spatial-threshold 0.5 --threshold-days 45`
- Check S1 mode availability for your region
- Verify NISAR catalog has valid geometries

### Performance (Step 1)
- Reduce `--chunk-size` if memory issues occur
- Increase `--chunk-size` for faster processing (if memory permits)
- Processing is asynchronous - wait for all chunks to complete

## Notes

- **Step 1** can take considerable time depending on NISAR catalog size
- **Chunk processing** in step 1 allows interruption/resumption
- **Stack numbering** in step 2 is arbitrary (no spatial/temporal order)
- **Visualization** in step 3 works best with Chrome/Firefox for full Folium features
- All timestamps are in **UTC**
- Geometries use **WGS84** (EPSG:4326)

## References

- **NISAR Mission:** [nisar.jpl.nasa.gov](https://nisar.jpl.nasa.gov/)
- **ASF Search API:** [github.com/asfadmin/Discovery-asf_search](https://github.com/asfadmin/Discovery-asf_search)
- **Copernicus Data Space:** [dataspace.copernicus.eu](https://dataspace.copernicus.eu/)
- **phidown:** Copernicus Data Space search/download library
