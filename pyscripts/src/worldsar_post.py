#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any

import h5py
import numpy as np
import zarr


DEFAULT_CHUNK_SIZE = (32, 32)


def normalize_attribute_value(value: Any) -> Any:
    """Convert HDF5 attribute values into JSON-serializable Zarr attributes."""
    if isinstance(value, bytes | np.bytes_):
        return value.decode("utf-8", errors="surrogateescape")
    if isinstance(value, str | bool | int | float) or value is None:
        return value
    if isinstance(value, np.generic):
        return normalize_attribute_value(value.item())
    if isinstance(value, np.ndarray):
        return normalize_attribute_value(value.tolist())
    if isinstance(value, list | tuple):
        return [normalize_attribute_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): normalize_attribute_value(item) for key, item in value.items()}
    return str(value)


def normalize_attributes(attrs: h5py.AttributeManager) -> dict[str, Any]:
    return {str(key): normalize_attribute_value(value) for key, value in attrs.items()}


def derive_chunk_shape(shape: tuple[int, ...], chunk_size: tuple[int, int]) -> tuple[int, ...] | None:
    if len(shape) == 0:
        return None
    if len(shape) == 1:
        return (min(shape[0], chunk_size[0]),)
    return (
        min(shape[0], chunk_size[0]),
        min(shape[1], chunk_size[1]),
        *shape[2:],
    )


def _copy_dataset(source: h5py.Dataset, target_parent: zarr.Group, chunk_size: tuple[int, int]) -> None:
    data = source[()]
    chunks = derive_chunk_shape(source.shape, chunk_size)
    array = target_parent.create_array(
        source.name.rsplit("/", 1)[-1],
        data=data,
        chunks=chunks if chunks is not None else "auto",
        overwrite=False,
    )
    array.attrs.update(normalize_attributes(source.attrs))


def _copy_group(source: h5py.Group, target: zarr.Group, chunk_size: tuple[int, int]) -> None:
    target.attrs.update(normalize_attributes(source.attrs))
    for name, obj in source.items():
        if isinstance(obj, h5py.Group):
            child = target.create_group(name)
            _copy_group(obj, child, chunk_size)
        elif isinstance(obj, h5py.Dataset):
            _copy_dataset(obj, target, chunk_size)
        else:
            raise TypeError(f"Unsupported HDF5 object at {obj.name}: {type(obj)!r}")


def resolve_output_path(input_path: Path, output_path: Path | None) -> Path:
    if output_path is not None:
        return output_path
    return input_path.with_suffix(".zarr")


def convert_tile_h5_to_zarr(
    input_path: Path | str,
    output_path: Path | str | None = None,
    chunk_size: tuple[int, int] = DEFAULT_CHUNK_SIZE,
    overwrite: bool = False,
) -> Path:
    source_path = Path(input_path).expanduser()
    if not source_path.is_absolute():
        source_path = (Path.cwd() / source_path).absolute()

    if output_path is None:
        target_path = resolve_output_path(source_path, None)
    else:
        target_path = Path(output_path).expanduser()
        if not target_path.is_absolute():
            target_path = (Path.cwd() / target_path).absolute()

    if source_path.suffix.lower() != ".h5":
        raise ValueError(f"Expected an .h5 tile, got: {source_path}")
    if not source_path.is_file():
        raise FileNotFoundError(f"Input tile does not exist: {source_path}")
    if len(chunk_size) != 2 or any(size <= 0 for size in chunk_size):
        raise ValueError(f"Chunk size must contain two positive integers, got: {chunk_size}")

    if target_path.exists():
        if not overwrite:
            raise FileExistsError(
                f"Output Zarr store already exists: {target_path}. Pass overwrite=True or --overwrite."
            )
        if target_path.is_dir():
            shutil.rmtree(target_path)
        else:
            target_path.unlink()

    target_path.parent.mkdir(parents=True, exist_ok=True)

    with h5py.File(source_path, "r") as source:
        root = zarr.create_group(store=target_path.as_posix(), zarr_format=3, overwrite=False)
        _copy_group(source, root, chunk_size)

    return target_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Convert a WorldSAR HDF5 tile into a Zarr v3 store.")
    parser.add_argument("input_tile", type=Path, help="Path to the source .h5 tile.")
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional output .zarr path. Defaults to a sibling store next to the input tile.",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        nargs=2,
        metavar=("ROWS", "COLS"),
        default=DEFAULT_CHUNK_SIZE,
        help="Chunk size for arrays. Defaults to 32 32.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace an existing output store if present.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    output = convert_tile_h5_to_zarr(
        input_path=args.input_tile,
        output_path=args.output,
        chunk_size=tuple(args.chunk_size),
        overwrite=args.overwrite,
    )
    summary = {
        "input": str(Path(args.input_tile).expanduser().absolute()),
        "output": str(output),
        "chunk_size": list(args.chunk_size),
        "zarr_format": 3,
    }
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
