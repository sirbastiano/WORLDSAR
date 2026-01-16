from pathlib import Path
from sarpyx.snapflow.engine import GPT
from sarpyx.utils.geos import check_points_in_polygon, rectangle_to_wkt, rectanglify
import re
from dotenv import load_dotenv
import os
import argparse

# ================================================================================================================================ ENVIRON
# Load environment variables from .env file
load_dotenv()
# Read paths from environment variables
GPT_PATH = os.getenv('GPT_PATH')
GRID_PATH = os.getenv('GRID_PATH')
# ========================================================================================================================================







# ================================================================================================================================ Parser
# Parse command-line arguments
def parse_arguments():
    """
    Parse command-line arguments.

    Returns:
        argparse.Namespace: Parsed arguments containing product_path, output_dir, and product_wkt.
    """
    parser = argparse.ArgumentParser(description='Process Sentinel-1 data.')
    parser.add_argument(
        '--product_path',
        type=str,
        required=True,
        help='Path to the input Sentinel-1 product.'
    )
    parser.add_argument(
        '--output_dir',
        type=str,
        required=True,
        help='Directory to save the processed output.'
    )
    parser.add_argument(
        '--cuts_outdir',
        type=str,
        required=True,
        help='Where to store the tiles after extraction.'
    )
    parser.add_argument(
        '--product_wkt',
        type=str,
        required=True,
        help='WKT string defining the product region of interest.'
    )
    return parser.parse_args()

# Basic initialization setting
args = parse_arguments()
product_path = Path(args.product_path)
output_dir = Path(args.output_dir)
product_wkt = args.product_wkt
cuts_outdir = Path(args.cuts_outdir)
prepro = True
grid_geoj_path = GRID_PATH
# ========================================================================================================================================









# ================================================================================================================================ AUXILIARY
def extract_product_id(path: str) -> str | None:
    m = re.search(r"/([^/]+?)_[^/_]+\.dim$", path)
    return m.group(1) if m else None


def subset(product_path: Path, output_dir: Path, geo_region: str = None, output_name: str = None):
    assert geo_region is not None, "Geo region WKT string must be provided for subsetting."
    
    op = GPT(
        product=product_path,
        outdir=output_dir,
        format='HDF5',
        gpt_path=GPT_PATH,
    )
    op.Subset(
        copy_metadata=True,
        output_name=output_name,
        geo_region=geo_region,
        )

    return op.prod_path
# ========================================================================================================================================

def pipeline_sentinel(product_path: Path, output_dir: Path, is_TOPS: bool = False):
    """A simple test pipeline to validate the GPT wrapper functionality.

    The operations included are:
    - Debursting
    - Calibration to complex
    - Multilooking
    - (Optional) Subsetting by geographic coordinates

    Args:
        product_path (Path): Path to the input product.
        output_dir (Path): Directory to save the processed output.

    Returns:
        Path: Path to the processed product.
    """
    op = GPT(
        product=product_path,
        outdir=output_dir,
        format='BEAM-DIMAP',
        gpt_path=GPT_PATH,
    )
    op.ApplyOrbitFile()
    if is_TOPS:
        op.TopsarDerampDemod()
    op.Deburst()
    op.Calibration(output_complex=True)
    # TODO: Add subaperture.
    op.TerrainCorrection(map_projection='AUTO:42001', pixel_spacing_in_meter=10.0)
    return op.prod_path


def pipeline_biomass(product_path: Path, output_dir: Path):
    """A simple test pipeline to validate the GPT wrapper functionality.

    The operations included are:
    - Debursting
    - Calibration to complex
    - Multilooking
    - (Optional) Subsetting by geographic coordinates

    Args:
        product_path (Path): Path to the input product.
        output_dir (Path): Directory to save the processed output.

    Returns:
        Path: Path to the processed product.
    """
    op = GPT(
        product=product_path,
        outdir=output_dir,
        format='BEAM-DIMAP',
        gpt_path=GPT_PATH,
    )
    
    op.TerrainCorrection(map_projection='AUTO:42001', pixel_spacing_in_meter=10.0)
    return op.prod_path



# ================================ MAIN ==================================
if __name__ == "__main__":
    
    # STEP1:
    if prepro:
        intermediate_product = pipeline_sentinel(product_path, output_dir)
        print(f"Intermediate processed product located at: {intermediate_product}")

    # STEP2:
    else:
        # ------ Cutting according to the tile griding system: ------
        print(f'Checking points within polygon: {product_wkt}')
        assert Path(grid_geoj_path).exists(), 'grid_10km.geojson does not exist.'
        # step 1: check the contained grid points in the prod
        contained = check_points_in_polygon(product_wkt, geojson_path=grid_geoj_path)
        # step 2: Build the rectangles for cutting
        rectangles = rectanglify(contained)
        # TODO: remove this hardcoded path in the final pipe, use directly  intermediate_product as path
        product_path = Path('/Data_large/SARGFM/data/2_processed/S1A_IW_SLC__1SDV_20240503T031928_20240503T031942_053701_0685FB_670F_TC.dim')
        name = extract_product_id(product_path.as_posix())
        if name is None:
            raise ValueError(f"Could not extract product id from: {product_path}")
        # step 3: CUT!
        for rect in rectangles:
            geo_region = rectangle_to_wkt(rect)
            final_product = subset(product_path, 
                                   cuts_outdir / name, 
                                   output_name=rect['BL']['properties']['name'],
                                   geo_region=geo_region)
            print(f"Final processed product located at: {final_product}")
            
    # STEP3:
    # Database indexing
    # Take folder cuts_outdir
    # Use pathlib to identify the different files (naming used grid convention)
    # Use functions from core_metadata.py to extract relevant metadata and build the database
    #   containing info about metadata and grid.
    
    
    # STEP4:
    # Upload to Hugginface.
        