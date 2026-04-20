"""Download a single NISAR product by filename using asf_search.

Credentials are read from ~/.netrc:
    machine urs.earthdata.nasa.gov login <username> password <password>

Usage:
    python scripts/download_nisar.py <product_name> --output-dir /path/to/data
"""
import argparse
from pathlib import Path

import asf_search as asf


def download(product_name: str, output_dir: Path) -> Path:
    results = asf.search(fileID=product_name)
    if not results:
        # Some NISAR granule IDs use a different search field
        results = asf.search(granule_list=[product_name])
    if not results:
        raise ValueError(f"Product not found on ASF: {product_name}")
    output_dir.mkdir(parents=True, exist_ok=True)
    results[0].download(path=output_dir)
    return output_dir / results[0].properties["fileName"]


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Download a NISAR product from ASF by filename.")
    p.add_argument("product_name", help="NISAR product filename (without extension)")
    p.add_argument("--output-dir", default=".", type=Path, help="Directory to save the file")
    args = p.parse_args()
    path = download(args.product_name, args.output_dir)
    print(f"Downloaded: {path}")
