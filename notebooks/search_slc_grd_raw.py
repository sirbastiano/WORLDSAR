import configparser
from phidown.search import CopernicusDataSearcher
import time
from datetime import datetime, timedelta
import pandas as pd
import random
from pathlib import Path


# -------------- Utility functions --------------
def adjust_time(time_str: str, seconds: int) -> str:
    """
    Adjust a given ISO 8601 time string by a specified number of seconds.

    Args:
        time_str (str): The original time in ISO 8601 format.
        seconds (int): The number of seconds to adjust the time by. Can be positive or negative.

    Returns:
        str: The adjusted time in format compatible with phidown (no timezone info).
    """
    original_time = datetime.fromisoformat(time_str.replace('Z', '+00:00'))
    adjusted_time = original_time + timedelta(seconds=seconds)
    # Format without timezone info and microseconds for phidown compatibility
    return adjusted_time.strftime('%Y-%m-%dT%H:%M:%S')


def geojson_to_polygon_wkt(geometry, *, on_multipolygon="first"):
    """
    Convert a GeoJSON geometry to a POLYGON WKT string.

    This function guarantees a POLYGON WKT output. Behavior by geometry type:
    - Polygon: serialized directly to POLYGON (2D or Z).
    - MultiPolygon: by default takes the first polygon and returns it as POLYGON.
      You can control this with `on_multipolygon`.
    - Any other geometry type: raises ValueError.

    Parameters
    ----------
    geometry : dict
        A GeoJSON-like geometry dictionary with keys:
        - 'type' (str): One of {'Polygon','MultiPolygon'} is supported; others raise.
        - 'coordinates' (list): For 'Polygon', a list of linear rings; for 'MultiPolygon',
          a list of polygons (each a list of rings). Rings are expected in GeoJSON order
          [x, y] or [x, y, z]. Rings should be closed (first == last); this function
          does not enforce closure.
    on_multipolygon : {'first', 'error'}, optional
        Behavior when input is a MultiPolygon:
        - 'first' (default): Use the first polygon within the MultiPolygon.
        - 'error': Raise ValueError if there is more than one polygon.
        Note: True topological merging (dissolve/union) is not performed.

    Returns
    -------
    str
        A POLYGON (or 'POLYGON Z') WKT string.

    Raises
    ------
    ValueError
        If geometry type is unsupported, structure is invalid, or MultiPolygon handling
        is set to 'error' with multiple polygons.

    Notes
    -----
    - This function does not perform geometric operations (e.g., union/merge).
    - Presence of any Z value in the chosen polygon promotes output to 'POLYGON Z'.
    """

    def _is_3d_coords(obj):
        """Return True if any coordinate has 3 elements."""
        found = False

        def _walk(o):
            nonlocal found
            if found:
                return
            if isinstance(o, (list, tuple)):
                if o and all(isinstance(v, (int, float)) for v in o):
                    if len(o) >= 3:
                        found = True
                else:
                    for item in o:
                        _walk(item)

        _walk(obj)
        return found

    def _fmt_num(n):
        """Format numbers compactly, removing trailing zeros and unnecessary decimals."""
        if isinstance(n, int):
            return str(n)
        return f"{float(n):.15g}"

    def _fmt_coord(coord):
        return " ".join(_fmt_num(c) for c in coord[:3])  # x y or x y z

    def _fmt_ring(ring):
        return f"({_fmt_coord_list(ring)})"

    def _fmt_coord_list(coords):
        return ", ".join(_fmt_coord(c) for c in coords)

    gtype = geometry.get("type")
    if not gtype:
        raise ValueError("Geometry missing 'type'")

    if gtype == "Polygon":
        rings = geometry.get("coordinates")
        if not isinstance(rings, list):
            raise ValueError("Polygon 'coordinates' must be a list of rings")
        dim = " Z" if _is_3d_coords(rings) else ""
        return f"POLYGON{dim} ({', '.join(_fmt_ring(r) for r in rings)})"

    if gtype == "MultiPolygon":
        polys = geometry.get("coordinates")
        if not isinstance(polys, list) or not polys:
            raise ValueError("MultiPolygon 'coordinates' must be a non-empty list of polygons")
        if on_multipolygon == "error" and len(polys) != 1:
            raise ValueError("MultiPolygon has multiple polygons; set on_multipolygon='first' to pick the first")
        chosen = polys[0]
        if not isinstance(chosen, list):
            raise ValueError("Invalid MultiPolygon structure: expected list of polygons (list of rings)")
        dim = " Z" if _is_3d_coords(chosen) else ""
        return f"POLYGON{dim} ({', '.join(_fmt_ring(r) for r in chosen)})"

    raise ValueError(f"Unsupported geometry type for polygon output: {gtype}")


def geojson_to_shrunk_polygon_wkt(geometry, *, on_multipolygon="first", shrink_factor=20.0):
    """
    Convert a GeoJSON Polygon/MultiPolygon to a POLYGON WKT after shrinking by a factor.

    The polygon is uniformly scaled in XY about the *outer-ring planar centroid* by 1/shrink_factor.
    Z values (if present) are preserved. For MultiPolygon, behavior matches the original:
    use the first polygon or raise if `on_multipolygon='error'` and multiple parts exist.

    Args:
        geometry (dict): GeoJSON-like geometry. Supported 'type': {'Polygon','MultiPolygon'}.
        on_multipolygon (Literal['first','error']): How to handle MultiPolygon (default: 'first').
        shrink_factor (float): Linear shrink factor (> 0). E.g., 10.0 → 10× smaller in XY.

    Returns:
        str: POLYGON or POLYGON Z WKT string of the shrunken geometry.

    Raises:
        ValueError: On unsupported types, invalid structures, empty coords, or invalid factor.

    Notes:
        * Only the chosen polygon is processed; no topological operations are performed.
        * Outer-ring centroid is computed via the signed-area (shoelace) formula in XY.
          If area is ~0 (degenerate), fallback to arithmetic mean of the outer-ring vertices.
        * Rings are not re-ordered or re-oriented; closure is preserved if present in input.
        * Z values are passed through unchanged (not scaled).
    """
    # -------- helpers --------
    def _is_3d_coords(obj):
        found = False
        def _walk(o):
            nonlocal found
            if found:
                return
            if isinstance(o, (list, tuple)):
                if o and all(isinstance(v, (int, float)) for v in o):
                    if len(o) >= 3:
                        found = True
                else:
                    for it in o:
                        _walk(it)
        _walk(obj)
        return found

    def _fmt_num(n):
        if isinstance(n, int):
            return str(n)
        return f"{float(n):.15g}"

    def _fmt_coord(coord):
        return " ".join(_fmt_num(c) for c in coord[:3])

    def _fmt_ring(ring):
        return f"({_fmt_coord_list(ring)})"

    def _fmt_coord_list(coords):
        return ", ".join(_fmt_coord(c) for c in coords)

    def _outer_ring_centroid_xy(ring):
        """Centroid of outer ring in XY via area-weighted formula; fallback to mean if degenerate."""
        pts = ring
        if len(pts) < 3:
            # degenerate; mean
            xs = [p[0] for p in pts] or [0.0]
            ys = [p[1] for p in pts] or [0.0]
            return (sum(xs) / len(xs), sum(ys) / len(ys))

        # Use all vertices; include closing vertex if present (handled safely)
        xys = [(p[0], p[1]) for p in pts]
        # Ensure we iterate pairs (i, i+1) cyclically
        A = 0.0
        Cx = 0.0
        Cy = 0.0
        n = len(xys)
        for i in range(n - 1):
            x0, y0 = xys[i]
            x1, y1 = xys[i + 1]
            cross = x0 * y1 - x1 * y0
            A += cross
            Cx += (x0 + x1) * cross
            Cy += (y0 + y1) * cross
        # If ring is closed, the last pair above used the closing edge already.
        A *= 0.5
        if abs(A) < 1e-15:
            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]
            return (sum(xs) / len(xs), sum(ys) / len(ys))
        Cx /= (6.0 * A)
        Cy /= (6.0 * A)
        return (Cx, Cy)

    def _scale_ring_about_xy_centroid(ring, cx, cy, s):
        """Scale a ring's XY about (cx, cy) by factor s; preserve Z."""
        out = []
        for p in ring:
            if not isinstance(p, (list, tuple)) or len(p) < 2:
                raise ValueError("Invalid coordinate; expected at least [x, y]")
            x, y = p[0], p[1]
            z = p[2] if len(p) >= 3 else None
            xs = cx + s * (x - cx)
            ys = cy + s * (y - cy)
            if z is None:
                out.append([xs, ys])
            else:
                out.append([xs, ys, z])
        # Preserve closure exactly if input was closed
        if len(ring) >= 2:
            first_in = ring[0]
            last_in = ring[-1]
            if len(first_in) >= 2 and len(last_in) >= 2 and first_in[0] == last_in[0] and first_in[1] == last_in[1]:
                out[ -1 ] = out[0][:]  # exact closure
        return out

    def _shrink_polygon_rings(rings, factor):
        if not rings or not isinstance(rings, list):
            raise ValueError("Polygon 'coordinates' must be a non-empty list of rings")
        if factor <= 0:
            raise ValueError("shrink_factor must be > 0")
        s = 1.0 / float(factor)

        outer = rings[0]
        if not isinstance(outer, list) or len(outer) < 3:
            raise ValueError("Outer ring must be a list of at least 3 coordinates")

        cx, cy = _outer_ring_centroid_xy(outer)
        out_rings = []
        for ring in rings:
            if not isinstance(ring, list) or len(ring) < 3:
                raise ValueError("Each ring must be a list of at least 3 coordinates")
            out_rings.append(_scale_ring_about_xy_centroid(ring, cx, cy, s))
        return out_rings

    # -------- main --------
    gtype = geometry.get("type")
    if not gtype:
        raise ValueError("Geometry missing 'type'")

    if gtype == "Polygon":
        rings = geometry.get("coordinates")
        shrunk_rings = _shrink_polygon_rings(rings, shrink_factor)
        dim = " Z" if _is_3d_coords(shrunk_rings) else ""
        return f"POLYGON{dim} ({', '.join(_fmt_ring(r) for r in shrunk_rings)})"

    if gtype == "MultiPolygon":
        polys = geometry.get("coordinates")
        if not isinstance(polys, list) or not polys:
            raise ValueError("MultiPolygon 'coordinates' must be a non-empty list of polygons")
        if on_multipolygon == "error" and len(polys) != 1:
            raise ValueError("MultiPolygon has multiple polygons; set on_multipolygon='first' to pick the first")
        chosen = polys[0]
        if not isinstance(chosen, list):
            raise ValueError("Invalid MultiPolygon structure: expected list of polygons (list of rings)")
        shrunk_rings = _shrink_polygon_rings(chosen, shrink_factor)
        dim = " Z" if _is_3d_coords(shrunk_rings) else ""
        return f"POLYGON{dim} ({', '.join(_fmt_ring(r) for r in shrunk_rings)})"

    raise ValueError(f"Unsupported geometry type for polygon output: {gtype}")


# -------------- Database functions --------------
def double_check_db(df: pd.DataFrame) -> None:
    """
    Double-check the DataFrame for duplicate entries based on 'Name' and 'Footprint'.

    Args:
        df (pd.DataFrame): DataFrame containing product information.
    """
    if len(df) == 0:
        raise ValueError("No products found in the database for the given query.")
    
    if len(df) == 1:
        # print("Database check passed: exactly one product found.")  
        pass
    
    if len(df) > 1:
        print(f"Found {len(df)} products. Here are their footprints:")
        for idx, row in df.iterrows():
            print(f"Product {idx}: {row['Name']}, Footprint: {row['Footprint']}")
        raise ValueError(f"Expected exactly one product to be found. \n Found: \n {df['Footprint']}")
        

def find_product_info(product_name: str) -> pd.DataFrame:
    """Look up a Copernicus GRD product by name.

    Args:
        product_name: Name of the GRD product to retrieve.

    Returns:
        pd.DataFrame: Matching product records.

    Raises:
        ValueError: If `product_name` is empty or not a string.
        LookupError: If no product matches the provided name.
    """
    if not isinstance(product_name, str) or not product_name.strip():
        raise ValueError("product_name must be a non-empty string.")

    searcher = CopernicusDataSearcher()
    df = searcher.query_by_name(product_name=product_name.strip())

    if df is None or df.empty:
        raise LookupError(f"No GRD product found with name '{product_name}'.")

    return df


def get_corresponding_slc(geo_footprint: dict, start: str, end: str) -> str:
    """
    Retrieve the corresponding SLC product name for a given GeoFootprint and time window.

    Args:
        geo_footprint (dict): GeoJSON-like geometry dictionary.
        start (str): Start time in ISO 8601 format.
        end (str): End time in ISO 8601 format.

    Returns:
        str: Name of the corresponding SLC product.
    """
    searcher = CopernicusDataSearcher()
    searcher.query_by_filter(
        collection_name='SENTINEL-1',
        product_type='SLC',
        orbit_direction=None,
        cloud_cover_threshold=None,
        aoi_wkt=geojson_to_shrunk_polygon_wkt(geo_footprint),
        start_date=start,
        end_date=end,
        top=1000,
        attributes={'processingLevel': 'LEVEL1'}
    )
    df = searcher.execute_query()
    double_check_db(df)
    product_name = df.sample(n=1)['Name'].values[0]
    return product_name


def get_corresponding_raw(geo_footprint: dict, start: str, end: str) -> str:
    """
    Retrieve the corresponding L0 product name for a given GeoFootprint and time window.

    Args:
        geo_footprint (dict): GeoJSON-like geometry dictionary.
        start (str): Start time in ISO 8601 format.
        end (str): End time in ISO 8601 format.

    Returns:
        str: Name of the corresponding L0 product.
    """
    searcher = CopernicusDataSearcher()
    searcher.query_by_filter(
        collection_name='SENTINEL-1',
        product_type=None,
        orbit_direction=None,
        cloud_cover_threshold=None,
        aoi_wkt=geojson_to_shrunk_polygon_wkt(geo_footprint),
        start_date=start,
        end_date=end,
        top=1000,
        attributes={'processingLevel': 'LEVEL0'}
    )
    df = searcher.execute_query()
    product_name = df.sample(n=1)['Name'].values[0]
    double_check_db(df)
    return product_name
# -------------- Database functions End --------------























