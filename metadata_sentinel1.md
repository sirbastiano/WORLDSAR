# Sentinel-1 Tile Metadata (`123D_472R.h5`)

## Tile inspected
- File: `/shared/home/rdelprete/PythonProjects/AgenticWork/worldsar_guide/WORLDSAR/outputs/tiles/S1A_S3_SLC__1SDV_20151229T152825_20151229T152844_009258_00D5C6_F1C9/123D_472R.h5`
- Format: HDF5
- Size: `29,536,656` bytes
- Top-level groups: `bands`, `metadata`

## Raster content (`/bands`)
All bands are `float32` with shape `1000 x 1127` and attributes `scaling_factor=1.0`, `scaling_offset=0.0`, `log10_scaled=false`.

- `Alpha` (unit: `deg`)
- `Anisotropy` (unit: `anisotropy`)
- `Entropy` (unit: `entropy`)
- `elevation` (unit: `meters`)
- `localIncidenceAngle` (unit: `deg`)

## Acquisition and product metadata (`/metadata/Abstracted_Metadata`)
- Mission: `SENTINEL-1A`
- Product: `S1A_S3_SLC__1SDV_20151229T152825_20151229T152844_009258_00D5C6_F1C9`
- Product type: `SLC`
- Acquisition mode: `SM`
- Pass: `ASCENDING`
- Polarizations: `VH`, `VV`
- Orbit: `ABS_ORBIT=9258`, `REL_ORBIT=86`, `orbit_cycle=67`
- Orbit file: `Sentinel Precise S1A_OPER_AUX_POEORB_OPOD_20210310T024756_V20151228T225943_20151230T005943.EOF.zip`
- DEM: `Copernicus 30m Global DEM`
- Terrain-corrected flag: `1`
- CRS / projection metadata: `WGS84`, `WGS 84 / Auto UTM`

## Tile geospatial footprint summary
- First line time: `29-DEC-2015 15:28:26.491675`
- Last line time: `29-DEC-2015 15:28:27.794351`
- Center: `lat=-11.521651184964222`, `lon=43.28013085660429`
- Near/Far corners in metadata:
- `first_near`: `(-10.957552100862944, 43.18172845991906)`
- `first_far`: `(-10.958148918602236, 43.28473670480687)`
- `last_near`: `(-11.04785591676626, 43.18117459028413)`
- `last_far`: `(-11.048457771824673, 43.284214174201594)`
- Pixel spacing: `10.0 m` range, `10.0 m` azimuth
- Raster dimensions: `num_output_lines=1000`, `num_samples_per_line=1127`

## Subset provenance (`/metadata/history/SubsetInfo`)
- Source product: `S1A_S3_SLC__1SDV_20151229T152825_20151229T152844_009258_00D5C6_F1C9_TC`
- Subregion origin: `x=4436`, `y=897`
- Subregion size: `width=1127`, `height=1000`
- Subsampling: `x=1`, `y=1`
- Subset contains these bands: `Entropy`, `Anisotropy`, `Alpha`, `elevation`, `localIncidenceAngle`

## Processing lineage (`/metadata/Processing_Graph`)
The recorded SNAP graph for this tile includes:

- `Apply-Orbit-File`
- `Calibration`
- `Polarimetric-Decomposition`
- `Terrain-Correction`
- `Subset`
- `Write` steps between/after operators

Recorded module version in graph nodes: `12.0.0`.
