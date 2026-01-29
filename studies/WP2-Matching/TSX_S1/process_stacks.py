import pandas as pd
import os
from pathlib import Path

def main():
    output_dir = Path('/Users/roberto.delprete/Library/CloudStorage/OneDrive-ESA/Desktop/Repos/WORLDSAR/studies/WP2-Matching/TSX_S1/output')
    deliverable_dir = Path('/Users/roberto.delprete/Library/CloudStorage/OneDrive-ESA/Desktop/Repos/WORLDSAR/studies/WP2-Matching/TSX_S1/deliverable')
    deliverable_dir.mkdir(exist_ok=True)

    stack_info = []

    for csv_file in output_dir.glob('stack_*.csv'):
        stack_id = int(csv_file.stem.split('_')[1])
        stack_df = pd.read_csv(csv_file)
        num_products = len(stack_df)
        if num_products > 4:
            start_date = pd.to_datetime(stack_df['tsx_start_datetime']).min()
            end_date = pd.to_datetime(stack_df['tsx_start_datetime']).max()
            duration_days = (end_date - start_date).days
            if duration_days >= 365:
                stack_info.append({
                    'stack_id': stack_id,
                    'num_products': num_products,
                    'start_date': start_date,
                    'end_date': end_date,
                    'duration_days': duration_days
                })

    stack_summary_df = pd.DataFrame(stack_info).sort_values('stack_id')
    parquet_path = deliverable_dir / 'tsx_stacks_one_year.parquet'
    stack_summary_df.to_parquet(parquet_path, index=False)
    print(f"Saved {len(stack_summary_df)} stacks to {parquet_path}")

    # Create markdown documentation
    md_content = f"""# TSX Temporal Stacks Analysis

## Overview
This document describes the TSX temporal stacks that cover at least one year and contain more than 4 products.

## Summary
- Total stacks analyzed: {len(list(output_dir.glob('stack_*.csv')))}
- Stacks meeting criteria (>=1 year, >4 products): {len(stack_summary_df)}

## Stack Details
{stack_summary_df.to_markdown(index=False)}

## Methodology
- Stacks are derived from TSX products with >=80% spatial overlap.
- Coverage is calculated as the difference between the earliest and latest acquisition dates.
- Only stacks with >4 products and >=365 days coverage are included.
"""
    md_path = deliverable_dir / 'tsx_stacks_documentation.md'
    with open(md_path, 'w') as f:
        f.write(md_content)
    print(f"Documentation saved to {md_path}")

if __name__ == "__main__":
    main()