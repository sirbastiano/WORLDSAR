import pandas as pd
from pathlib import Path

def main():
    deliverable_dir = Path('/Users/roberto.delprete/Library/CloudStorage/OneDrive-ESA/Desktop/Repos/WORLDSAR/studies/WP2-Matching/TSX_S1/deliverable')
    output_dir = Path('/Users/roberto.delprete/Library/CloudStorage/OneDrive-ESA/Desktop/Repos/WORLDSAR/studies/WP2-Matching/TSX_S1/output')
    parquet_path = deliverable_dir / 'tsx_stacks_one_year.parquet'
    df = pd.read_parquet(parquet_path)
    
    # Add product names
    product_lists = []
    for stack_id in df['stack_id']:
        stack_csv = output_dir / f'stack_{stack_id}.csv'
        if stack_csv.exists():
            stack_df = pd.read_csv(stack_csv)
            products = stack_df['tsx_id'].tolist()
            product_lists.append(products)
        else:
            product_lists.append([])
    
    df['product_names'] = product_lists
    
    # Total TSX products
    total_products = df['num_products'].sum()
    print(f"Total TSX products in stacks: {total_products}")
    
    # Save to CSV
    csv_path = deliverable_dir / 'tsx_stacks_one_year.csv'
    df.to_csv(csv_path, index=False)
    print(f"Saved to CSV: {csv_path}")
    
    # Update markdown
    md_path = deliverable_dir / 'S1IW_tsx_stacks_documentation.md'
    with open(md_path, 'r') as f:
        content = f.read()
    
    # Add total products
    new_content = content.replace(
        "## Summary\n- Total stacks analyzed: ",
        f"## Summary\n- Total TSX products in stacks: {total_products}\n- Total stacks analyzed: "
    )
    
    with open(md_path, 'w') as f:
        f.write(new_content)
    print(f"Updated markdown: {md_path}")

if __name__ == "__main__":
    main()