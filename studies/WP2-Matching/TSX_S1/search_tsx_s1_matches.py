#!/usr/bin/env python3
"""
Script to search for matching Sentinel-1 products for TSX archive.

This script reads a TSX archive CSV, searches for matching Sentinel-1 SLC products
within specified temporal and spatial thresholds, and saves the results as parquet files.

The script processes the TSX database in chunks (default 500 rows), executes concurrent
async queries for each TSX product, and saves intermediate results as part files before
merging into a final output.

Usage Examples:
    Basic usage with required output path:
        $ python search_tsx_s1_matches.py --output-path results/matches.parquet

    Custom TSX database path:
        $ python search_tsx_s1_matches.py \
            --db-path /path/to/tsx_archive.csv \
            --output-path results/matches.parquet

    Adjust spatial and temporal thresholds:
        $ python search_tsx_s1_matches.py \
            --output-path results/matches.parquet \
            --spatial-threshold 0.9 \
            --threshold-days 14

    Process larger chunks (more memory, faster):
        $ python search_tsx_s1_matches.py \
            --output-path results/matches.parquet \
            --chunk-size 1000

    Full example with all parameters:
        $ python search_tsx_s1_matches.py \
            --db-path /Users/user/WORLDSAR/DB/footprints_TSX/TSX_archive.csv \
            --output-path /Users/user/WORLDSAR/results/tsx_s1_matches.parquet \
            --spatial-threshold 0.85 \
            --threshold-days 7 \
            --chunk-size 500

Output:
    - Intermediate part files: {output_path}_part_0000.parquet, _part_0001.parquet, etc.
    - Final merged file: {output_path}
    - Part files are automatically cleaned up after merge

Performance Notes:
    - Each chunk processes rows concurrently using asyncio
    - Larger chunk-size values use more memory but may be faster
    - Part files allow recovery if script is interrupted
    - Default chunk size (500) balances memory usage and performance

Required CSV Columns:
    The TSX database CSV must contain:
        - id: Unique identifier for TSX product
        - start_datetime: Start datetime (ISO format with optional microseconds)
        - end_datetime: End datetime (ISO format with optional microseconds)
        - bbox: Bounding box as string representation of list [minlon, minlat, maxlon, maxlat]
"""

import argparse
import asyncio
import pandas as pd
from datetime import datetime
from ast import literal_eval
from pathlib import Path
from phidown.search import CopernicusDataSearcher
from shapely.geometry import shape
from shapely import wkt
from tqdm import tqdm


async def search_async(aoi_wkt=None, start_date='2023-05-03T00:00:00', end_date='2024-05-03T04:00:00', spatial_threshold=None):
    """
    Search for Sentinel-1 SLC products with optional spatial filtering (async version).

    Args:
        aoi_wkt (str): Area of interest in WKT format (e.g., 'POLYGON(...)').
        start_date (str): Start date in 'YYYY-MM-DDTHH:MM:SS' format.
        end_date (str): End date in 'YYYY-MM-DDTHH:MM:SS' format.
        spatial_threshold (float): Minimum overlap ratio (0-1) between product footprint and AOI.

    Returns:
        pandas.DataFrame: Search results with 'coverage' column, optionally filtered by spatial overlap.
    """
    loop = asyncio.get_event_loop()
    searcher = CopernicusDataSearcher()
    
    # Configure the search parameters
    searcher.query_by_filter(
        collection_name='SENTINEL-1',
        product_type='SLC',
        orbit_direction=None,
        cloud_cover_threshold=None,
        aoi_wkt=aoi_wkt,
        start_date=start_date,
        end_date=end_date,
        top=1000,
        count=True,
        attributes={
            'processingLevel': 'LEVEL1',
            'operationalMode': 'EW'
        } 
    )
    
    # Execute query in thread pool to avoid blocking
    out = await loop.run_in_executor(None, searcher.execute_query)
    
    # Check if results are empty
    if out is None or len(out) == 0:
        return pd.DataFrame()
    
    if spatial_threshold is not None and aoi_wkt is not None:
        # WKT string -> shapely Polygon
        poly = wkt.loads(aoi_wkt)
        
        def calculate_coverage(row, poly):
            # GeoJSON dict -> shapely Polygon
            footprint_geojson = row['GeoFootprint']
            if footprint_geojson is None:
                return 0.0
            footprint = shape(footprint_geojson)
            intersection_area = footprint.intersection(poly).area
            poly_area = poly.area
            if poly_area == 0:
                return 0.0
            overlap_ratio = intersection_area / poly_area
            return overlap_ratio
        
        # Add coverage column
        out['coverage'] = out.apply(lambda row: calculate_coverage(row, poly), axis=1)
        
        # Filter by threshold
        filtered_out = out[out['coverage'] >= spatial_threshold]
        return filtered_out.reset_index(drop=True)
    
    return out


def extract_quickinfo(row):
    """
    Extract quick info from a dataframe row.

    Args:
        row (pandas.Series): Row containing 'start_datetime' and 'end_datetime', and 'bbox'.

    Returns:
        dict: Dictionary with formatted start and end dates, and area of interest (AOI).
    """
    # Date format YYYY-MM-DDTHH:MM:SS from 2025-10-26T13:56:11.965035Z
    fmt = lambda s: s.split('.')[0]
    start, end = fmt(row['start_datetime']), fmt(row['end_datetime'])
    
    # bbox to WKT
    bbox_to_wkt = lambda b: (f'POLYGON(({b[0]} {b[1]}, {b[2]} {b[1]}, '
                             f'{b[2]} {b[3]}, {b[0]} {b[3]}, {b[0]} {b[1]}))')
    aoi = bbox_to_wkt(literal_eval(row['bbox']))
    
    return {
        'start_date': start,
        'end_date': end,
        'aoi_wkt': aoi
    }


def get_expanded_date_range(info, threshold_days):
    """
    Expand the date range by half of threshold_days on each side.

    Args:
        info (dict): Dictionary with 'start_date' and 'end_date' keys.
        threshold_days (int): Number of days to expand (total).

    Returns:
        tuple[str, str]: Expanded start and end dates in 'YYYY-MM-DDTHH:MM:SS' format.
    """
    start_dt = datetime.strptime(info['start_date'], '%Y-%m-%dT%H:%M:%S')
    end_dt = datetime.strptime(info['end_date'], '%Y-%m-%dT%H:%M:%S')
    expanded_start = (start_dt - pd.Timedelta(days=threshold_days // 2)).strftime('%Y-%m-%dT%H:%M:%S')
    expanded_end = (end_dt + pd.Timedelta(days=threshold_days // 2)).strftime('%Y-%m-%dT%H:%M:%S')
    return expanded_start, expanded_end


async def process_tsx_row(row, spatial_threshold, threshold_days):
    """
    Process a single TSX row and search for matching S1 products.

    Args:
        row (pandas.Series): TSX database row.
        spatial_threshold (float): Minimum spatial overlap ratio.
        threshold_days (int): Temporal threshold in days.

    Returns:
        list: List of match dictionaries for this TSX product.
    """
    matches = []
    
    info = extract_quickinfo(row)
    expanded_start_date, expanded_end_date = get_expanded_date_range(info, threshold_days)
    
    try:
        out = await search_async(
            aoi_wkt=info['aoi_wkt'],
            start_date=expanded_start_date,
            end_date=expanded_end_date, 
            spatial_threshold=spatial_threshold
        )
        
        if len(out) > 0:
            # For each Sentinel-1 match, create a row linking TSX and S1
            for _, s1_row in out.iterrows():
                matches.append({
                    'tsx_id': row['id'],
                    'tsx_start_datetime': row['start_datetime'],
                    'tsx_end_datetime': row['end_datetime'],
                    'tsx_bbox': row['bbox'],
                    's1_name': s1_row['Name'],
                    's1_id': s1_row.get('Id', None),
                    's1_start_date': s1_row.get('ContentDate', {}).get('Start', None),
                    's1_end_date': s1_row.get('ContentDate', {}).get('End', None),
                    's1_footprint': str(s1_row.get('GeoFootprint', None)),
                    'spatial_overlap': s1_row['coverage'],
                    'time_window_set': threshold_days
                })
    except Exception as e:
        # Return error info as part of result
        return {'error': str(e), 'tsx_id': row['id']}
    
    return matches


async def process_chunk(chunk_df, spatial_threshold, threshold_days, chunk_idx, pbar):
    """
    Process a chunk of TSX database rows concurrently.

    Args:
        chunk_df (pandas.DataFrame): Chunk of TSX database to process.
        spatial_threshold (float): Minimum spatial overlap ratio.
        threshold_days (int): Temporal threshold in days.
        chunk_idx (int): Chunk index for logging.
        pbar (tqdm): Progress bar instance.

    Returns:
        list: List of all matches found in this chunk.
    """
    tasks = []
    for idx, row in chunk_df.iterrows():
        task = process_tsx_row(row, spatial_threshold, threshold_days)
        tasks.append(task)
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    all_matches = []
    errors = 0
    
    for result in results:
        pbar.update(1)
        
        if isinstance(result, Exception):
            errors += 1
            tqdm.write(f'Exception in chunk {chunk_idx}: {str(result)}')
        elif isinstance(result, dict) and 'error' in result:
            errors += 1
            tqdm.write(f'Error for TSX ID {result.get("tsx_id")}: {result.get("error")}')
        elif isinstance(result, list):
            all_matches.extend(result)
    
    return all_matches


def save_chunk_results(matches, output_path, chunk_idx):
    """
    Save chunk results to a part file.

    Args:
        matches (list): List of match dictionaries.
        output_path (Path): Base output path.
        chunk_idx (int): Chunk index for filename.
    """
    if not matches:
        return
    
    chunk_df = pd.DataFrame(matches)
    part_file = output_path.parent / f'{output_path.stem}_part_{chunk_idx:04d}.parquet'
    chunk_df.to_parquet(part_file, index=False)
    print(f'\nSaved part {chunk_idx} with {len(matches)} matches to {part_file}')


async def async_main(args):
    """
    Async main function to process TSX database.

    Args:
        args: Parsed command line arguments.
    """
    output_path = Path(args.output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Load TSX database
    print(f'Loading TSX database from {args.db_path}...')
    db = pd.read_csv(args.db_path)
    print(f'Loaded {len(db)} TSX products')
    
    # Process matches
    print(f'\nSearching with parameters:')
    print(f'  Spatial threshold: {args.spatial_threshold}')
    print(f'  Temporal threshold: {args.threshold_days} days')
    print(f'  Chunk size: {args.chunk_size} rows\n')
    
    total_matches = 0
    chunk_size = args.chunk_size
    num_chunks = (len(db) + chunk_size - 1) // chunk_size
    
    with tqdm(total=len(db), desc='Processing TSX products') as pbar:
        for chunk_idx in range(num_chunks):
            start_idx = chunk_idx * chunk_size
            end_idx = min((chunk_idx + 1) * chunk_size, len(db))
            chunk_df = db.iloc[start_idx:end_idx]
            
            tqdm.write(f'\nProcessing chunk {chunk_idx + 1}/{num_chunks} (rows {start_idx}-{end_idx})...')
            
            matches = await process_chunk(
                chunk_df, 
                args.spatial_threshold, 
                args.threshold_days,
                chunk_idx,
                pbar
            )
            
            # Save chunk results immediately
            save_chunk_results(matches, output_path, chunk_idx)
            total_matches += len(matches)
            
            tqdm.write(f'Chunk {chunk_idx + 1} complete: {len(matches)} matches found (total: {total_matches})')
    
    print(f'\nProcessing complete!')
    print(f'Total TSX products processed: {len(db)}')
    print(f'Total matches found: {total_matches}')
    print(f'Total parts saved: {num_chunks}')
    
    # Merge all parts into final file
    print(f'\nMerging parts into final file...')
    part_files = sorted(output_path.parent.glob(f'{output_path.stem}_part_*.parquet'))
    
    if part_files:
        all_parts = [pd.read_parquet(f) for f in part_files]
        final_df = pd.concat(all_parts, ignore_index=True)
        final_df.to_parquet(output_path, index=False)
        print(f'Saved final file with {len(final_df)} matches to {output_path}')
        
        # Clean up part files
        for part_file in part_files:
            part_file.unlink()
        print(f'Cleaned up {len(part_files)} part files')
    else:
        print('No matches found!')


def main():
    parser = argparse.ArgumentParser(
        description='Search for matching Sentinel-1 products for TSX archive'
    )
    parser.add_argument(
        '--db-path',
        type=str,
        default='/Users/roberto.delprete/Library/CloudStorage/OneDrive-ESA/Desktop/Repos/WORLDSAR/studies/WP2-Matching/TSX_S1/footprints_TSX/TSX_TSM_SSC_archive_index.csv',
        help='Path to TSX archive CSV file'
    )
    parser.add_argument(
        '--output-path',
        type=str,
        required=True,
        help='Output path for parquet file (will be split into parts)'
    )
    parser.add_argument(
        '--spatial-threshold',
        type=float,
        default=0.85,
        help='Minimum spatial overlap ratio (0-1)'
    )
    parser.add_argument(
        '--threshold-days',
        type=int,
        default=7,
        help='Temporal threshold in days'
    )
    parser.add_argument(
        '--chunk-size',
        type=int,
        default=500,
        help='Number of TSX rows to process per chunk'
    )
    
    args = parser.parse_args()
    
    # Run async main
    asyncio.run(async_main(args))


if __name__ == '__main__':
    main()


