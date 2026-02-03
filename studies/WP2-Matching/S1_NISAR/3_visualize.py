#!/usr/bin/env python3
"""
Pipeline step 3: visualize NISAR-S1 stacks.

Creates interactive HTML maps and a statistics summary page.
Optionally publishes outputs to the repo docs dashboard.
"""

from datetime import datetime
from pathlib import Path
import re
import shutil

import folium
import numpy as np
import pandas as pd
from folium import plugins
from shapely import wkt
from tqdm import tqdm


SUMMARY_FILENAME = "nisar_s1_index.html"
HEATMAP_FILENAME = "nisar_s1_stack_heatmap.html"
QUALITY_FILENAME = "nisar_s1_temporal_frequency.html"


def write_placeholder_html(output_path, title, message):
    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>{title}</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 40px; color: #222; }}
    .card {{ max-width: 720px; padding: 24px; border: 1px solid #ddd; border-radius: 10px; }}
    h1 {{ margin: 0 0 12px 0; font-size: 22px; }}
    p {{ margin: 0; line-height: 1.5; }}
  </style>
</head>
<body>
  <div class="card">
    <h1>{title}</h1>
    <p>{message}</p>
  </div>
</body>
</html>
"""
    output_path.write_text(html)


def load_stack_files(stack_dir):
    print(f"\nLoading stack files from {stack_dir}...")
    stack_files = sorted(stack_dir.glob("stack_*.csv"))
    stacks = {}

    for stack_file in tqdm(stack_files, desc="Loading stacks"):
        stack_id = int(stack_file.stem.split("_")[1])
        df = pd.read_csv(stack_file)
        df["nisar_start_time"] = pd.to_datetime(df["nisar_start_time"], errors="coerce")
        df = df.sort_values("nisar_start_time")
        stacks[stack_id] = df

    print(f"Loaded {len(stacks)} stacks")
    return stacks


def compute_stack_statistics(stacks):
    print("\nComputing stack statistics...")
    stats = []

    for stack_id, stack_df in tqdm(stacks.items(), desc="Computing stats"):
        if len(stack_df) == 0:
            continue
        wkt_value = stack_df["nisar_wkt"].iloc[0]
        geom = wkt.loads(wkt_value) if isinstance(wkt_value, str) else wkt_value
        if geom is None or geom.is_empty:
            continue

        num_products = len(stack_df)

        if num_products > 1:
            time_diffs = stack_df["nisar_start_time"].diff().dropna()
            avg_time_diff_days = time_diffs.mean().total_seconds() / 86400
            min_time_diff_days = time_diffs.min().total_seconds() / 86400
            max_time_diff_days = time_diffs.max().total_seconds() / 86400
        else:
            avg_time_diff_days = np.nan
            min_time_diff_days = np.nan
            max_time_diff_days = np.nan

        centroid = geom.centroid
        minx, miny, maxx, maxy = geom.bounds

        stats.append(
            {
                "stack_id": stack_id,
                "num_products": num_products,
                "avg_time_diff_days": avg_time_diff_days,
                "min_time_diff_days": min_time_diff_days,
                "max_time_diff_days": max_time_diff_days,
                "center_lon": centroid.x,
                "center_lat": centroid.y,
                "bbox_minlon": minx,
                "bbox_minlat": miny,
                "bbox_maxlon": maxx,
                "bbox_maxlat": maxy,
            }
        )

    stats_df = pd.DataFrame(stats)
    print(f"\nStatistics computed for {len(stats_df)} stacks")
    if len(stats_df) == 0:
        print("Total products across all stacks: 0")
        return stats_df

    print(f"Total products across all stacks: {stats_df['num_products'].sum()}")
    print(f"Average products per stack: {stats_df['num_products'].mean():.1f}")
    print(f"Median temporal spacing: {stats_df['avg_time_diff_days'].median():.1f} days")

    return stats_df


def create_heatmap(stats_df, output_path):
    print("\nCreating product count heatmap...")
    center_lat = stats_df["center_lat"].mean()
    center_lon = stats_df["center_lon"].mean()

    m = folium.Map(location=[center_lat, center_lon], zoom_start=2, tiles="OpenStreetMap")

    heat_data = [
        [row["center_lat"], row["center_lon"], row["num_products"]]
        for _, row in stats_df.iterrows()
    ]

    plugins.HeatMap(
        heat_data,
        min_opacity=0.3,
        max_zoom=13,
        radius=15,
        blur=20,
        gradient={
            0.0: "blue",
            0.3: "cyan",
            0.5: "lime",
            0.7: "yellow",
            1.0: "red",
        },
    ).add_to(m)

    marker_cluster = plugins.MarkerCluster(name="Stack Details")

    for _, row in stats_df.iterrows():
        popup_html = f"""
        <b>Stack ID:</b> {row['stack_id']}<br>
        <b>Products:</b> {row['num_products']}<br>
        <b>Avg Temporal Spacing:</b> {row['avg_time_diff_days']:.1f} days<br>
        <b>Min Spacing:</b> {row['min_time_diff_days']:.1f} days<br>
        <b>Max Spacing:</b> {row['max_time_diff_days']:.1f} days<br>
        <b>Location:</b> ({row['center_lat']:.3f}, {row['center_lon']:.3f})
        """

        folium.Marker(
            location=[row["center_lat"], row["center_lon"]],
            popup=folium.Popup(popup_html, max_width=300),
            icon=folium.Icon(
                color="red" if row["num_products"] > 10 else "blue", icon="info-sign"
            ),
        ).add_to(marker_cluster)

    marker_cluster.add_to(m)
    folium.LayerControl().add_to(m)

    nav_html = f"""
    <div style="position: fixed; 
                top: 10px; left: 50%; transform: translateX(-50%); 
                background-color: rgba(255, 255, 255, 0.95); 
                border: 2px solid #4CAF50; 
                border-radius: 5px;
                z-index:9999; 
                padding: 10px 20px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.2);">
        <a href="{SUMMARY_FILENAME}" style="text-decoration: none; color: #4CAF50; font-weight: bold; margin: 0 10px;">🏠 Home</a> |
        <span style="color: #4CAF50; font-weight: bold; margin: 0 10px;">📊 Coverage Heatmap</span> |
        <a href="{QUALITY_FILENAME}" style="text-decoration: none; color: #2196F3; margin: 0 10px;">⏱️ Quality Map</a>
    </div>
    """
    m.get_root().html.add_child(folium.Element(nav_html))

    title_html = """
    <div style="position: fixed; 
                top: 70px; left: 50px; width: 520px; height: 90px; 
                background-color: white; border:2px solid grey; z-index:9999; 
                font-size:14px; padding: 10px">
        <h4>NISAR-S1 Stack Coverage Heatmap</h4>
        <p>Heat intensity shows number of products per stack location.<br>
        Click markers for detailed stack information.</p>
    </div>
    """
    m.get_root().html.add_child(folium.Element(title_html))

    m.save(str(output_path))
    print(f"Heatmap saved to {output_path}")


def create_temporal_frequency_map(stats_df, output_path):
    print("\nCreating temporal frequency map...")

    stats_temporal = stats_df[stats_df["num_products"] > 1].copy()
    print(f"Creating map for {len(stats_temporal)} stacks with 2+ products")

    center_lat = stats_temporal["center_lat"].mean()
    center_lon = stats_temporal["center_lon"].mean()

    m = folium.Map(location=[center_lat, center_lon], zoom_start=2, tiles="OpenStreetMap")

    def get_color_2d(avg_days, num_products):
        if pd.isna(avg_days):
            return "gray"

        if avg_days <= 15:
            freq_score = 3
        elif avg_days <= 30:
            freq_score = 2
        elif avg_days <= 50:
            freq_score = 1
        else:
            freq_score = 0

        if num_products >= 30:
            count_score = 3
        elif num_products >= 20:
            count_score = 2
        elif num_products >= 10:
            count_score = 1
        else:
            count_score = 0

        combined_score = freq_score + count_score
        color_map = {
            6: "#006400",
            5: "#228B22",
            4: "#32CD32",
            3: "#FFD700",
            2: "#FFA500",
            1: "#FF4500",
            0: "#8B0000",
        }
        return color_map.get(combined_score, "gray")

    for _, row in stats_temporal.iterrows():
        color = get_color_2d(row["avg_time_diff_days"], row["num_products"])
        avg_days = row["avg_time_diff_days"]
        num_prods = row["num_products"]

        if avg_days <= 15 and num_prods >= 30:
            quality = "Excellent"
        elif avg_days <= 30 and num_prods >= 20:
            quality = "Good"
        elif avg_days <= 50 or num_prods >= 10:
            quality = "Fair"
        else:
            quality = "Poor"

        popup_html = f"""
        <b>Stack ID:</b> {row['stack_id']}<br>
        <b>Quality:</b> <span style="color:{color}; font-weight:bold">{quality}</span><br>
        <b>Products:</b> {row['num_products']}<br>
        <b>Avg Temporal Spacing:</b> {row['avg_time_diff_days']:.1f} days<br>
        <b>Min Spacing:</b> {row['min_time_diff_days']:.1f} days<br>
        <b>Max Spacing:</b> {row['max_time_diff_days']:.1f} days<br>
        <b>Location:</b> ({row['center_lat']:.3f}, {row['center_lon']:.3f})
        """

        folium.CircleMarker(
            location=[row["center_lat"], row["center_lon"]],
            radius=6,
            popup=folium.Popup(popup_html, max_width=300),
            color=color,
            fill=True,
            fillColor=color,
            fillOpacity=0.8,
            weight=2,
        ).add_to(m)

    legend_html = """
    <div style="position: fixed; 
                bottom: 50px; right: 50px; width: 240px; height: 320px; 
                background-color: white; border:2px solid grey; z-index:9999; 
                font-size:12px; padding: 10px">
        <h4 style="margin-top:0">Stack Quality</h4>
        <p style="margin:3px 0"><span style="color:#006400; font-size:16px">●</span> Excellent (≤15d, ≥30 prod)</p>
        <p style="margin:3px 0"><span style="color:#228B22; font-size:16px">●</span> Very Good</p>
        <p style="margin:3px 0"><span style="color:#32CD32; font-size:16px">●</span> Good (≤30d, ≥20 prod)</p>
        <p style="margin:3px 0"><span style="color:#FFD700; font-size:16px">●</span> Fair</p>
        <p style="margin:3px 0"><span style="color:#FFA500; font-size:16px">●</span> Poor</p>
        <p style="margin:3px 0"><span style="color:#FF4500; font-size:16px">●</span> Very Poor</p>
        <p style="margin:3px 0"><span style="color:#8B0000; font-size:16px">●</span> Worst (>50d, <10 prod)</p>
        <hr style="margin: 10px 0">
        <p style="margin-top:10px; font-size:10px; line-height: 1.4">
        <b>Quality based on:</b><br>
        • Temporal spacing (lower=better)<br>
        • Product count (higher=better)<br>
        <b>Green</b> = frequent revisits + many products
        </p>
    </div>
    """
    m.get_root().html.add_child(folium.Element(legend_html))

    nav_html = f"""
    <div style="position: fixed; 
                top: 10px; left: 50%; transform: translateX(-50%); 
                background-color: rgba(255, 255, 255, 0.95); 
                border: 2px solid #4CAF50; 
                border-radius: 5px;
                z-index:9999; 
                padding: 10px 20px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.2);">
        <a href="{SUMMARY_FILENAME}" style="text-decoration: none; color: #4CAF50; font-weight: bold; margin: 0 10px;">🏠 Home</a> |
        <a href="{HEATMAP_FILENAME}" style="text-decoration: none; color: #2196F3; margin: 0 10px;">📊 Coverage Heatmap</a> |
        <span style="color: #4CAF50; font-weight: bold; margin: 0 10px;">⏱️ Quality Map</span>
    </div>
    """
    m.get_root().html.add_child(folium.Element(nav_html))

    title_html = """
    <div style="position: fixed; 
                top: 70px; left: 50px; width: 540px; height: 90px; 
                background-color: white; border:2px solid grey; z-index:9999; 
                font-size:14px; padding: 10px">
        <h4>NISAR-S1 Stack Quality Map</h4>
        <p>Color shows combined quality based on temporal frequency and product count.<br>
        Green = high frequency (short revisit) + many products = best quality stacks.</p>
    </div>
    """
    m.get_root().html.add_child(folium.Element(title_html))

    m.save(str(output_path))
    print(f"Temporal frequency map saved to {output_path}")


def create_statistics_summary(stats_df, output_path):
    print("\nCreating statistics summary...")

    total_stacks = len(stats_df)
    total_products = stats_df["num_products"].sum() if total_stacks > 0 else 0
    avg_products = stats_df["num_products"].mean() if total_stacks > 0 else 0
    median_products = stats_df["num_products"].median() if total_stacks > 0 else 0

    stats_temporal = stats_df[stats_df["num_products"] > 1]
    avg_temporal_spacing = (
        stats_temporal["avg_time_diff_days"].mean() if len(stats_temporal) > 0 else 0
    )
    median_temporal_spacing = (
        stats_temporal["avg_time_diff_days"].median() if len(stats_temporal) > 0 else 0
    )

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>WP2 SAR Mission Matching - NISAR Summary</title>
        <meta charset="UTF-8">
        <style>
            body {{
                font-family: Arial, sans-serif;
                margin: 0;
                padding: 0;
                background-color: #f5f5f5;
            }}
            .header {{
                background: linear-gradient(135deg, #0f2027 0%, #203a43 50%, #2c5364 100%);
                color: white;
                padding: 30px 40px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            }}
            .header h1 {{
                margin: 0;
                font-size: 32px;
            }}
            .header p {{
                margin: 10px 0 0 0;
                font-size: 16px;
                opacity: 0.9;
            }}
            .container {{
                max-width: 1200px;
                margin: 40px auto;
                padding: 0 20px;
            }}
            .mission-section {{
                background-color: white;
                padding: 30px;
                margin-bottom: 30px;
                border-radius: 10px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                border: 2px solid #4CAF50;
            }}
            .mission-section h2 {{
                color: #333;
                border-bottom: 3px solid #4CAF50;
                padding-bottom: 10px;
                margin-top: 0;
            }}
            .status-badge {{
                display: inline-block;
                padding: 5px 15px;
                border-radius: 20px;
                font-size: 12px;
                font-weight: bold;
                margin-left: 10px;
                background-color: #4CAF50;
                color: white;
            }}
            .stats-grid {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 15px;
                margin: 20px 0;
            }}
            .stat-box {{
                background-color: #f9f9f9;
                padding: 20px;
                border-radius: 5px;
                border-left: 4px solid #2c5364;
            }}
            .stat-label {{
                font-size: 14px;
                color: #777;
                margin-bottom: 5px;
            }}
            .stat-value {{
                font-size: 28px;
                font-weight: bold;
                color: #333;
            }}
            .links-container {{
                display: flex;
                flex-wrap: wrap;
                gap: 10px;
                margin-top: 20px;
            }}
            .link-button {{
                display: inline-block;
                padding: 12px 24px;
                background-color: #2c5364;
                color: white;
                text-decoration: none;
                border-radius: 5px;
                font-weight: bold;
                transition: all 0.3s;
            }}
            .link-button:hover {{
                background-color: #203a43;
                transform: translateY(-2px);
                box-shadow: 0 4px 8px rgba(0,0,0,0.2);
            }}
            .section-description {{
                color: #555;
                line-height: 1.6;
                margin-bottom: 20px;
            }}
            .footer {{
                text-align: center;
                color: #777;
                font-size: 12px;
                margin: 40px 0;
            }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>🛰️ NISAR ↔ Sentinel-1 Matching</h1>
            <p>Interactive visualizations and statistics for NISAR/Sentinel-1 stack analysis</p>
        </div>

        <div class="container">
            <div class="mission-section">
                <h2>
                    Sentinel-1 ↔ NISAR
                    <span class="status-badge">✓ ACTIVE</span>
                </h2>
                <p class="section-description">
                    Sentinel-1 matched with NISAR L-band SAR products. Analysis of {total_stacks} stacks
                    containing {total_products} products with temporal and spatial overlap characteristics.
                </p>

                <div class="stats-grid">
                    <div class="stat-box">
                        <div class="stat-label">Total Stacks</div>
                        <div class="stat-value">{total_stacks}</div>
                    </div>
                    <div class="stat-box">
                        <div class="stat-label">Total Products</div>
                        <div class="stat-value">{total_products}</div>
                    </div>
                    <div class="stat-box">
                        <div class="stat-label">Avg Products/Stack</div>
                        <div class="stat-value">{avg_products:.1f}</div>
                    </div>
                    <div class="stat-box">
                        <div class="stat-label">Median Temporal Spacing</div>
                        <div class="stat-value">{median_temporal_spacing:.1f} days</div>
                    </div>
                </div>

                <div class="links-container">
                    <a href="{HEATMAP_FILENAME}" target="_blank" class="link-button">📊 Coverage Heatmap</a>
                    <a href="{QUALITY_FILENAME}" target="_blank" class="link-button">⏱️ Stack Quality Map</a>
                </div>
            </div>
        </div>

        <div class="footer">
            <p>WP2-Matching Analysis | Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            <p>WORLDSAR Project | ESA</p>
        </div>
    </body>
    </html>
    """

    output_path.write_text(html_content)
    print(f"Statistics summary saved to {output_path}")


def publish_outputs(visuals_dir, publish_dir):
    publish_dir.mkdir(parents=True, exist_ok=True)
    files_to_publish = [
        HEATMAP_FILENAME,
        QUALITY_FILENAME,
        SUMMARY_FILENAME,
    ]

    for filename in files_to_publish:
        src = visuals_dir / filename
        dst = publish_dir / filename
        shutil.copy2(src, dst)
        print(f"Published {src} -> {dst}")


def update_portal_index(portal_path, stats_df):
    if not portal_path.exists():
        raise FileNotFoundError(f"Portal index not found: {portal_path}")

    total_stacks = len(stats_df)
    total_products = stats_df["num_products"].sum() if total_stacks > 0 else 0
    avg_products = stats_df["num_products"].mean() if total_stacks > 0 else 0
    median_temporal_spacing = (
        stats_df[stats_df["num_products"] > 1]["avg_time_diff_days"].median()
        if total_stacks > 0
        else 0
    )

    nisar_section = f"""
            <div class=\"mission-section active\">
                <h2>
                    Sentinel-1 ↔ NISAR
                    <span class=\"status-badge status-active\">✓ ACTIVE</span>
                </h2>
                <p class=\"section-description\">
                    Sentinel-1 matched with NISAR L-band SAR products. Analysis of {total_stacks} stacks 
                    containing {total_products} products with temporal and spatial overlap characteristics.
                </p>
                
                <div class=\"stats-grid\">
                    <div class=\"stat-box\">
                        <div class=\"stat-label\">Total Stacks</div>
                        <div class=\"stat-value\">{total_stacks}</div>
                    </div>
                    <div class=\"stat-box\">
                        <div class=\"stat-label\">Total Products</div>
                        <div class=\"stat-value\">{total_products}</div>
                    </div>
                    <div class=\"stat-box\">
                        <div class=\"stat-label\">Avg Products/Stack</div>
                        <div class=\"stat-value\">{avg_products:.1f}</div>
                    </div>
                    <div class=\"stat-box\">
                        <div class=\"stat-label\">Median Temporal Spacing</div>
                        <div class=\"stat-value\">{median_temporal_spacing:.1f} days</div>
                    </div>
                </div>
                
                <div class=\"links-container\">
                    <a href=\"{HEATMAP_FILENAME}\" target=\"_blank\" class=\"link-button\">📊 Coverage Heatmap</a>
                    <a href=\"{QUALITY_FILENAME}\" target=\"_blank\" class=\"link-button\">⏱️ Stack Quality Map</a>
                </div>
            </div>
    """

    content = portal_path.read_text()
    pattern = re.compile(
        r"(<!-- S1-NISAR Section -->)(.*?)(<!-- S1-BIOMASS Section -->)",
        re.DOTALL,
    )
    if not pattern.search(content):
        raise ValueError("Could not find S1-NISAR section markers in portal index")

    updated = pattern.sub(r"\\1\n" + nisar_section + r"\n\\3", content)
    updated = re.sub(
        r"Generated on [0-9\-: ]+",
        f"Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        updated,
    )
    portal_path.write_text(updated)
    print(f"Updated portal index at {portal_path}")


def main():
    base_dir = Path(__file__).resolve().parent
    default_stack_dir = base_dir / "output"
    default_visuals_dir = base_dir / "visuals"
    default_publish_dir = None
    default_portal_path = base_dir.parents[3] / "docs" / "index.html"

    import argparse

    parser = argparse.ArgumentParser(
        description="Pipeline step 3: visualize NISAR-S1 temporal stacks"
    )
    parser.add_argument(
        "--stack-dir",
        type=str,
        default=str(default_stack_dir),
        help="Directory containing stack CSV files",
    )
    parser.add_argument(
        "--visuals-dir",
        type=str,
        default=str(default_visuals_dir),
        help="Directory to write HTML outputs",
    )
    parser.add_argument(
        "--publish-dir",
        type=str,
        default=default_publish_dir,
        help="Optional directory to copy dashboard HTML files (e.g., docs)",
    )
    parser.add_argument(
        "--update-portal",
        action="store_true",
        help="Update docs/index.html with NISAR stats and links (requires --publish-dir)",
    )
    parser.add_argument(
        "--portal-path",
        type=str,
        default=str(default_portal_path),
        help="Path to the portal index.html to update",
    )

    args = parser.parse_args()

    stacks = load_stack_files(Path(args.stack_dir))
    stats_df = compute_stack_statistics(stacks)

    visuals_dir = Path(args.visuals_dir)
    visuals_dir.mkdir(parents=True, exist_ok=True)

    if stats_df.empty:
        print("No stacks found. Writing placeholder visualizations.")
        write_placeholder_html(
            visuals_dir / SUMMARY_FILENAME,
            "NISAR/Sentinel-1 Summary",
            "No stack files were found. Run Step 1 and Step 2 to generate stacks, "
            "then re-run Step 3.",
        )
        write_placeholder_html(
            visuals_dir / HEATMAP_FILENAME,
            "NISAR/Sentinel-1 Stack Heatmap",
            "No stack data available to display a heatmap.",
        )
        write_placeholder_html(
            visuals_dir / QUALITY_FILENAME,
            "NISAR/Sentinel-1 Temporal Frequency",
            "No stack data available to display temporal frequency.",
        )

        if args.publish_dir:
            publish_dir = Path(args.publish_dir)
            publish_outputs(visuals_dir, publish_dir)

            if args.update_portal:
                update_portal_index(Path(args.portal_path), stats_df)

        print("\n" + "=" * 60)
        print("No stacks found. Placeholder visualizations created.")
        print(f"Open {visuals_dir / SUMMARY_FILENAME} to view the summary")
        print("=" * 60)
        return

    create_heatmap(stats_df, visuals_dir / HEATMAP_FILENAME)
    create_temporal_frequency_map(stats_df, visuals_dir / QUALITY_FILENAME)
    create_statistics_summary(stats_df, visuals_dir / SUMMARY_FILENAME)

    if args.publish_dir:
        publish_dir = Path(args.publish_dir)
        publish_outputs(visuals_dir, publish_dir)

        if args.update_portal:
            update_portal_index(Path(args.portal_path), stats_df)

    print("\n" + "=" * 60)
    print("All visualizations created successfully!")
    print(f"Open {visuals_dir / SUMMARY_FILENAME} to view the summary")
    print("=" * 60)


if __name__ == "__main__":
    main()
