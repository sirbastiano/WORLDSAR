#!/usr/bin/env python3
"""
Create overview and zoom figures for WorldSAR TC products and sub-aperture features.

Per product and per available (optional swath prefix, polarization) group, this script writes:
  - overview_<suffix>.png: full-aperture and sub-aperture intensity previews
  - zoom_<suffix>.png: central zoom of intensities plus all computed feature bands
"""

import argparse
import math
import re
from pathlib import Path
from typing import Dict, List, NamedTuple, Tuple

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.windows import Window


IQ_RE = re.compile(
    r"^(?P<part>[iq])_(?:(?P<prefix>IW\d+)_)?(?P<pol>VV|VH)(?:_SA(?P<sa>\d+))?\.img$",
    re.IGNORECASE,
)


class PlotGroup(NamedTuple):
    prefix: str
    pol: str
    full_i: Path
    full_q: Path
    subaps: Tuple[int, ...]
    subap_paths: Dict[int, Dict[str, Path]]


def make_suffix(prefix: str, pol: str) -> str:
    return f"{prefix}_{pol}" if prefix else pol


def to_db(intensity: np.ndarray, eps: float = 1e-8) -> np.ndarray:
    return 10.0 * np.log10(np.maximum(intensity, eps)).astype(np.float32, copy=False)


def compute_intensity(i_arr: np.ndarray, q_arr: np.ndarray) -> np.ndarray:
    return (i_arr.astype(np.float32) ** 2 + q_arr.astype(np.float32) ** 2).astype(np.float32, copy=False)


def central_window(width: int, height: int, size: int) -> Window:
    w = min(width, size)
    h = min(height, size)
    col_off = max(0, (width - w) // 2)
    row_off = max(0, (height - h) // 2)
    return Window(col_off, row_off, w, h)


def read_intensity_preview(i_path: Path, q_path: Path, max_size: int) -> np.ndarray:
    with rasterio.open(i_path) as src_i, rasterio.open(q_path) as src_q:
        scale = min(max_size / src_i.height, max_size / src_i.width, 1.0)
        out_h = max(1, int(src_i.height * scale))
        out_w = max(1, int(src_i.width * scale))
        i_arr = src_i.read(1, out_shape=(out_h, out_w), resampling=Resampling.average)
        q_arr = src_q.read(1, out_shape=(out_h, out_w), resampling=Resampling.average)
    return to_db(compute_intensity(i_arr, q_arr))


def read_intensity_zoom(i_path: Path, q_path: Path, zoom_size: int) -> np.ndarray:
    with rasterio.open(i_path) as src_i, rasterio.open(q_path) as src_q:
        win = central_window(src_i.width, src_i.height, zoom_size)
        i_arr = src_i.read(1, window=win)
        q_arr = src_q.read(1, window=win)
    return to_db(compute_intensity(i_arr, q_arr))


def read_feature_bands(feature_path: Path, zoom_size: int) -> List[Tuple[str, np.ndarray]]:
    with rasterio.open(feature_path) as src:
        win = central_window(src.width, src.height, zoom_size)
        data = src.read(window=win).astype(np.float32)
        desc = list(src.descriptions or [])
    result = []
    for band_idx in range(data.shape[0]):
        name = desc[band_idx] if band_idx < len(desc) and desc[band_idx] else f"band_{band_idx + 1}"
        result.append((pretty_feature_title(name), data[band_idx]))
    return result


def robust_limits(arrays: List[np.ndarray], lower: float = 2.0, upper: float = 98.0) -> Tuple[float, float]:
    finite = np.concatenate([a[np.isfinite(a)] for a in arrays if np.isfinite(a).any()])
    if finite.size == 0:
        return 0.0, 1.0
    vmin = float(np.percentile(finite, lower))
    vmax = float(np.percentile(finite, upper))
    if not np.isfinite(vmin) or not np.isfinite(vmax) or vmin == vmax:
        vmax = vmin + 1.0
    return vmin, vmax


def reference_limits(reference: np.ndarray, lower: float = 2.0, upper: float = 98.0) -> Tuple[float, float]:
    return robust_limits([reference], lower=lower, upper=upper)


def pretty_feature_title(name: str) -> str:
    gamma_match = re.match(r"^gamma(\d+)(\d+)$", name)
    if gamma_match:
        return "Interlook Coherence ({}-{})".format(gamma_match.group(1), gamma_match.group(2))

    if name == "gamma_mean":
        return "Mean Interlook Coherence"

    cov_power_match = re.match(r"^C(\d)(\d)$", name)
    if cov_power_match and cov_power_match.group(1) == cov_power_match.group(2):
        return "Covariance Power ({})".format(cov_power_match.group(1))

    re_match = re.match(r"^ReC(\d)(\d)$", name)
    if re_match:
        return "Covariance Real Part ({}-{})".format(re_match.group(1), re_match.group(2))

    im_match = re.match(r"^ImC(\d)(\d)$", name)
    if im_match:
        return "Covariance Imaginary Part ({}-{})".format(im_match.group(1), im_match.group(2))

    if name == "phase_variance":
        return "Interlook Phase Variance"

    return name.replace("_", " ").title()


def discover_plot_groups(product_dir: Path) -> List[PlotGroup]:
    full_paths: Dict[Tuple[str, str], Dict[str, Path]] = {}
    subap_paths: Dict[Tuple[str, str], Dict[int, Dict[str, Path]]] = {}

    for img_path in sorted(product_dir.glob("*.img")):
        match = IQ_RE.match(img_path.name)
        if not match:
            continue

        prefix = (match.group("prefix") or "").upper()
        pol = match.group("pol").upper()
        part = match.group("part").lower()
        sa = match.group("sa")
        key = (prefix, pol)

        if sa is None:
            full_paths.setdefault(key, {})[part] = img_path
        else:
            subap_paths.setdefault(key, {}).setdefault(int(sa), {})[part] = img_path

    groups: List[PlotGroup] = []
    for key, full_iq in sorted(full_paths.items()):
        if "i" not in full_iq or "q" not in full_iq:
            continue
        sa_map = subap_paths.get(key, {})
        valid_subaps = tuple(sorted(sa for sa, iq in sa_map.items() if "i" in iq and "q" in iq))
        groups.append(
            PlotGroup(
                prefix=key[0],
                pol=key[1],
                full_i=full_iq["i"],
                full_q=full_iq["q"],
                subaps=valid_subaps,
                subap_paths={sa: sa_map[sa] for sa in valid_subaps},
            )
        )
    return groups


def save_overview_figure(
    group: PlotGroup,
    out_path: Path,
    preview_size: int,
    intensity_pmin: float,
    intensity_pmax: float,
) -> None:
    panels = [("Full", read_intensity_preview(group.full_i, group.full_q, preview_size))]
    for sa in group.subaps:
        panels.append(
            (
                f"SA{sa}",
                read_intensity_preview(group.subap_paths[sa]["i"], group.subap_paths[sa]["q"], preview_size),
            )
        )

    vmin, vmax = reference_limits(panels[0][1], lower=intensity_pmin, upper=intensity_pmax)
    fig, axes = plt.subplots(1, len(panels), figsize=(4 * len(panels), 4.5), squeeze=False)

    for ax, (title, arr) in zip(axes[0], panels):
        im = ax.imshow(arr, cmap="gray", vmin=vmin, vmax=vmax)
        ax.set_title(f"{title} [{group.pol}]")
        ax.axis("off")
        plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04, label="dB")

    fig.suptitle(f"{out_path.parent.name} | {make_suffix(group.prefix, group.pol)} | full view", fontsize=12)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def save_zoom_figure(
    group: PlotGroup,
    feature_dir: Path,
    out_path: Path,
    zoom_size: int,
    intensity_pmin: float,
    intensity_pmax: float,
) -> None:
    panels = [("Full", read_intensity_zoom(group.full_i, group.full_q, zoom_size))]
    for sa in group.subaps:
        panels.append(
            (
                f"SA{sa}",
                read_intensity_zoom(group.subap_paths[sa]["i"], group.subap_paths[sa]["q"], zoom_size),
            )
        )

    features: List[Tuple[str, np.ndarray]] = []
    suffix = make_suffix(group.prefix, group.pol)
    for stem in [f"coherence_{suffix}.tif", f"covariance_{suffix}.tif", f"phase_variance_{suffix}.tif"]:
        tif_path = feature_dir / stem
        if tif_path.exists():
            features.extend(read_feature_bands(tif_path, zoom_size))

    items = [(f"{name} intensity [dB]", arr) for name, arr in panels] + features
    ncols = min(4, max(1, len(items)))
    nrows = math.ceil(len(items) / ncols)
    fig, axes = plt.subplots(nrows, ncols, figsize=(4 * ncols, 4 * nrows), squeeze=False)

    inten_vmin, inten_vmax = reference_limits(panels[0][1], lower=intensity_pmin, upper=intensity_pmax)

    for idx, (title, arr) in enumerate(items):
        ax = axes[idx // ncols][idx % ncols]
        if title.endswith("intensity [dB]"):
            vmin, vmax, cmap = inten_vmin, inten_vmax, "gray"
        else:
            vmin, vmax = robust_limits([arr])
            cmap = "viridis"
        im = ax.imshow(arr, cmap=cmap, vmin=vmin, vmax=vmax)
        ax.set_title(title, fontsize=10)
        ax.axis("off")
        plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)

    for idx in range(len(items), nrows * ncols):
        axes[idx // ncols][idx % ncols].axis("off")

    fig.suptitle(
        f"{out_path.parent.name} | {suffix} | central zoom {zoom_size}x{zoom_size}",
        fontsize=12,
    )
    fig.tight_layout()
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def find_tc_products(root: Path) -> List[Path]:
    if root.is_dir() and root.name.endswith("_TC.data"):
        return [root]
    return sorted(p for p in root.rglob("*_TC.data") if p.is_dir())


def main() -> None:
    parser = argparse.ArgumentParser(description="Plot WorldSAR TC intensities and subap features.")
    parser.add_argument("--input-root", type=Path, required=True, help="TC product root or single *_TC.data directory.")
    parser.add_argument("--features-root", type=Path, required=True, help="Root directory with subap feature TIFFs.")
    parser.add_argument("--output-root", type=Path, required=True, help="Output directory for PNG figures.")
    parser.add_argument("--preview-size", type=int, default=1024, help="Maximum preview size for full-scene plots.")
    parser.add_argument("--zoom-size", type=int, default=1024, help="Central zoom size in pixels.")
    parser.add_argument("--intensity-pmin", type=float, default=2.0, help="Lower percentile for intensity display, computed from full-aperture.")
    parser.add_argument("--intensity-pmax", type=float, default=98.0, help="Upper percentile for intensity display, computed from full-aperture.")
    args = parser.parse_args()

    args.output_root.mkdir(parents=True, exist_ok=True)
    products = find_tc_products(args.input_root)
    if not products:
        print(f"No *_TC.data directories found under: {args.input_root}")
        return

    print(f"Found {len(products)} *_TC.data products.")

    for product_dir in products:
        rel_parent = Path(".")
        if args.input_root in product_dir.parents:
            rel_parent = product_dir.parent.relative_to(args.input_root)

        feature_dir = args.features_root / rel_parent / product_dir.name
        figure_dir = args.output_root / rel_parent / product_dir.name
        figure_dir.mkdir(parents=True, exist_ok=True)

        print(f"\nProcessing plots for: {product_dir}")
        groups = discover_plot_groups(product_dir)
        for group in groups:
            suffix = make_suffix(group.prefix, group.pol)
            save_overview_figure(
                group,
                figure_dir / f"overview_{suffix}.png",
                args.preview_size,
                args.intensity_pmin,
                args.intensity_pmax,
            )
            save_zoom_figure(
                group,
                feature_dir,
                figure_dir / f"zoom_{suffix}.png",
                args.zoom_size,
                args.intensity_pmin,
                args.intensity_pmax,
            )
            print(f"  [{suffix}] wrote overview and zoom figures")

    print("\nDone.")


if __name__ == "__main__":
    main()
