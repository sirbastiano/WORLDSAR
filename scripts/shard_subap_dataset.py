#!/usr/bin/env python3

import argparse
import csv
import os
import shutil
import tarfile
from collections import OrderedDict
from pathlib import Path
from typing import List, Optional, Set, TextIO, Tuple


DEFAULT_SOURCE = Path("/lustre/scratch/1001/rdelprete/srsd_patches/dataset_sm_subaps")
DEFAULT_OUTPUT = Path("/lustre/scratch/1001/rdelprete/srsd_patches/dataset_sm_subaps_sharded")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Shard the SRSD sub-aperture dataset into one tar archive per metadata prefix "
            "to keep Hugging Face dataset file counts manageable."
        )
    )
    parser.add_argument(
        "--source-root",
        type=Path,
        default=DEFAULT_SOURCE,
        help="Dataset root containing out_tensors_x96/ and _metadata_parts/.",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Destination directory for shard tar files and indexes.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Delete an existing output directory before writing.",
    )
    parser.add_argument(
        "--limit-shards",
        type=int,
        default=None,
        help="Only build the first N shards after sorting prefixes. Useful for smoke tests.",
    )
    parser.add_argument(
        "--skip-scan",
        action="store_true",
        help="Reuse previously generated manifest files in the output directory.",
    )
    return parser.parse_args()


def ensure_clean_output(output_root: Path, overwrite: bool) -> None:
    if output_root.exists():
        if not overwrite:
            raise FileExistsError(
                f"Output directory already exists: {output_root}. Use --overwrite to replace it."
            )
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    (output_root / "shards").mkdir(parents=True, exist_ok=True)
    (output_root / "_manifests").mkdir(parents=True, exist_ok=True)


def load_metadata_prefixes(metadata_root: Path) -> List[str]:
    prefixes = sorted(path.stem for path in metadata_root.glob("*.csv"))
    if not prefixes:
        raise FileNotFoundError(f"No metadata CSV files found in {metadata_root}")
    return prefixes


def tensor_prefix(filename: str) -> Optional[str]:
    if not filename.endswith(".safetensors"):
        return None
    marker = "__"
    last = filename.rfind(marker)
    if last == -1:
        return None
    return filename[:last]


class HandleCache:
    def __init__(self, limit: int = 64) -> None:
        self.limit = limit
        self._handles: OrderedDict[str, TextIO] = OrderedDict()

    def get(self, key: str, path: Path) -> TextIO:
        handle = self._handles.pop(key, None)
        if handle is None:
            handle = path.open("a", encoding="utf-8")
        self._handles[key] = handle
        if len(self._handles) > self.limit:
            _, oldest = self._handles.popitem(last=False)
            oldest.close()
        return handle

    def close(self) -> None:
        for handle in self._handles.values():
            handle.close()
        self._handles.clear()


def build_manifests(tensor_root: Path, prefixes: Set[str], manifest_root: Path) -> Tuple[int, int]:
    matched = 0
    unmatched = 0
    cache = HandleCache()
    try:
        for entry in os.scandir(tensor_root):
            if not entry.is_file():
                continue
            prefix = tensor_prefix(entry.name)
            if prefix is None:
                continue
            if prefix not in prefixes:
                unmatched += 1
                continue
            manifest_path = manifest_root / f"{prefix}.txt"
            handle = cache.get(prefix, manifest_path)
            handle.write(entry.name)
            handle.write("\n")
            matched += 1
    finally:
        cache.close()
    return matched, unmatched


def write_readme(output_root: Path, source_root: Path) -> None:
    readme = output_root / "README.md"
    readme.write_text(
        "\n".join(
            [
                "---",
                "pretty_name: SRSD Sub-Aperture S1SM x96",
                "task_categories:",
                "- image-classification",
                "language:",
                "- en",
                "license: unknown",
                "---",
                "",
                "# SRSD Sub-Aperture S1SM x96",
                "",
                "This dataset is packaged as one tar shard per metadata prefix to keep the file count manageable for Hugging Face Hub uploads.",
                "",
                "## Layout",
                "",
                "- `shards/<prefix>.tar`: archive containing `metadata/<prefix>.csv` and the matching `tensors/*.safetensors` files.",
                "- `shard_index.csv`: one row per shard with file counts and byte totals.",
                "",
                "## Source",
                "",
                f"Generated from `{source_root}`.",
                "",
                "## Notes",
                "",
                "- Each tar shard groups tensor patches by the same prefix used by its metadata CSV.",
                "- Safetensor filenames are preserved inside the tar archives.",
                "- Replace this card text with task-specific documentation before publishing if you want a richer Hub presentation.",
                "",
            ]
        ),
        encoding="utf-8",
    )


def build_shards(
    tensor_root: Path,
    metadata_root: Path,
    output_root: Path,
    prefixes: List[str],
) -> Tuple[int, int]:
    shard_dir = output_root / "shards"
    index_path = output_root / "shard_index.csv"
    total_tensors = 0
    total_bytes = 0

    with index_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["prefix", "tar_name", "tensor_count", "tensor_bytes", "metadata_name"])

        for idx, prefix in enumerate(prefixes, start=1):
            manifest_path = output_root / "_manifests" / f"{prefix}.txt"
            tensor_names = []
            if manifest_path.exists():
                tensor_names = [line.strip() for line in manifest_path.read_text(encoding="utf-8").splitlines() if line.strip()]

            tar_name = f"{prefix}.tar"
            tar_path = shard_dir / tar_name
            metadata_path = metadata_root / f"{prefix}.csv"
            shard_bytes = 0

            with tarfile.open(tar_path, "w") as tar:
                tar.add(metadata_path, arcname=f"metadata/{metadata_path.name}", recursive=False)
                for tensor_name in tensor_names:
                    tensor_path = tensor_root / tensor_name
                    shard_bytes += tensor_path.stat().st_size
                    tar.add(tensor_path, arcname=f"tensors/{tensor_name}", recursive=False)

            writer.writerow([prefix, tar_name, len(tensor_names), shard_bytes, metadata_path.name])
            total_tensors += len(tensor_names)
            total_bytes += shard_bytes

            if idx % 100 == 0 or idx == len(prefixes):
                print(
                    f"[build] {idx}/{len(prefixes)} shards written | "
                    f"{total_tensors:,} tensors | {total_bytes / (1024 ** 4):.2f} TiB"
                )

    return total_tensors, total_bytes


def main() -> None:
    args = parse_args()
    source_root = args.source_root.resolve()
    tensor_root = source_root / "out_tensors_x96"
    metadata_root = source_root / "_metadata_parts"
    output_root = args.output_root.resolve()

    if not tensor_root.is_dir():
        raise FileNotFoundError(f"Missing tensor directory: {tensor_root}")
    if not metadata_root.is_dir():
        raise FileNotFoundError(f"Missing metadata directory: {metadata_root}")

    if args.skip_scan:
        output_root.mkdir(parents=True, exist_ok=True)
        (output_root / "shards").mkdir(parents=True, exist_ok=True)
        (output_root / "_manifests").mkdir(parents=True, exist_ok=True)
    else:
        ensure_clean_output(output_root, args.overwrite)

    prefixes = load_metadata_prefixes(metadata_root)
    if args.limit_shards is not None:
        prefixes = prefixes[: args.limit_shards]
    prefix_set = set(prefixes)

    if args.skip_scan:
        print(f"[scan] reusing manifests from {output_root / '_manifests'}")
        matched = sum(1 for _ in (output_root / "_manifests").glob("*.txt"))
        unmatched = 0
    else:
        print(f"[scan] indexing tensors in {tensor_root}")
        matched, unmatched = build_manifests(tensor_root, prefix_set, output_root / "_manifests")
        print(f"[scan] matched {matched:,} tensors across {len(prefixes):,} prefixes")
        if unmatched:
            print(f"[scan] skipped {unmatched:,} tensors without matching metadata")

    write_readme(output_root, source_root)
    total_tensors, total_bytes = build_shards(tensor_root, metadata_root, output_root, prefixes)
    print(f"[done] wrote {len(prefixes):,} tar shards to {output_root / 'shards'}")
    print(f"[done] indexed {total_tensors:,} tensors totaling {total_bytes / (1024 ** 4):.2f} TiB")


if __name__ == "__main__":
    main()
