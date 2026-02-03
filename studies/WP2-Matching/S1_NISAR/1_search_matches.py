#!/usr/bin/env python3
"""
Pipeline step 1: search for matching Sentinel-1 products for NISAR GSLC entries.

Reads a NISAR CSV (from 0_retrieve_NISAR_products.py), searches for matching
Sentinel-1 SLC products within specified temporal/spatial thresholds, and
saves results as a parquet file.
"""

import argparse
import asyncio
from pathlib import Path

import pandas as pd
from phidown.search import CopernicusDataSearcher
from shapely import wkt
from shapely.geometry import shape
from tqdm import tqdm


def parse_wkt_safe(wkt_value):
    if wkt_value is None or pd.isna(wkt_value):
        return None
    if hasattr(wkt_value, "geom_type"):
        return wkt_value
    if not isinstance(wkt_value, str):
        raise ValueError(f"Invalid WKT value: {wkt_value}")
    geom = wkt.loads(wkt_value)
    if geom.is_empty:
        raise ValueError("Empty geometry from WKT")
    return geom


def parse_time_safe(value, label):
    dt = pd.to_datetime(value, errors="coerce", utc=True)
    if pd.isna(dt):
        raise ValueError(f"Invalid {label}: {value}")
    return dt


def expand_date_range(start_dt, end_dt, threshold_days):
    padding = pd.Timedelta(days=threshold_days / 2)
    expanded_start = (start_dt - padding).strftime("%Y-%m-%dT%H:%M:%S")
    expanded_end = (end_dt + padding).strftime("%Y-%m-%dT%H:%M:%S")
    return expanded_start, expanded_end


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
            # Use operationalMode for Sentinel-1 mode filtering; processingLevel filters
            # in CDSE were eliminating valid SLC results.
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
            intersection = footprint.intersection(poly_ref)
            if intersection.is_empty:
                return 0.0
            min_area = min(footprint.area, poly_ref.area)
            return intersection.area / min_area if min_area > 0 else 0.0

        out = out.copy()
        out["coverage"] = out.apply(lambda row: calculate_coverage(row, poly), axis=1)
        out = out[out["coverage"] >= spatial_threshold]
        return out.reset_index(drop=True)

    out = out.copy()
    out["coverage"] = None
    return out


def extract_quickinfo(row):
    start = parse_time_safe(row.get("startTime_utc"), "startTime_utc")
    end = parse_time_safe(row.get("stopTime_utc"), "stopTime_utc")
    geom = parse_wkt_safe(row.get("WKT"))
    if geom is None:
        raise ValueError(f"Missing WKT geometry for NISAR scene {row.get('sceneName')}")
    return {
        "start_dt": start,
        "end_dt": end,
        "aoi_wkt": geom.wkt,
    }


async def process_nisar_row(row, spatial_threshold, threshold_days, s1_mode, s1_product_type):
    matches = []
    info = extract_quickinfo(row)
    expanded_start, expanded_end = expand_date_range(
        info["start_dt"], info["end_dt"], threshold_days
    )

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
            start_str = info["start_dt"].strftime("%Y-%m-%dT%H:%M:%S")
            end_str = info["end_dt"].strftime("%Y-%m-%dT%H:%M:%S")
            for _, s1_row in out.iterrows():
                matches.append(
                    {
                        "nisar_scene_name": row.get("sceneName"),
                        "nisar_file_id": row.get("fileID"),
                        "nisar_platform": row.get("platform"),
                        "nisar_processing_level": row.get("processingLevel"),
                        "nisar_beam_mode": row.get("beamMode"),
                        "nisar_polarization": row.get("polarization"),
                        "nisar_flight_direction": row.get("flightDirection"),
                        "nisar_start_time": start_str,
                        "nisar_stop_time": end_str,
                        "nisar_duration_s": row.get("duration_s"),
                        "nisar_wkt": row.get("WKT"),
                        "nisar_centroid_lon": row.get("centroid_lon"),
                        "nisar_centroid_lat": row.get("centroid_lat"),
                        "nisar_url": row.get("url"),
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
        return {"error": str(exc), "nisar_scene_name": row.get("sceneName")}

    return matches


async def process_chunk(chunk_df, spatial_threshold, threshold_days, s1_mode, s1_product_type, chunk_idx, pbar):
    tasks = [
        process_nisar_row(row, spatial_threshold, threshold_days, s1_mode, s1_product_type)
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
            tqdm.write(
                f"Error for NISAR scene {result.get('nisar_scene_name')}: {result.get('error')}"
            )
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


def find_latest_csv(base_dir, pattern="nisar_gslc_*.csv"):
    candidates = sorted(base_dir.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0] if candidates else None


async def async_main(args):
    output_path = Path(args.output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    db_path = Path(args.db_path)
    db = pd.read_csv(db_path)
    print(f"Loaded {len(db)} NISAR products from {db_path}")

    print("\nSearch parameters:")
    print(f"  Spatial threshold: {args.spatial_threshold}")
    print(f"  Temporal threshold: {args.threshold_days} days")
    print(f"  S1 mode: {args.s1_mode}")
    print(f"  S1 product type: {args.s1_product_type}\n")

    total_matches = 0
    total_errors = 0
    chunk_size = args.chunk_size
    num_chunks = (len(db) + chunk_size - 1) // chunk_size

    with tqdm(total=len(db), desc="Processing NISAR products") as pbar:
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
    print(f"Total NISAR products processed: {len(db)}")
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
    latest_csv = find_latest_csv(base_dir)
    default_db = str(latest_csv) if latest_csv else ""
    default_output = base_dir / "deliverable" / "nisar_s1_IW_matches.parquet"

    parser = argparse.ArgumentParser(
        description="Pipeline step 1: search for matching Sentinel-1 products for NISAR GSLC archive"
    )
    parser.add_argument(
        "--db-path",
        type=str,
        default=default_db,
        help="Path to NISAR GSLC CSV file (defaults to latest nisar_gslc_*.csv)",
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
        default=0.6,
        help="Minimum spatial overlap ratio (intersection / min footprint area)",
    )
    parser.add_argument(
        "--threshold-days",
        type=int,
        default=30,
        help="Temporal threshold in days",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=300,
        help="Number of NISAR rows to process per chunk",
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

    if not args.db_path:
        raise FileNotFoundError(
            f"No NISAR CSV found in {base_dir}. Run 0_retrieve_NISAR_products.py first."
        )

    if args.output_path == str(default_output) and args.s1_mode != "IW":
        args.output_path = str(
            base_dir / "deliverable" / f"nisar_s1_{args.s1_mode}_matches.parquet"
        )

    asyncio.run(async_main(args))


if __name__ == "__main__":
    main()
