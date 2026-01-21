from pathlib import Path
from dotenv import load_dotenv
import re, os, sys
import pandas as pd
from functools import partial
import argparse

from sarpyx.snapflow.engine import GPT
from sarpyx.utils.geos import check_points_in_polygon, rectangle_to_wkt, rectanglify

from wkt_utils import sentinel1_wkt_extractor_cdse
from core_metadata import extract_core_metadata_sentinel, read_h5

# Load environment variables from .env file
load_dotenv()
# Read paths from environment variables
GPT_PATH = os.getenv('gpt_path')
GRID_PATH = os.getenv('grid_path')
DB_DIR = os.getenv('db_dir')
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
    parser.add_argument(
        '--prod_mode',
        type=str,
        required=True,
        help='Product mode: ["S1TOPS", "S1STRIP","BM","NISAR", "TSX", "CSG", "ICE"].'
    )
    return parser.parse_args()

# Basic initialization setting
args = parse_arguments()
product_path = Path(args.product_path)
output_dir = Path(args.output_dir)
product_wkt = args.product_wkt
cuts_outdir = Path(args.cuts_outdir)
grid_geoj_path = Path(GRID_PATH) if GRID_PATH else None
product_mode = args.prod_mode






# ======================================================================================================================== SETTINGS
""" Processing settings"""
tiling = True
prepro = True
db_indexing = True
upload_hf = False

# ======================================================================================================================== AUXILIARY
""" Auxiliary functions for database creation and product subsetting. """
def extract_product_id(path: str) -> str | None:
    m = re.search(r"/([^/]+?)_[^/_]+\.dim$", path)
    return m.group(1) if m else None


def create_tile_database(input_folder: str, output_db_folder: str) -> pd.DataFrame:
    """Create a database of tile metadata from h5 files.
    
    Args:
        input_folder: Path to folder containing h5 tile files
        output_db_folder: Path to folder where database parquet file will be saved
        
    Returns:
        DataFrame containing the metadata for all tiles
    """
    # Find all h5 tiles in the input folder
    tile_path = Path(input_folder)
    h5_tiles = list(tile_path.rglob('*.h5'))
    print(f"Found {len(h5_tiles)} h5 files in {input_folder}")
    
    # Initialize empty database
    db = pd.DataFrame()
    
    # Process each tile
    for idx, tile_file in enumerate(h5_tiles):
        print(f"Processing tile {idx + 1}/{len(h5_tiles)}: {tile_file.name}")
        
        # Read h5 file and extract metadata
        data, metadata = read_h5(tile_file)
        row = pd.Series(metadata['quickinfo'])
        row['ID'] = tile_file.stem  # Add TileID to the row
        
        # Append to database
        db = pd.concat([db, pd.DataFrame([row])], ignore_index=True)
    
    # Save database to parquet file
    output_db_path = Path(output_db_folder)
    output_db_path.mkdir(parents=True, exist_ok=True)
    
    prod_name = tile_path.name
    output_file = output_db_path / f'{prod_name}_core_metadata.parquet'
    db.to_parquet(output_file, index=False)
    
    print(f"Core metadata saved to {output_file}")
    
    return db


def to_geotiff(product_path: Path, output_dir: Path, geo_region: str = None, output_name: str = None):
    assert geo_region is not None, "Geo region WKT string must be provided for subsetting."
    
    op = GPT(
        product=product_path,
        outdir=output_dir,
        format='GDAL-GTiff-WRITER',
        gpt_path=GPT_PATH,
    )
    op.Write()

    return op.prod_path


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

# ======================================================================================================================== PIPELINES
""" Different pipelines for different missions/products. """
def pipeline_sentinel(product_path: Path, output_dir: Path, is_TOPS: bool = False, subaperture: bool = False):
    """A simple test pipeline to validate the GPT wrapper functionality.

    The operations included are:
    - Debursting
    - Calibration to complex
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
    if is_TOPS and subaperture:
        op.TopsarDerampDemod()
    op.Deburst()
    op.Calibration(output_complex=True)
    # TODO: Add subaperture.
    op.TerrainCorrection(map_projection='AUTO:42001', pixel_spacing_in_meter=10.0)
    return op.prod_path


def pipeline_terrasar(product_path: Path, output_dir: Path):
    """Terrasar-X pipeline.

    The operations included are:
    - Calibration, outputting complex data if available.
    - Terrain Correction with automatic map projection and 5m pixel spacing.

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
    op.Calibration(output_complex=True)
    # TODO: Add subaperture.
    op.TerrainCorrection(map_projection='AUTO:42001', pixel_spacing_in_meter=5.0)
    return op.prod_path


def pipeline_cosmo(product_path: Path, output_dir: Path):
    """COSMO-SkyMed pipeline.

    The operations included are:
    - Calibration, outputting complex data if available.
    - Terrain Correction with automatic map projection and 5m pixel spacing.

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
    op.Calibration(output_complex=True)
    # TODO: Add subaperture.
    op.TerrainCorrection(map_projection='AUTO:42001', pixel_spacing_in_meter=5.0)
    return op.prod_path


def pipeline_biomass(product_path: Path, output_dir: Path):
    """BIOMASS pipeline.

    Args:
        product_path (Path): Path to the input product.
        output_dir (Path): Directory to save the processed output.

    Returns:
        Path: Path to the processed product.
    """
    op = GPT(
        product=product_path,
        outdir=output_dir,
        format='GDAL-GTiff-WRITER',
        gpt_path=GPT_PATH,
    )
    op.Write()
    # TODO: Calculate SubApertures with BIOMASS Data.
    return op.prod_path


def pipeline_nisar(product_path: Path, output_dir: Path):
    """ NISAR Pipeline.

    The operations included are:

    Args:
        product_path (Path): Path to the input product.
        output_dir (Path): Directory to save the processed output.

    Returns:
        Path: Path to the processed product.
    """
    
    # TODO: fix implementation
    product_path = None
    return product_path
# ========================================================================================================================================



# ========================================================================================================================================
""" The router switches between different pipelines based on the product mode. """
ROUTER_PIPE = {
    'S1TOPS': partial(pipeline_sentinel, is_TOPS=True),
    'S1STRIP': partial(pipeline_sentinel, is_TOPS=False),
    'BM': pipeline_biomass,
    'TSX': pipeline_terrasar,
    'NISAR': pipeline_nisar,
    'CSG': pipeline_cosmo,
}
# ========================================================================================================================================













# =============================================== MAIN =================================================
if __name__ == "__main__":
    
    # STEP1:
    if prepro:
        intermediate_product = ROUTER_PIPE[product_mode](product_path, output_dir)
        print(f"Intermediate processed product located at: {intermediate_product}")
        assert Path(intermediate_product).exists(), f"Intermediate product {intermediate_product} does not exist."

    # STEP2:
    if tiling:
        # ------ Cutting according to the tile griding system: UTM / WGS84 Auto ------
        print(f'Checking points within polygon: {product_wkt}')
        assert grid_geoj_path is not None and grid_geoj_path.exists(), 'grid_10km.geojson does not exist.'
        # step 1: check the contained grid points in the prod
        contained = check_points_in_polygon(product_wkt, geojson_path=grid_geoj_path)
        # step 2: Build the rectangles for cutting
        rectangles = rectanglify(contained)
        product_path = Path(intermediate_product)
        name = extract_product_id(product_path.as_posix())
        if name is None:
            raise ValueError(f"Could not extract product id from: {product_path}")
        # CUT!
        for rect in rectangles:
            geo_region = rectangle_to_wkt(rect)
            final_product = subset(product_path, 
                                   cuts_outdir / name, 
                                   output_name=rect['BL']['properties']['name'],
                                   geo_region=geo_region)
            print(f"Final processed product located at: {final_product}")
        total_tiles = len(rectangles)
        num_cuts = list(Path(cuts_outdir / name).rglob('*.h5'))
        assert total_tiles == len(num_cuts), f"Expected {total_tiles} tiles, but found {len(num_cuts)}."
        
            
    # STEP3:
    # Database indexing
    if db_indexing:
        cuts_folder = cuts_outdir / name
        db = create_tile_database(cuts_folder.as_posix(), DB_DIR)
        assert not db.empty, "Database creation failed, resulting DataFrame is empty."
        print("Database created successfully.")
        
    sys.exit(0)
    
# ========================================================================================================================================  
        