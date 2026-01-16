from phidown.search import CopernicusDataSearcher
from shapely.geometry import shape

searcher_by_name = CopernicusDataSearcher()

# Replace with an actual product name you want to find
product_to_find = 'S1A_IW_SLC__1SDV_20240503T031928_20240503T031942_053701_0685FB_670F.SAFE' # Example, replace with a recent, valid name

print(f"Searching for product with exact name: {product_to_find}\n")
df_exact = searcher_by_name.query_by_name(product_name=product_to_find)

if not df_exact.empty:
    searcher_by_name.display_results(top_n=1)
    print(df_exact)
    print("\nProduct found successfully.")
    
    # Get the GeoFootprint and convert to WKT
    geofootprint = df_exact['GeoFootprint'].values[0]
    print(f"Product with GeoFootprint: '{geofootprint}' found.")
    
    # Convert GeoJSON geometry to WKT
    polygon = shape(geofootprint)
    wkt_polygon = polygon.wkt
    
    print(f"\nWKT Polygon:\n{wkt_polygon}")
    
else:
    print(f"Product '{product_to_find}' not found or an error occurred.")