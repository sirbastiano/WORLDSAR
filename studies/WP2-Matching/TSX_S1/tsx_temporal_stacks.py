import pandas as pd
import networkx as nx
from shapely.geometry import Polygon
import ast
import os

def load_matches():
    matches_path = '/Users/roberto.delprete/Library/CloudStorage/OneDrive-ESA/Desktop/Repos/WORLDSAR/studies/WP2-Matching/TSX_S1/deliverable/tsx_s1_IW_matches.parquet'
    return pd.read_parquet(matches_path)

def extract_unique_tsx(matches):
    return matches[['tsx_id', 'tsx_bbox', 'tsx_start_datetime']].drop_duplicates().reset_index(drop=True)

def bbox_to_poly(bbox_str):
    bbox = ast.literal_eval(bbox_str)
    min_lon, min_lat, max_lon, max_lat = bbox
    return Polygon([(min_lon, min_lat), (max_lon, min_lat), (max_lon, max_lat), (min_lon, max_lat)])

def overlap_ratio(poly1, poly2):
    if poly1.is_empty or poly2.is_empty:
        return 0.0
    inter = poly1.intersection(poly2)
    if inter.is_empty:
        return 0.0
    min_area = min(poly1.area, poly2.area)
    return inter.area / min_area if min_area > 0 else 0.0

def build_graph(tsx_df):
    footprints = tsx_df['tsx_bbox'].apply(bbox_to_poly)
    G = nx.Graph()
    ids = tsx_df['tsx_id']
    for idx in ids:
        G.add_node(idx)
    n = len(ids)
    print(f"Processing {n} TSX products")
    for i in range(n):
        for j in range(i+1, n):
            ratio = overlap_ratio(footprints.iloc[i], footprints.iloc[j])
            if ratio >= 0.8:
                G.add_edge(ids.iloc[i], ids.iloc[j])
    return G

def find_temporal_stacks(tsx_df, G):
    stacks = list(nx.connected_components(G))
    temporal_stacks = []
    for stack in stacks:
        stack_df = tsx_df[tsx_df['tsx_id'].isin(stack)].copy()
        stack_df['tsx_start_datetime'] = pd.to_datetime(stack_df['tsx_start_datetime'])
        stack_df = stack_df.sort_values('tsx_start_datetime')
        temporal_stacks.append(stack_df[['tsx_id', 'tsx_start_datetime']])
    return temporal_stacks

def save_stacks(temporal_stacks, output_dir='./output'):
    os.makedirs(output_dir, exist_ok=True)
    for idx, stack in enumerate(temporal_stacks):
        if len(stack) > 1:
            stack.to_csv(f'{output_dir}/stack_{idx+1}.csv', index=False)
    print(f"Stacks saved to {output_dir}")

def main():
    matches = load_matches()
    tsx_df = extract_unique_tsx(matches)
    print(f"Unique TSX products: {len(tsx_df)}")
    G = build_graph(tsx_df)
    temporal_stacks = find_temporal_stacks(tsx_df, G)
    print(f"Found {len(temporal_stacks)} temporal stacks")
    print(f"Stacks with >1 product: {len([s for s in temporal_stacks if len(s) > 1])}")
    save_stacks(temporal_stacks)
    # Print example stacks
    for idx, stack in enumerate(temporal_stacks):
        if len(stack) > 1 and idx < 5:  # Print first 5 multi-product stacks
            print(f"\nStack {idx+1}: {len(stack)} products")
            print(stack.to_string())

    # Collect stacks covering at least one year
    stack_info = []
    for idx, stack in enumerate(temporal_stacks):
        if len(stack) > 1:
            start = stack['tsx_start_datetime'].min()
            end = stack['tsx_start_datetime'].max()
            duration = (end - start).days
            if duration >= 365:
                stack_info.append({
                    'stack_id': idx + 1,
                    'num_products': len(stack),
                    'start_date': start,
                    'end_date': end,
                    'duration_days': duration
                })
    stack_df = pd.DataFrame(stack_info)
    output_path = '/Users/roberto.delprete/Library/CloudStorage/OneDrive-ESA/Desktop/Repos/WORLDSAR/studies/WP2-Matching/TSX_S1/deliverable/tsx_stacks_one_year.parquet'
    stack_df.to_parquet(output_path, index=False)
    print(f"Saved {len(stack_df)} stacks covering at least one year to {output_path}")

if __name__ == "__main__":
    main()