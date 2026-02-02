# TSX-S1 Stack Visualizations

This directory contains interactive HTML maps and statistics for TSX-S1 matched stacks.

## Generated Files

### Main Entry Point
- **[index.html](index.html)** - Statistics summary page with links to all visualizations
  - Overview statistics (834 stacks, 22,917 total products)
  - Temporal characteristics (median spacing: 20.3 days)
  - Distribution statistics
  - Top 20 stacks by product count

### Interactive Maps

1. **[tsx_s1_stack_heatmap.html](tsx_s1_stack_heatmap.html)** - Coverage Heatmap
   - Heat intensity shows the number of products per stack location
   - Darker/redder areas indicate higher product density
   - Click on markers for detailed stack information
   - Shows all 834 stacks

2. **[tsx_s1_temporal_frequency.html](tsx_s1_temporal_frequency.html)** - Stack Quality Map
   - Uses 2D color mapping based on BOTH temporal frequency and product count
   - Color scheme (green = best, red = worst):
     - **Dark Green (#006400)**: Excellent (≤15 days, ≥30 products)
     - **Forest Green (#228B22)**: Very Good
     - **Lime Green (#32CD32)**: Good (≤30 days, ≥20 products)
     - **Gold (#FFD700)**: Fair (medium quality)
     - **Orange (#FFA500)**: Poor
     - **Orange Red (#FF4500)**: Very Poor
     - **Dark Red (#8B0000)**: Worst (>50 days, <10 products)
   - Green stacks = frequent revisits + many products = highest quality for analysis
   - Fixed circle size for all markers

3. **[tsx_centroids_heatmap.html](tsx_centroids_heatmap.html)** - TSX Centroids Heatmap
   - Heatmap of all TSX product centroids
   - Shows geographic distribution of TSX acquisitions

4. **[tsx_centroids_clustered.html](tsx_centroids_clustered.html)** - TSX Centroids Clustered
   - Clustered view of TSX product locations
   - Useful for exploring dense areas

### Previous Visualizations
- **tsx_centroids_clustered.html** - Clustered view of TSX centroids
- **tsx_centroids_heatmap.html** - Original heatmap of TSX centroids
- **overlap_vs_time_scatter.png** - Scatter plot of spatial overlap vs temporal window
- **spatial_overlap_hist.png** - Histogram of spatial overlap distribution
- **time_window_hist.png** - Histogram of temporal window distribution

## Key Statistics

- **Total Stacks:** 834
- **Total Products:** 22,917
- **Average Products per Stack:** 27.5
- **Median Products per Stack:** 13
- **Average Temporal Spacing:** 28.4 days
- **Median Temporal Spacing:** 20.3 days

## How to Use

1. Open [index.html](index.html) in a web browser to see the summary statistics
2. Click on the links to open interactive maps:
   - Coverage heatmap shows WHERE products are concentrated
   - Temporal frequency map shows HOW OFTEN products are acquired in each location
3. In the interactive maps:
   - Zoom in/out using mouse wheel or +/- buttons
   - Pan by clicking and dragging
   - Click on markers/circles for detailed information about each stack
   - Toggle layers using the layer control (top right)

## Data Sources

- **Metadata:** `../deliverable/tsx_s1_IW_matches.parquet`
- **Stack Files:** `../output/stack_*.csv` (834 files)
- **TSX Database:** Contains 23,396 unique TSX products
- **S1 Matches:** 41,687 TSX-S1 matches with spatial overlap ≥ 0.85

## Generation

Visualizations generated using [2_visualize.py](../2_visualize.py)

Generated on: January 29, 2026
