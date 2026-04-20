import argparse
import json
import math
import re
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path

import h5py
import numpy as np
import pandas as pd
import rasterio
import rasterio.features
from affine import Affine
from pyproj import Transformer
from rasterio.mask import mask
from rasterio.transform import from_bounds
from rasterio.warp import Resampling, reproject
from shapely import wkt as shapely_wkt
from shapely.geometry import box, mapping, shape
from shapely.ops import transform as shapely_transform


EARTH_RADIUS_EQUATOR_KM = 6378.137


def parse_timestamp(value: str) -> datetime:
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def parse_ids(ids_arg, ids_file):
    ids = []
    if ids_arg:
        ids.extend([item.strip() for item in ids_arg.split(",") if item.strip()])

    if ids_file:
        path = Path(ids_file)
        if not path.exists():
            raise FileNotFoundError(f"IDs file not found: {path}")
        for line in path.read_text().splitlines():
            text = line.strip()
            if text:
                ids.append(text)

    ids = list(dict.fromkeys(ids))
    if not ids:
        raise ValueError("No IDs provided. Use --ids or --ids-file.")
    return ids


def _row_label_to_int(label: str) -> int:
    m = re.fullmatch(r"(\d+)([UD])", label.upper())
    if not m:
        raise ValueError(f"Invalid row label: {label}")
    value = int(m.group(1))
    return value if m.group(2) == "U" else -value


def _col_label_to_int(label: str) -> int:
    m = re.fullmatch(r"(\d+)([RL])", label.upper())
    if not m:
        raise ValueError(f"Invalid col label: {label}")
    value = int(m.group(1))
    return value if m.group(2) == "R" else -value


def _grid_latitudes(dist_km: float) -> np.ndarray:
    arc_pole_to_pole = math.pi * EARTH_RADIUS_EQUATOR_KM
    n = math.ceil(arc_pole_to_pole / dist_km)
    lats = np.linspace(-90, 90, n + 1)[:-1]
    lats = np.mod(lats, 180) - 90
    return np.sort(lats)


def _grid_rows(dist_km: float):
    lats = _grid_latitudes(dist_km)
    zeroth = int(np.searchsorted(lats, 0.0))
    rows = [None] * len(lats)
    rows[zeroth:] = [f"{i}U" for i in range(len(lats) - zeroth)]
    rows[:zeroth] = [f"{abs(i - zeroth)}D" for i in range(zeroth)]
    return np.array(rows), lats


def _longitudes_for_lat(lat: float, dist_km: float) -> np.ndarray:
    radius_at_lat = EARTH_RADIUS_EQUATOR_KM * math.cos(math.radians(lat))
    circumference = 2 * math.pi * max(radius_at_lat, 1e-9)
    n = max(1, math.ceil(circumference / dist_km))
    lons = np.linspace(-180, 180, n + 1)[:-1]
    lons = np.mod(lons, 360) - 180
    return np.sort(lons)


def _cols_for_longitudes(lons: np.ndarray) -> np.ndarray:
    cols = [None] * len(lons)
    zeroth = int(np.argmin(np.abs(lons - 0.0)))
    cols[zeroth:] = [f"{i}R" for i in range(len(lons) - zeroth)]
    cols[:zeroth] = [f"{abs(i - zeroth)}L" for i in range(zeroth)]
    return np.array(cols)


def _extract_grid_feature_id(feature: dict):
    properties = feature.get("properties") or {}
    candidates = [
        feature.get("id"),
        properties.get("ID"),
        properties.get("id"),
        properties.get("grid_id"),
        properties.get("GRID_ID"),
        properties.get("majortom_id"),
        properties.get("MajorTOM_ID"),
        properties.get("name"),
        properties.get("Name"),
    ]
    for value in candidates:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def load_id_footprints_from_geojson(ids, grid_geojson_path: Path, buffer_ratio: float = 0.0):
    with grid_geojson_path.open("r", encoding="utf-8") as f:
        payload = json.load(f)

    features = payload.get("features") if isinstance(payload, dict) else None
    if not isinstance(features, list):
        raise ValueError(f"Invalid GeoJSON structure in {grid_geojson_path}: missing features list")

    requested = {str(grid_id).upper(): grid_id for grid_id in ids}
    footprints = {}

    for feature in features:
        if not isinstance(feature, dict):
            continue

        feature_id = _extract_grid_feature_id(feature)
        if feature_id is None:
            continue

        requested_id = requested.get(feature_id.upper())
        if requested_id is None or requested_id in footprints:
            continue

        geometry_data = feature.get("geometry")
        if geometry_data is None:
            continue

        try:
            geom = shape(geometry_data)
        except Exception:
            continue

        if geom.is_empty or geom.geom_type not in {"Polygon", "MultiPolygon"}:
            continue

        if buffer_ratio > 0:
            minx, miny, maxx, maxy = geom.bounds
            width = maxx - minx
            height = maxy - miny
            bx = width * buffer_ratio
            by = height * buffer_ratio
            geom = box(minx - bx, miny - by, maxx + bx, maxy + by)

        footprints[requested_id] = geom
        if len(footprints) == len(ids):
            break

    missing = [grid_id for grid_id in ids if grid_id not in footprints]
    return footprints, missing


def footprint_from_id(grid_id: str, dist_km: float, buffer_ratio: float = 0.0):
    m = re.fullmatch(r"([0-9]+[UD])_([0-9]+[RL])", grid_id.upper())
    if not m:
        raise ValueError(f"Invalid Major-TOM ID format: {grid_id}")

    row_label, col_label = m.group(1), m.group(2)

    rows, lats = _grid_rows(dist_km)
    row_map = {r: i for i, r in enumerate(rows)}
    if row_label not in row_map:
        raise ValueError(f"Row out of grid domain for ID {grid_id}")

    row_idx = row_map[row_label]
    bottom = float(lats[row_idx])
    if row_idx + 1 < len(lats):
        top = float(lats[row_idx + 1])
    else:
        top = float(lats[row_idx] + (lats[row_idx] - lats[row_idx - 1]))

    lons = _longitudes_for_lat(bottom, dist_km)
    cols = _cols_for_longitudes(lons)
    col_map = {c: i for i, c in enumerate(cols)}
    if col_label not in col_map:
        raise ValueError(f"Column out of grid domain for ID {grid_id}")

    col_idx = col_map[col_label]
    left = float(lons[col_idx])
    if col_idx + 1 < len(lons):
        right = float(lons[col_idx + 1])
    else:
        right = float(lons[col_idx] + (lons[col_idx] - lons[col_idx - 1]))

    width = right - left
    height = top - bottom
    bx = width * buffer_ratio
    by = height * buffer_ratio

    return box(left - bx, bottom - by, right + bx, top + by)


def build_id_footprints(ids, grid_dist_km=10.0, buffer_ratio=0.0, grid_geojson: Path | None = None):
    footprints = {}
    missing = []

    pending_ids = list(ids)
    if grid_geojson is not None:
        if grid_geojson.exists():
            try:
                loaded_footprints, pending_ids = load_id_footprints_from_geojson(
                    ids,
                    grid_geojson_path=grid_geojson,
                    buffer_ratio=buffer_ratio,
                )
                footprints.update(loaded_footprints)
                print(
                    f"Loaded {len(loaded_footprints)}/{len(ids)} ID footprints from GeoJSON grid: {grid_geojson}"
                )
            except Exception as exc:
                print(f"Warning: failed loading grid GeoJSON {grid_geojson} ({exc}). Falling back to on-the-fly grid.")
                pending_ids = list(ids)
        else:
            print(f"Grid GeoJSON not found: {grid_geojson}. Falling back to on-the-fly grid.")

    for grid_id in pending_ids:
        try:
            footprints[grid_id] = footprint_from_id(grid_id, dist_km=grid_dist_km, buffer_ratio=buffer_ratio)
        except Exception:
            missing.append(grid_id)
    return footprints, missing


def expand_bounds_km(minx: float, miny: float, maxx: float, maxy: float, margin_km: float):
    if margin_km <= 0:
        return minx, miny, maxx, maxy

    center_lat = (miny + maxy) / 2.0
    delta_lat = margin_km / 111.32
    cos_lat = math.cos(math.radians(center_lat))
    if abs(cos_lat) < 1e-6:
        cos_lat = 1e-6
    delta_lon = margin_km / (111.32 * cos_lat)
    return minx - delta_lon, miny - delta_lat, maxx + delta_lon, maxy + delta_lat


def ids_to_aoi_wkt(footprints_wgs84: dict, margin_km: float = 0.0) -> str:
    if not footprints_wgs84:
        raise ValueError("Cannot build AOI: empty Major-TOM footprint dictionary.")

    minx = min(poly.bounds[0] for poly in footprints_wgs84.values())
    miny = min(poly.bounds[1] for poly in footprints_wgs84.values())
    maxx = max(poly.bounds[2] for poly in footprints_wgs84.values())
    maxy = max(poly.bounds[3] for poly in footprints_wgs84.values())

    minx, miny, maxx, maxy = expand_bounds_km(minx, miny, maxx, maxy, margin_km)
    return box(minx, miny, maxx, maxy).wkt


def product_start_time(row: pd.Series):
    content = row.get("ContentDate")
    if isinstance(content, dict) and "Start" in content:
        try:
            return parse_timestamp(content["Start"])
        except Exception:
            pass

    for key in ["OriginDate", "ContentDate/Start", "Start", "startDate"]:
        if key in row and pd.notna(row[key]):
            try:
                return parse_timestamp(str(row[key]))
            except Exception:
                continue
    return None


def product_cloud_cover(row: pd.Series):
    for key in ["CloudCover", "cloud_cover"]:
        if key in row and pd.notna(row[key]):
            try:
                return float(row[key])
            except Exception:
                pass

    attrs = row.get("Attributes")
    if isinstance(attrs, list):
        for item in attrs:
            if not isinstance(item, dict):
                continue
            name = str(item.get("Name", "")).strip().lower()
            if name == "cloudcover":
                value = item.get("Value")
                try:
                    return float(value)
                except Exception:
                    continue

    return float("nan")


def rank_products(df: pd.DataFrame, target_ts: datetime) -> pd.DataFrame:
    ranked = df.copy()
    ranked["_start_dt"] = ranked.apply(product_start_time, axis=1)
    ranked = ranked[ranked["_start_dt"].notna()].copy()
    if ranked.empty:
        raise ValueError("Search results found, but no valid acquisition timestamps were parsed.")

    ranked["_time_diff"] = ranked["_start_dt"].apply(lambda d: abs((d - target_ts).total_seconds()))
    ranked["_cloud"] = ranked.apply(product_cloud_cover, axis=1)
    ranked["_cloud"] = pd.to_numeric(ranked["_cloud"], errors="coerce")
    ranked["_cloud_sort"] = ranked["_cloud"].fillna(999.0)
    ranked = ranked.sort_values(["_time_diff", "_cloud_sort"]).reset_index(drop=True)
    return ranked


def parse_s2_name_fields(product_name: str):
    text = str(product_name)
    mission = None
    acquisition_mode = None
    product_type = None

    m = re.match(r"^(S2[ABC])_MSI(L[12][AC])", text.upper())
    if m:
        mission_code = m.group(1)
        mission = f"SENTINEL-{mission_code[1]}{mission_code[2]}"
        acquisition_mode = "MSI"
        product_type = m.group(2)

    return mission, acquisition_mode, product_type


def product_name_prefix(product_name: str):
    return product_name[:-5] if product_name.endswith(".SAFE") else product_name


def extract_band_token(path: Path):
    match = re.search(r"(?:^|_)(B(?:0[1-9]|1[0-2]|8A))(?:_|\.)", path.name.upper())
    if match:
        return match.group(1)
    return None


def choose_reference_band_path(band_paths):
    priority = ["B02", "B03", "B04", "B08"]
    by_token = {extract_band_token(Path(path)): Path(path) for path in band_paths}
    for token in priority:
        if token in by_token:
            return by_token[token]
    return Path(band_paths[0])


def _band_res_priority(path: Path) -> int:
    """Return a resolution priority (lower = finer).  0=10m, 1=20m, 2=60m, 3=unknown.

    Sentinel-2 L2A stores copies of 10m bands in the R20m folder (and in R60m),
    so the same band token (e.g. B02) can appear at multiple resolutions.  We
    always want the finest available copy as the reference for the output grid.
    """
    s = path.as_posix()
    if "R10m" in s or "_10m." in s:
        return 0
    if "R20m" in s or "_20m." in s:
        return 1
    if "R60m" in s or "_60m." in s:
        return 2
    return 3


def find_product_band_rasters(download_dir: Path, product_name: str, requested_band_tokens):
    candidates = []
    for ext in ("*.tif", "*.tiff", "*.jp2"):
        candidates.extend(download_dir.rglob(ext))

    if not candidates:
        raise FileNotFoundError(
            f"No raster files found in {download_dir}. Expected .tif/.tiff/.jp2 after download."
        )

    prefix = product_name_prefix(product_name)
    product_candidates = [p for p in candidates if prefix in p.as_posix() or prefix in p.name]
    product_candidates = [p for p in product_candidates if "IMG_DATA" in p.as_posix()]
    if not product_candidates:
        raise FileNotFoundError(f"No raster files found for product {product_name} under {download_dir}.")

    band_map = {}
    for path in product_candidates:
        token = extract_band_token(path)
        if token is None:
            continue
        existing = band_map.get(token)
        if existing is None:
            band_map[token] = path
        else:
            new_prio = _band_res_priority(path)
            old_prio = _band_res_priority(existing)
            # Always prefer the finer-resolution copy; break ties by mtime.
            if new_prio < old_prio or (
                new_prio == old_prio and path.stat().st_mtime > existing.stat().st_mtime
            ):
                band_map[token] = path

    if not band_map:
        raise FileNotFoundError(
            f"No Sentinel-2 band rasters (Bxx/B8A) detected for product {product_name} under {download_dir}."
        )

    if requested_band_tokens is None:
        selected_tokens = sorted(band_map.keys())
    else:
        selected_tokens = [token for token in requested_band_tokens if token in band_map]

    return [band_map[token] for token in selected_tokens]


def ensure_raster_readable(path: Path) -> Path:
    with rasterio.open(path) as src:
        _ = src.count
    return path


def extract_product_geometry_wgs84(product_row: pd.Series):
    for key in ["GeoFootprint", "Footprint", "geometry", "Geofootprint"]:
        value = product_row.get(key)
        if value is None or (isinstance(value, float) and pd.isna(value)):
            continue
        if isinstance(value, dict):
            try:
                return shape(value)
            except Exception:
                continue
        if isinstance(value, str):
            text = value.strip()
            if not text:
                continue
            if text.upper().startswith(("POLYGON", "MULTIPOLYGON")):
                try:
                    return shapely_wkt.loads(text)
                except Exception:
                    continue
            try:
                parsed = json.loads(text)
                if isinstance(parsed, dict):
                    return shape(parsed)
            except Exception:
                continue
    return None


def compute_overlapping_ids_with_coverage(
    *,
    reference_band_path: Path,
    pending_footprints_wgs84: dict,
    min_coverage_ratio: float,
    require_valid_data: bool,
):
    covered = []
    coverage_stats = {}

    with rasterio.open(reference_band_path) as src:
        transformer = Transformer.from_crs("EPSG:4326", src.crs, always_xy=True)
        product_bounds_geom = box(*src.bounds)

        for grid_id, geom_wgs84 in pending_footprints_wgs84.items():
            geom_src = shapely_transform(transformer.transform, geom_wgs84)
            geom_area = float(geom_src.area)
            if geom_area <= 0:
                coverage_stats[grid_id] = {
                    "bbox_ratio": 0.0,
                    "valid_data_ratio": 0.0,
                    "effective_ratio": 0.0,
                }
                continue

            intersection = geom_src.intersection(product_bounds_geom)
            bbox_ratio = float(intersection.area / geom_area) if not intersection.is_empty else 0.0

            valid_data_ratio = bbox_ratio
            if require_valid_data and bbox_ratio > 0:
                try:
                    out_img, out_transform = mask(
                        src,
                        [mapping(geom_src)],
                        crop=True,
                        filled=False,
                    )
                    band = out_img[0]
                    inside_geom = rasterio.features.geometry_mask(
                        [mapping(geom_src)],
                        out_shape=band.shape,
                        transform=out_transform,
                        invert=True,
                    )
                    total_inside = int(inside_geom.sum())
                    if total_inside > 0:
                        valid_mask = inside_geom & (~np.ma.getmaskarray(band))
                        data = np.ma.getdata(band)
                        if src.nodata is not None:
                            valid_mask = valid_mask & (data != src.nodata)
                        valid_fraction = float(valid_mask.sum() / total_inside)
                        valid_data_ratio = bbox_ratio * valid_fraction
                    else:
                        valid_data_ratio = 0.0
                except Exception:
                    valid_data_ratio = 0.0

            effective_ratio = min(bbox_ratio, valid_data_ratio)
            coverage_stats[grid_id] = {
                "bbox_ratio": bbox_ratio,
                "valid_data_ratio": valid_data_ratio,
                "effective_ratio": effective_ratio,
            }

            if effective_ratio >= min_coverage_ratio:
                covered.append(grid_id)

    return covered, coverage_stats


def crop_band_for_id(band_path: Path, geom_wgs84, ref_shape=None, ref_transform=None, ref_crs=None, target_pixels=None):
    """
    Crop one S2 band onto a tile-aligned output grid for a MajorTOM cell.

    The output grid is a north-up axis-aligned bounding box of the projected WGS84
    cell geometry.  When *target_pixels* is given (e.g. 1000 for a 10 km cell at 10 m
    resolution), both width and height are forced to that value so every tile has
    identical pixel dimensions.  The pixel spacing adapts slightly per tile (<1%
    deviation from native resolution).  Pixels outside the true cell polygon are
    forced to NaN via a geometry mask.
    """
    with rasterio.open(band_path) as src:
        src_nodata = src.nodata if src.nodata is not None else 0
        transformer = Transformer.from_crs("EPSG:4326", src.crs, always_xy=True)
        geom_src = shapely_transform(transformer.transform, geom_wgs84)

        if ref_shape is None:
            minx, miny, maxx, maxy = geom_src.bounds
            res_x, res_y = src.res
            if target_pixels is not None:
                width = height = int(target_pixels)
            else:
                width = max(1, int(math.ceil((maxx - minx) / abs(res_x))))
                height = max(1, int(math.ceil((maxy - miny) / abs(res_y))))
            ref_crs = src.crs
            ref_transform = Affine(
                (maxx - minx) / width,
                0.0,
                minx,
                0.0,
                -(maxy - miny) / height,
                maxy,
            )
            ref_shape = (height, width)

        # Pre-fill with NaN so areas outside S2 coverage are NaN, not zero.
        dst = np.full(ref_shape, np.nan, dtype=np.float32)
        reproject(
            source=rasterio.band(src, 1),
            destination=dst,
            src_transform=src.transform,
            src_crs=src.crs,
            dst_transform=ref_transform,
            dst_crs=ref_crs,
            resampling=Resampling.bilinear,
            src_nodata=src_nodata,  # S2 padding zeros are treated as nodata
            dst_nodata=np.nan,
        )

    return dst, ref_transform, ref_crs


def s2_grid_area_metrics(geom_wgs84, transform, shape, crs):
    """
    Compare the stored S2 grid footprint area with the projected MajorTOM cell area.

    The stored footprint comes from the affine grid itself, so this metric catches cases
    where the chosen output grid inflates too much relative to the intended cell. This is
    most useful as a geographic safeguard at high latitudes or near awkward projection
    boundaries, where a naive projected bounding box can overestimate the tile extent.
    """
    transformer = Transformer.from_crs("EPSG:4326", crs, always_xy=True)
    geom_src = shapely_transform(transformer.transform, geom_wgs84)
    geom_area = float(geom_src.area)
    if geom_area <= 0:
        return {
            "geom_area": geom_area,
            "grid_area": 0.0,
            "relative_error": float("inf"),
        }

    pixel_area = abs(transform.a * transform.e - transform.b * transform.d)
    grid_area = float(pixel_area * shape[0] * shape[1])
    relative_error = abs(grid_area - geom_area) / geom_area
    return {
        "geom_area": geom_area,
        "grid_area": grid_area,
        "relative_error": float(relative_error),
    }


def nonzero_pixel_ratio(stack: np.ndarray) -> float:
    finite = np.isfinite(stack)
    if stack.ndim == 3:
        nonzero = np.any((stack != 0) & finite, axis=0)
        return float(nonzero.mean())
    return float(np.mean((stack != 0) & finite))


def write_h5_stack_for_id(output_path: Path, stack: np.ndarray, band_names, transform, crs):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with h5py.File(output_path, "w") as h5f:
        h5f.create_dataset("data", data=stack, compression="gzip")
        h5f.create_dataset("band_names", data=np.array(band_names, dtype="S8"))
        h5f.attrs["transform"] = tuple(transform)
        h5f.attrs["crs"] = str(crs)


def build_s2_core_metadata_df(product_row: pd.Series, covered_ids):
    product_name = str(product_row.get("Name", "UNKNOWN_PRODUCT"))
    mission, acquisition_mode, product_type = parse_s2_name_fields(product_name)
    start_dt = product_row.get("_start_dt")
    if start_dt is not None and pd.isna(start_dt):
        start_dt = None
    if start_dt is None:
        start_dt = product_start_time(product_row)

    rows = []
    for grid_id in covered_ids:
        rows.append(
            {
                "MISSION": mission,
                "ACQUISITION_MODE": acquisition_mode,
                "PRODUCT_TYPE": product_type,
                "PRODUCT": product_name_prefix(product_name),
                "first_line_time": str(start_dt) if start_dt is not None else None,
                "ID": grid_id,
            }
        )
    db = pd.DataFrame(rows)
    keep_cols = []
    for col in db.columns:
        if col == "ID" or (db[col].notna().any() and (db[col].astype(str).str.len() > 0).any()):
            keep_cols.append(col)
    return db[keep_cols]


def write_s2_core_metadata_parquet(output_db_dir: Path, product_name: str, product_row: pd.Series, covered_ids):
    output_db_dir.mkdir(parents=True, exist_ok=True)
    out = output_db_dir / f"{product_name_prefix(str(product_name))}_core_metadata.parquet"
    build_s2_core_metadata_df(product_row, covered_ids).to_parquet(out, index=False)
    return out


def merge_core_metadata_parquets(output_db_dir: Path) -> Path | None:
    per_product = [
        p for p in sorted(output_db_dir.glob("*_core_metadata.parquet"))
        if p.name != "all_products_core_metadata.parquet"
    ]
    if not per_product:
        return None
    merged = pd.concat([pd.read_parquet(p) for p in per_product], ignore_index=True)
    out = output_db_dir / "all_products_core_metadata.parquet"
    merged.to_parquet(out, index=False)
    return out


def cleanup_downloaded_product(download_dir: Path, product_name: str) -> int:
    product_prefix = product_name_prefix(product_name)
    targets = set()
    for path in download_dir.rglob("*"):
        if product_prefix not in path.name:
            continue
        if path.name.endswith(".SAFE") or path.is_file():
            targets.add(path)

    deleted = 0
    for target in sorted(targets, key=lambda p: (p.is_file(), len(p.as_posix())), reverse=True):
        if not target.exists():
            continue
        if target.is_dir():
            shutil.rmtree(target, ignore_errors=True)
            deleted += 1
        else:
            target.unlink(missing_ok=True)
            deleted += 1
    return deleted


def run_search_and_download(*, aoi_wkt: str, start_date: str, end_date: str, cloud_cover_threshold: float, top: int, product_type: str):
    from phidown.search import CopernicusDataSearcher

    searcher = CopernicusDataSearcher()
    searcher.query_by_filter(
        collection_name="SENTINEL-2",
        product_type=product_type,
        cloud_cover_threshold=cloud_cover_threshold,
        aoi_wkt=aoi_wkt,
        start_date=start_date,
        end_date=end_date,
        top=top,
        count=True,
    )

    df = searcher.execute_query()
    if df is None or len(df) == 0:
        raise ValueError("No matching Sentinel-2 products found for given timestamp/location.")
    return searcher, df


def parse_band_tokens(bands_arg: str):
    if bands_arg.strip().lower() == "all":
        return None
    tokens = [token.strip().upper() for token in bands_arg.split(",") if token.strip()]
    if not tokens:
        raise ValueError("--bands cannot be empty. Use 'all' or comma-separated tokens like B02,B03,B04,B08.")
    return tokens


def parse_args():
    parser = argparse.ArgumentParser(
        description="Standalone Sentinel-2 alignment script: search, download, overlap-filter, and crop by Major-TOM IDs."
    )

    parser.add_argument("--timestamp", required=True, help="Target timestamp (ISO8601).")
    parser.add_argument("--time-window-days", type=float, default=10.0)
    parser.add_argument("--aoi-margin-km", type=float, default=0.0)
    parser.add_argument("--cloud-max", type=float, default=100.0)
    parser.add_argument("--cloud-min", type=float, default=0.0)
    parser.add_argument("--allow-unknown-cloud", action="store_true", default=True)
    parser.add_argument("--reject-unknown-cloud", action="store_true")

    parser.add_argument("--ids", default=None)
    parser.add_argument("--ids-file", default=None)
    parser.add_argument("--grid-dist-km", type=float, default=10.0)
    parser.add_argument("--buffer-ratio", type=float, default=0.0)
    parser.add_argument(
        "--grid-geojson",
        default="grid_10km.geojson",
        help="Path to precomputed grid GeoJSON. Default mode tries this first, then falls back to on-the-fly grid.",
    )

    parser.add_argument("--download-dir", required=True)
    parser.add_argument("--crops-dir", required=True)
    parser.add_argument("--s5cfg", default=".s5cfg")
    parser.add_argument("--bands", default="all")
    parser.add_argument("--product-type", default="S2MSI2A")
    parser.add_argument("--top", type=int, default=None)
    parser.add_argument("--max-products", type=int, default=1)
    parser.add_argument("--min-id-coverage-ratio", type=float, default=1.0)
    parser.add_argument("--min-nonzero-pixel-ratio", type=float, default=0.05)
    parser.add_argument(
        "--max-grid-area-relative-error",
        type=float,
        default=0.05,
        help=(
            "Maximum allowed relative difference between the stored S2 grid footprint "
            "area and the projected MajorTOM cell area.  The AABB-based output grid is "
            "slightly larger than the projected cell (up to ~4 %% at mid-latitudes), "
            "so the default is 5 %%."
        ),
    )
    parser.add_argument("--stop-when-all-covered", action="store_true", default=True)
    parser.add_argument("--process-all-products", dest="stop_when_all_covered", action="store_false")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--delete-downloaded-product", action="store_true")
    parser.add_argument("--debug", action="store_true")

    return parser.parse_args()


def main():
    args = parse_args()
    if args.top is None:
        args.top = max(args.max_products, 100)

    if not (0.0 <= args.min_id_coverage_ratio <= 1.0):
        raise ValueError("--min-id-coverage-ratio must be in [0, 1].")
    if not (0.0 <= args.min_nonzero_pixel_ratio <= 1.0):
        raise ValueError("--min-nonzero-pixel-ratio must be in [0, 1].")
    if args.max_grid_area_relative_error < 0.0:
        raise ValueError("--max-grid-area-relative-error must be >= 0.")

    ids = parse_ids(args.ids, args.ids_file)
    grid_geojson = Path(args.grid_geojson) if args.grid_geojson else None
    footprints, missing_ids = build_id_footprints(
        ids,
        grid_dist_km=args.grid_dist_km,
        buffer_ratio=args.buffer_ratio,
        grid_geojson=grid_geojson,
    )
    if not footprints:
        raise ValueError("None of the provided Major-TOM IDs matched the grid.")

    aoi_wkt = ids_to_aoi_wkt(footprints, margin_km=args.aoi_margin_km)
    target_ts = parse_timestamp(args.timestamp)
    requested_bands = parse_band_tokens(args.bands)

    half_window = timedelta(days=args.time_window_days / 2.0)
    start_date = (target_ts - half_window).astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    end_date = (target_ts + half_window).astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

    download_dir = Path(args.download_dir)
    download_dir.mkdir(parents=True, exist_ok=True)

    searcher, results_df = run_search_and_download(
        aoi_wkt=aoi_wkt,
        start_date=start_date,
        end_date=end_date,
        cloud_cover_threshold=args.cloud_max,
        top=args.top,
        product_type=args.product_type,
    )

    ranked_df = rank_products(results_df, target_ts)
    allow_unknown_cloud = args.allow_unknown_cloud and not args.reject_unknown_cloud
    known = ranked_df["_cloud"].notna()
    in_range = (ranked_df["_cloud"] >= args.cloud_min) & (ranked_df["_cloud"] <= args.cloud_max)
    ranked_df = ranked_df[in_range | (~known)] if allow_unknown_cloud else ranked_df[in_range & known]
    ranked_df = ranked_df.copy()
    if ranked_df.empty:
        raise ValueError("No products left after applying cloud filtering.")

    s5cfg = Path(args.s5cfg)
    if not s5cfg.exists():
        raise FileNotFoundError(f"s5cmd config not found: {s5cfg}")

    pending_ids = set(footprints.keys())
    all_written = 0
    processed_products = 0

    for _, product_row in ranked_df.head(args.max_products).iterrows():
        if args.stop_when_all_covered and not pending_ids:
            break

        product_name = str(product_row.get("Name", "UNKNOWN_PRODUCT"))
        target_ids = pending_ids if args.stop_when_all_covered else set(footprints.keys())
        target_footprints = {gid: footprints[gid] for gid in target_ids}
        if not target_footprints:
            continue

        geom = extract_product_geometry_wgs84(product_row)
        if geom is not None:
            overlaps = sum(1 for g in target_footprints.values() if geom.intersects(g))
            if overlaps == 0:
                print(f"Skipping product before download (catalog footprint has 0 overlapping IDs): {product_name}")
                continue

        selected_df = pd.DataFrame([product_row])
        download_result = searcher.download_products(
            df=selected_df,
            output_dir=str(download_dir),
            config_file=str(s5cfg),
            verbose=True,
            show_progress=True,
        )

        band_paths = find_product_band_rasters(download_dir, product_name, requested_bands)
        band_paths = [ensure_raster_readable(Path(p)) for p in band_paths]
        ref_band = choose_reference_band_path(band_paths)

        covered_ids, coverage_stats = compute_overlapping_ids_with_coverage(
            reference_band_path=ref_band,
            pending_footprints_wgs84=target_footprints,
            min_coverage_ratio=args.min_id_coverage_ratio,
            require_valid_data=True,
        )

        if not covered_ids:
            print(f"Skipping product after download (0 overlapping IDs): {product_name}")
            if args.delete_downloaded_product:
                deleted = cleanup_downloaded_product(download_dir, product_name)
                print(f"  Cleanup deleted {deleted} paths from download dir")
            processed_products += 1
            continue

        crops_dir = Path(args.crops_dir)
        crops_dir.mkdir(parents=True, exist_ok=True)

        band_names = [extract_band_token(Path(path)) or Path(path).stem for path in band_paths]
        with rasterio.open(ref_band) as _src:
            _native_res = max(_src.res)
        target_pixels = max(1, int(round(args.grid_dist_km * 1000 / _native_res)))
        kept_ids = []
        for grid_id in covered_ids:
            out_h5 = crops_dir / f"{grid_id}.h5"
            if out_h5.exists() and not args.overwrite:
                kept_ids.append(grid_id)
                all_written += 1
                continue

            geom_wgs84 = target_footprints[grid_id]
            try:
                ref_arr, ref_transform, ref_crs = crop_band_for_id(ref_band, geom_wgs84, target_pixels=target_pixels)
                area_metrics = s2_grid_area_metrics(
                    geom_wgs84,
                    ref_transform,
                    ref_arr.shape,
                    ref_crs,
                )
                if area_metrics["relative_error"] > args.max_grid_area_relative_error:
                    print(
                        f"  Skipping ID {grid_id}: S2 grid area mismatch "
                        f"{area_metrics['relative_error']:.3%} exceeds threshold "
                        f"{args.max_grid_area_relative_error:.3%} "
                        f"(grid={area_metrics['grid_area']:.1f} m^2, "
                        f"tile={area_metrics['geom_area']:.1f} m^2)"
                    )
                    continue

                stack_arrays = []
                for path in band_paths:
                    arr, _, _ = crop_band_for_id(
                        Path(path),
                        geom_wgs84,
                        ref_shape=ref_arr.shape,
                        ref_transform=ref_transform,
                        ref_crs=ref_crs,
                    )
                    stack_arrays.append(arr)
            except Exception as exc:
                print(f"  Skipping ID {grid_id}: crop failed ({exc})")
                continue

            stack = np.stack(stack_arrays, axis=0)
            nz_ratio = nonzero_pixel_ratio(stack)
            
            # Debug: Check if stack is all NaN or all zero
            valid_data = np.isfinite(stack).any()
            
            if not valid_data:
                print(f"  Skipping ID {grid_id}: all data is NaN or invalid")
                continue
                
            # Always reject crops that contain no non-zero finite values at all.
            if nz_ratio <= 0.0:
                print(f"  Skipping ID {grid_id}: all finite pixels are zero")
                continue

            if args.min_nonzero_pixel_ratio > 0 and nz_ratio < args.min_nonzero_pixel_ratio:
                print(
                    f"  Skipping ID {grid_id}: non-zero pixel ratio {nz_ratio:.3f} "
                    f"< threshold {args.min_nonzero_pixel_ratio:.3f}"
                )
                continue

            write_h5_stack_for_id(out_h5, stack, band_names, ref_transform, ref_crs)
            kept_ids.append(grid_id)
            all_written += 1

        if kept_ids:
            meta_path = write_s2_core_metadata_parquet(
                output_db_dir=Path(args.crops_dir) / "DB",
                product_name=product_name,
                product_row=product_row,
                covered_ids=kept_ids,
            )
            print(f"  Core metadata parquet: {meta_path}")

        pending_ids -= set(kept_ids)
        processed_products += 1

        min_eff = min(coverage_stats[gid]["effective_ratio"] for gid in covered_ids)
        print(f"Processed product: {product_name}")
        print(f"  Download result: {download_result}")
        print(f"  Bands stacked: {len(band_paths)}")
        print(f"  IDs kept: {len(kept_ids)}")
        print(f"  Min effective ID coverage ratio: {min_eff:.3f}")
        print(f"  Remaining IDs: {len(pending_ids)}")

        if args.delete_downloaded_product:
            deleted = cleanup_downloaded_product(download_dir, product_name)
            print(f"  Cleanup deleted {deleted} paths from download dir")

    print(f"Search results: {len(results_df)}")
    print(f"Products processed: {processed_products}")
    print(f"Total H5 crops written: {all_written}")
    print(f"Input IDs: {len(ids)}")
    print(f"Matched IDs: {len(footprints)}")
    print(f"Missing IDs: {len(missing_ids)}")
    if missing_ids:
        print("Missing list:", ", ".join(missing_ids))
    print(f"Uncovered IDs after processing: {len(pending_ids)}")
    if pending_ids:
        print("Uncovered list:", ", ".join(sorted(pending_ids)))

    merged = merge_core_metadata_parquets(Path(args.crops_dir) / "DB")
    if merged is not None:
        print(f"Merged parquet: {merged}")


if __name__ == "__main__":
    main()
