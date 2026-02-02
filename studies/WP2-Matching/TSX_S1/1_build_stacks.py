#!/usr/bin/env python3
"""
Pipeline step 1: build TSX temporal stacks from TSX-S1 matches.

Outputs:
- stack CSV files in output/ (stack_{id}.csv)
- summary parquet/CSV in deliverable/
- markdown documentation in deliverable/
"""

import argparse
from pathlib import Path

import ast
import networkx as nx
import pandas as pd
from shapely.geometry import Polygon


def load_matches(matches_path):
    return pd.read_parquet(matches_path)


def extract_unique_tsx(matches):
    cols = ["tsx_id", "tsx_bbox", "tsx_start_datetime"]
    return matches[cols].drop_duplicates().reset_index(drop=True)


def bbox_to_poly(bbox_str):
    bbox = ast.literal_eval(bbox_str) if isinstance(bbox_str, str) else bbox_str
    min_lon, min_lat, max_lon, max_lat = bbox
    return Polygon(
        [
            (min_lon, min_lat),
            (max_lon, min_lat),
            (max_lon, max_lat),
            (min_lon, max_lat),
        ]
    )


def overlap_ratio(poly1, poly2):
    if poly1.is_empty or poly2.is_empty:
        return 0.0
    inter = poly1.intersection(poly2)
    if inter.is_empty:
        return 0.0
    min_area = min(poly1.area, poly2.area)
    return inter.area / min_area if min_area > 0 else 0.0


def build_graph(tsx_df, overlap_threshold):
    footprints = tsx_df["tsx_bbox"].apply(bbox_to_poly)
    G = nx.Graph()
    ids = tsx_df["tsx_id"].tolist()
    for tsx_id in ids:
        G.add_node(tsx_id)
    n = len(ids)
    print(f"Processing {n} TSX products for spatial overlap")
    for i in range(n):
        for j in range(i + 1, n):
            ratio = overlap_ratio(footprints.iloc[i], footprints.iloc[j])
            if ratio >= overlap_threshold:
                G.add_edge(ids[i], ids[j])
    return G


def find_temporal_stacks(tsx_df, graph):
    stacks = list(nx.connected_components(graph))
    temporal_stacks = []
    for stack in stacks:
        stack_df = tsx_df[tsx_df["tsx_id"].isin(stack)].copy()
        stack_df["tsx_start_datetime"] = pd.to_datetime(stack_df["tsx_start_datetime"])
        stack_df = stack_df.sort_values("tsx_start_datetime")
        temporal_stacks.append(stack_df[["tsx_id", "tsx_start_datetime", "tsx_bbox"]])
    return temporal_stacks


def save_stacks(temporal_stacks, output_dir):
    output_dir.mkdir(parents=True, exist_ok=True)
    saved = 0
    for idx, stack in enumerate(temporal_stacks, start=1):
        if len(stack) > 1:
            stack.to_csv(output_dir / f"stack_{idx}.csv", index=False)
            saved += 1
    print(f"Stacks saved: {saved} files in {output_dir}")


def summarize_stacks(temporal_stacks, min_products, min_days):
    stack_info = []
    for idx, stack in enumerate(temporal_stacks, start=1):
        if len(stack) < min_products:
            continue
        start = stack["tsx_start_datetime"].min()
        end = stack["tsx_start_datetime"].max()
        duration = (end - start).days
        if duration >= min_days:
            stack_info.append(
                {
                    "stack_id": idx,
                    "num_products": len(stack),
                    "start_date": start,
                    "end_date": end,
                    "duration_days": duration,
                }
            )
    return pd.DataFrame(stack_info)


def write_documentation(output_dir, summary_df, total_stacks, overlap_threshold, min_products, min_days):
    md_content = f"""# TSX Temporal Stacks Analysis

## Overview
This document describes the TSX temporal stacks that cover at least {min_days} days
and contain at least {min_products} products.

## Summary
- Total stacks analyzed: {total_stacks}
- Stacks meeting criteria: {len(summary_df)}

## Stack Details
{summary_df.to_markdown(index=False) if not summary_df.empty else 'No stacks met the criteria.'}

## Methodology
- Stacks are derived from TSX products with >= {overlap_threshold:.2f} spatial overlap.
- Coverage is calculated as the difference between the earliest and latest acquisition dates.
"""
    md_path = output_dir / "tsx_stacks_documentation.md"
    md_path.write_text(md_content)
    print(f"Documentation saved to {md_path}")


def main():
    base_dir = Path(__file__).resolve().parent
    default_matches = base_dir / "deliverable" / "tsx_s1_IW_matches.parquet"
    default_output = base_dir / "output"
    default_deliverable = base_dir / "deliverable"

    parser = argparse.ArgumentParser(
        description="Pipeline step 1: build TSX temporal stacks from TSX-S1 matches"
    )
    parser.add_argument(
        "--matches-path",
        type=str,
        default=str(default_matches),
        help="Path to TSX-S1 matches parquet",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=str(default_output),
        help="Directory for stack CSV files",
    )
    parser.add_argument(
        "--deliverable-dir",
        type=str,
        default=str(default_deliverable),
        help="Directory for summary outputs",
    )
    parser.add_argument(
        "--overlap-threshold",
        type=float,
        default=0.8,
        help="Minimum overlap ratio to connect products",
    )
    parser.add_argument(
        "--min-products",
        type=int,
        default=5,
        help="Minimum products per stack for summary",
    )
    parser.add_argument(
        "--min-days",
        type=int,
        default=365,
        help="Minimum temporal coverage in days for summary",
    )

    args = parser.parse_args()

    matches = load_matches(args.matches_path)
    tsx_df = extract_unique_tsx(matches)
    print(f"Unique TSX products: {len(tsx_df)}")

    graph = build_graph(tsx_df, args.overlap_threshold)
    temporal_stacks = find_temporal_stacks(tsx_df, graph)
    print(f"Found {len(temporal_stacks)} temporal stacks")
    print(f"Stacks with >1 product: {len([s for s in temporal_stacks if len(s) > 1])}")

    output_dir = Path(args.output_dir)
    save_stacks(temporal_stacks, output_dir)

    summary_df = summarize_stacks(temporal_stacks, args.min_products, args.min_days)

    deliverable_dir = Path(args.deliverable_dir)
    deliverable_dir.mkdir(parents=True, exist_ok=True)
    parquet_path = deliverable_dir / "tsx_stacks_one_year.parquet"
    csv_path = deliverable_dir / "tsx_stacks_one_year.csv"

    summary_df.to_parquet(parquet_path, index=False)
    summary_df.to_csv(csv_path, index=False)
    print(f"Saved {len(summary_df)} stacks to {parquet_path}")
    print(f"Saved summary CSV to {csv_path}")

    write_documentation(
        deliverable_dir,
        summary_df,
        total_stacks=len(temporal_stacks),
        overlap_threshold=args.overlap_threshold,
        min_products=args.min_products,
        min_days=args.min_days,
    )


if __name__ == "__main__":
    main()
