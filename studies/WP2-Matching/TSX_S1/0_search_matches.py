#!/usr/bin/env python3
"""
Pipeline step 0: search for matching Sentinel-1 products for TSX archive entries.

Reads a TSX archive CSV, searches for matching Sentinel-1 SLC products within
specified temporal and spatial thresholds, and saves results as a parquet file.
"""

import argparse
import asyncio
from ast import literal_eval
from datetime import datetime
from pathlib import Path

import pandas as pd
from phidown.search import CopernicusDataSearcher
from shapely import wkt
from shapely.geometry import shape
from tqdm import tqdm


def parse_bbox(bbox_value):
    """Parse bbox value and validate order [minlon, minlat, maxlon, maxlat]."""
    bbox = literal_eval(bbox_value) if isinstance(bbox_value, str) else bbox_value
    if not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
        raise ValueError(f"Invalid bbox: {bbox_value}")
    min_lon, min_lat, max_lon, max_lat = bbox
    in_180 = -180 <= min_lon <= 180 and -180 <= max_lon <= 180
    if not in_180:
        raise ValueError(f"Invalid lon range in bbox: {bbox}")
    if not (-90 <= min_lat <= 90 and -90 <= max_lat <= 90):
        raise ValueError(f"Invalid lat range in bbox: {bbox}")
    if min_lon > max_lon or min_lat > max_lat:
        raise ValueError(f"Invalid bbox ordering: {bbox}")
    return [min_lon, min_lat, max_lon, max_lat]


def bbox_to_wkt(bbox):
    return (
        f"POLYGON(({bbox[0]} {bbox[1]}, {bbox[2]} {bbox[1]}, "
        f"{bbox[2]} {bbox[3]}, {bbox[0]} {bbox[3]}, {bbox[0]} {bbox[1]}))"
    )


async def search_async(*, aoi_wkt, start_date, end_date, spatial_threshold, s1_mode, s1_product_type):
    """Search for Sentinel-1 SLC products with optional spatial filtering (async)."""
    loop = asyncio.get_running_loop()
    searcher = CopernicusDataSearcher()

    searcher.query_by_filter(
        collection_name="SENTINEL-1",
        product_type=s1_product_type,
        orbit_direction=None,
        cloud_cover_threshold=None,
        aoi_wkt=aoi_wkt,
        start_date=start_date,
        end_date=end_date,
        top=1000,
        count=True,
        attributes={
            "processingLevel": "LEVEL1",
            "operationalMode": s1_mode,
        },
    )

    out = await loop.run_in_executor(None, searcher.execute_query)

    if out is None or len(out) == 0:
        return pd.DataFrame()

    if spatial_threshold is not None and aoi_wkt is not None:
        poly = wkt.loads(aoi_wkt)

        def calculate_coverage(row, poly_ref):
            footprint_geojson = row.get("GeoFootprint")
            if footprint_geojson is None:
                return 0.0
            footprint = shape(footprint_geojson)
            if poly_ref.is_empty:
                return 0.0
            intersection_area = footprint.intersection(poly_ref).area
            poly_area = poly_ref.area
            return intersection_area / poly_area if poly_area > 0 else 0.0

        out = out.copy()
        out["coverage"] = out.apply(lambda row: calculate_coverage(row, poly), axis=1)
        out = out[out["coverage"] >= spatial_threshold]
        return out.reset_index(drop=True)

    out = out.copy()
    out["coverage"] = None
    return out


def extract_quickinfo(row):
    """Extract temporal window and AOI WKT from a TSX row."""
    fmt = lambda s: s.split(".")[0]
    start = fmt(row["start_datetime"])
    end = fmt(row["end_datetime"])
    bbox = parse_bbox(row["bbox"])
    return {
        "start_date": start,
        "end_date": end,
        "aoi_wkt": bbox_to_wkt(bbox),
    }


def expand_date_range(info, threshold_days):
    """Expand the date range by half of threshold_days on each side."""
    start_dt = datetime.strptime(info["start_date"], "%Y-%m-%dT%H:%M:%S")
    end_dt = datetime.strptime(info["end_date"], "%Y-%m-%dT%H:%M:%S")
    padding = pd.Timedelta(days=threshold_days // 2)
    expanded_start = (start_dt - padding).strftime("%Y-%m-%dT%H:%M:%S")
    expanded_end = (end_dt + padding).strftime("%Y-%m-%dT%H:%M:%S")
    return expanded_start, expanded_end


async def process_tsx_row(row, spatial_threshold, threshold_days, s1_mode, s1_product_type):
    """Process a single TSX row and search for matching S1 products."""
    matches = []
    info = extract_quickinfo(row)
    expanded_start, expanded_end = expand_date_range(info, threshold_days)

    try:
        out = await search_async(
            aoi_wkt=info["aoi_wkt"],
            start_date=expanded_start,
            end_date=expanded_end,
            spatial_threshold=spatial_threshold,
            s1_mode=s1_mode,
            s1_product_type=s1_product_type,
        )

        if len(out) > 0:
            for _, s1_row in out.iterrows():
                matches.append(
                    {
                        "tsx_id": row["id"],
                        "tsx_start_datetime": row["start_datetime"],
                        "tsx_end_datetime": row["end_datetime"],
                        "tsx_bbox": row["bbox"],
                        "s1_name": s1_row.get("Name"),
                        "s1_id": s1_row.get("Id"),
                        "s1_start_date": s1_row.get("ContentDate", {}).get("Start"),
                        "s1_end_date": s1_row.get("ContentDate", {}).get("End"),
                        "s1_footprint": str(s1_row.get("GeoFootprint")),
                        "spatial_overlap": s1_row.get("coverage"),
                        "time_window_days": threshold_days,
                        "s1_mode": s1_mode,
                        "s1_product_type": s1_product_type,
                    }
                )
    except Exception as exc:
        return {"error": str(exc), "tsx_id": row.get("id")}

    return matches


async def process_chunk(chunk_df, spatial_threshold, threshold_days, s1_mode, s1_product_type, chunk_idx, pbar):
    """Process a chunk of TSX rows concurrently."""
    tasks = [
        process_tsx_row(row, spatial_threshold, threshold_days, s1_mode, s1_product_type)
        for _, row in chunk_df.iterrows()
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    all_matches = []
    errors = 0

    for result in results:
        pbar.update(1)
        if isinstance(result, Exception):
            errors += 1
            tqdm.write(f"Exception in chunk {chunk_idx}: {result}")
        elif isinstance(result, dict) and "error" in result:
            errors += 1
            tqdm.write(f"Error for TSX ID {result.get('tsx_id')}: {result.get('error')}")
        elif isinstance(result, list):
            all_matches.extend(result)

    return all_matches, errors


def save_chunk_results(matches, output_path, chunk_idx):
    if not matches:
        return None
    chunk_df = pd.DataFrame(matches)
    part_file = output_path.parent / f"{output_path.stem}_part_{chunk_idx:04d}.parquet"
    chunk_df.to_parquet(part_file, index=False)
    print(f"\nSaved part {chunk_idx} with {len(matches)} matches to {part_file}")
    return part_file


async def async_main(args):
    output_path = Path(args.output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    db = pd.read_csv(args.db_path)
    print(f"Loaded {len(db)} TSX products from {args.db_path}")

    print("\nSearch parameters:")
    print(f"  Spatial threshold: {args.spatial_threshold}")
    print(f"  Temporal threshold: {args.threshold_days} days")
    print(f"  S1 mode: {args.s1_mode}")
    print(f"  S1 product type: {args.s1_product_type}\n")

    total_matches = 0
    total_errors = 0
    chunk_size = args.chunk_size
    num_chunks = (len(db) + chunk_size - 1) // chunk_size

    with tqdm(total=len(db), desc="Processing TSX products") as pbar:
        for chunk_idx in range(num_chunks):
            start_idx = chunk_idx * chunk_size
            end_idx = min((chunk_idx + 1) * chunk_size, len(db))
            chunk_df = db.iloc[start_idx:end_idx]

            tqdm.write(
                f"\nProcessing chunk {chunk_idx + 1}/{num_chunks} (rows {start_idx}-{end_idx})..."
            )

            matches, errors = await process_chunk(
                chunk_df,
                args.spatial_threshold,
                args.threshold_days,
                args.s1_mode,
                args.s1_product_type,
                chunk_idx,
                pbar,
            )

            save_chunk_results(matches, output_path, chunk_idx)
            total_matches += len(matches)
            total_errors += errors

            tqdm.write(
                f"Chunk {chunk_idx + 1} complete: {len(matches)} matches found "
                f"(total: {total_matches}, errors: {total_errors})"
            )

    print("\nProcessing complete!")
    print(f"Total TSX products processed: {len(db)}")
    print(f"Total matches found: {total_matches}")
    print(f"Total errors: {total_errors}")

    print("\nMerging parts into final file...")
    part_files = sorted(output_path.parent.glob(f"{output_path.stem}_part_*.parquet"))

    if part_files:
        all_parts = [pd.read_parquet(f) for f in part_files]
        final_df = pd.concat(all_parts, ignore_index=True)
        final_df.to_parquet(output_path, index=False)
        print(f"Saved final file with {len(final_df)} matches to {output_path}")

        for part_file in part_files:
            part_file.unlink()
        print(f"Cleaned up {len(part_files)} part files")
    else:
        print("No matches found!")


def main():
    base_dir = Path(__file__).resolve().parent
    default_db = base_dir / "footprints_TSX" / "TSX_TSM_SSC_archive_index.csv"
    default_output = base_dir / "deliverable" / "tsx_s1_IW_matches.parquet"

    parser = argparse.ArgumentParser(
        description="Pipeline step 0: search for matching Sentinel-1 products for TSX archive"
    )
    parser.add_argument(
        "--db-path",
        type=str,
        default=str(default_db),
        help="Path to TSX archive CSV file",
    )
    parser.add_argument(
        "--output-path",
        type=str,
        default=str(default_output),
        help="Output path for parquet file (will be split into parts)",
    )
    parser.add_argument(
        "--spatial-threshold",
        type=float,
        default=0.85,
        help="Minimum spatial overlap ratio (0-1)",
    )
    parser.add_argument(
        "--threshold-days",
        type=int,
        default=7,
        help="Temporal threshold in days",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=500,
        help="Number of TSX rows to process per chunk",
    )
    parser.add_argument(
        "--s1-mode",
        type=str,
        default="IW",
        help="Sentinel-1 operational mode (e.g., IW, EW)",
    )
    parser.add_argument(
        "--s1-product-type",
        type=str,
        default="SLC",
        help="Sentinel-1 product type (e.g., SLC)",
    )

    args = parser.parse_args()
    args.s1_mode = args.s1_mode.upper()

    if args.output_path == str(default_output) and args.s1_mode != "IW":
        args.output_path = str(base_dir / "deliverable" / f"tsx_s1_{args.s1_mode}_matches.parquet")

    asyncio.run(async_main(args))


if __name__ == "__main__":
    main()
