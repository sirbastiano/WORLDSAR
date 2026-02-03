import asf_search as asf
import pandas as pd
from shapely.geometry import shape
from datetime import datetime

def main():
    # 1) Build the search
    # GSLC is a processingLevel value (Level-2 Geocoded SLC / Geocoded Single Look Complex)
    print("Searching for NISAR GSLC products...")
    results = asf.search(
        dataset=asf.DATASET.NISAR,                 # keep it scoped to the NISAR collection
        processingLevel=asf.PRODUCT_TYPE.GSLC      # Level-2 Geocoded SLC (GSLC)
    )

    print(f"Found: {len(results)} GSLC granules")
    # This is usually the most robust path: ASFSearchResults.geojson() is stable across versions.
    g = results.geojson()

    rows = []
    for feat in g.get("features", []):
        props = feat.get("properties", {}) or {}
        geom = feat.get("geometry", None)

        # robust URL extraction (sometimes list)
        url = props.get("url")
        if isinstance(url, list):
            url = url[0] if url else None

        # parse geometry to compute spatial summary columns
        geom_shape = shape(geom) if geom else None
        centroid = geom_shape.centroid if geom_shape else None
        
        # timestamps
        start = pd.to_datetime(props.get("startTime"), errors="coerce", utc=True)
        stop  = pd.to_datetime(props.get("stopTime"), errors="coerce", utc=True)
        duration_s = (stop - start).total_seconds() if (pd.notna(start) and pd.notna(stop)) else None

        rows.append({
            # core identifiers
            "sceneName": props.get("sceneName"),
            "fileID": props.get("fileID"),
            "platform": props.get("platform"),
            "processingLevel": props.get("processingLevel"),
            "beamMode": props.get("beamMode"),
            "polarization": props.get("polarization"),
            "flightDirection": props.get("flightDirection"),

            # time
            "startTime_utc": start,
            "stopTime_utc": stop,
            "duration_s": duration_s,

            # link
            "url": url,

            # spatial derived columns
            "centroid_lon": centroid.x if centroid else None,
            "centroid_lat": centroid.y if centroid else None,
            "WKT": geom_shape.wkt if geom_shape else None,
        })

    df = pd.DataFrame(rows)

    # optional: clean typing + ordering
    preferred_order = [
        "sceneName", "fileID", "WKT", "platform", "processingLevel",
        "beamMode", "polarization", "flightDirection",
        "startTime_utc", "stopTime_utc", "duration_s",
        "centroid_lon", "centroid_lat",
        "url", 
    ]
    df = df[[c for c in preferred_order if c in df.columns]]
    
    # Save to CSV with timestamp
    now_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_filename = f"nisar_gslc_{now_str}.csv"
    df.to_csv(output_filename, index=False)
    print(f"DataFrame saved to {output_filename}")

if __name__ == "__main__":
    main()
