#!/usr/bin/env python3
"""
Information-theoretic validation for WorldSAR sub-aperture configurations.

The script samples pixels from TC products and compares candidate numbers of
sub-apertures and inter-look-coherence window sizes. It is intentionally
standalone: it reuses discovery and feature functions from compute_subap_features
but writes compact CSV/JSON reports instead of full rasters.
"""

import argparse
import csv
import itertools
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, NamedTuple, Optional, Sequence, Tuple

import numpy as np
import rasterio
from rasterio.windows import Window

try:
    from sklearn.cluster import KMeans
    from sklearn.metrics import normalized_mutual_info_score, silhouette_score

    HAVE_SKLEARN = True
except ImportError:
    KMeans = None
    normalized_mutual_info_score = None
    silhouette_score = None
    HAVE_SKLEARN = False

from compute_subap_features import (
    LookSet,
    coherence,
    covariance_terms,
    discover_look_sets,
    find_tc_products,
    phase_variance,
    read_complex_window,
)


class SampleBlock(NamedTuple):
    product: str
    prefix: str
    pol: str
    suffix: str
    subaps: Tuple[int, ...]
    stack: np.ndarray


class ConfigMetrics(NamedTuple):
    group_level: str
    product: str
    prefix: str
    pol: str
    suffix: str
    base_mode: str
    subap_count: int
    selected_subaps: str
    win_size: int
    product_count: int
    sample_count: int
    redundancy_corr_mean: float
    redundancy_corr_max: float
    redundancy_nmi_mean: float
    redundancy_nmi_max: float
    complement_cond_entropy_mean: float
    complement_unexplained_variance_mean: float
    complement_added_feature_entropy_mean: float
    stability_spatial_delta_mean: float
    stability_subsample_mean_delta: float
    stability_subsample_std_delta: float
    cluster_silhouette: float
    cluster_stability_nmi: float
    score: float


def parse_int_list(text: str) -> List[int]:
    values = [int(item.strip()) for item in text.split(",") if item.strip()]
    if not values:
        raise argparse.ArgumentTypeError("expected at least one integer")
    return values


def finite_vector(values: np.ndarray) -> np.ndarray:
    arr = np.asarray(values, dtype=np.float64).reshape(-1)
    return arr[np.isfinite(arr)]


def safe_float(value: float) -> float:
    if value is None or not np.isfinite(value):
        return float("nan")
    return float(value)


def quantile_bins(values: np.ndarray, bins: int) -> np.ndarray:
    values = finite_vector(values)
    if values.size == 0:
        return np.array([-np.inf, np.inf], dtype=np.float64)
    qs = np.linspace(0.0, 1.0, bins + 1)
    edges = np.quantile(values, qs)
    edges = np.unique(edges)
    if edges.size < 2:
        center = float(values[0])
        return np.array([center - 0.5, center + 0.5], dtype=np.float64)
    edges[0] = -np.inf
    edges[-1] = np.inf
    return edges


def digitize(values: np.ndarray, edges: np.ndarray) -> np.ndarray:
    return np.digitize(values, edges[1:-1], right=False).astype(np.int64)


def entropy_from_labels(labels: np.ndarray) -> float:
    labels = np.asarray(labels).reshape(-1)
    if labels.size == 0:
        return float("nan")
    _, counts = np.unique(labels, return_counts=True)
    probs = counts.astype(np.float64) / counts.sum()
    return float(-np.sum(probs * np.log2(probs + 1e-12)))


def joint_labels(columns: Sequence[np.ndarray]) -> np.ndarray:
    if not columns:
        return np.zeros(0, dtype=np.int64)
    stacked = np.vstack([np.asarray(col).reshape(-1) for col in columns]).T
    _, labels = np.unique(stacked, axis=0, return_inverse=True)
    return labels.astype(np.int64)


def mutual_information_labels(x: np.ndarray, y: np.ndarray) -> float:
    hx = entropy_from_labels(x)
    hy = entropy_from_labels(y)
    hxy = entropy_from_labels(joint_labels([x, y]))
    return float(hx + hy - hxy)


def normalized_mi_labels(x: np.ndarray, y: np.ndarray) -> float:
    if HAVE_SKLEARN:
        return float(normalized_mutual_info_score(x, y, average_method="geometric"))
    hx = entropy_from_labels(x)
    hy = entropy_from_labels(y)
    mi = mutual_information_labels(x, y)
    denom = math.sqrt(max(hx, 0.0) * max(hy, 0.0))
    return float(mi / denom) if denom > 0 else float("nan")


def standardize(matrix: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    mean = np.nanmean(matrix, axis=0)
    std = np.nanstd(matrix, axis=0)
    std[std < 1e-8] = 1.0
    z = (matrix - mean) / std
    return np.nan_to_num(z, copy=False), mean, std


def linear_unexplained_variance(y: np.ndarray, x: np.ndarray) -> float:
    mask = np.isfinite(y) & np.all(np.isfinite(x), axis=1)
    if mask.sum() < x.shape[1] + 2:
        return float("nan")
    yy = y[mask].astype(np.float64)
    xx = x[mask].astype(np.float64)
    xx = np.column_stack([np.ones(xx.shape[0]), xx])
    try:
        coef, *_ = np.linalg.lstsq(xx, yy, rcond=None)
    except np.linalg.LinAlgError:
        return float("nan")
    pred = xx @ coef
    var_y = np.var(yy)
    if var_y <= 1e-12:
        return float("nan")
    residual_ratio = np.var(yy - pred) / var_y
    return float(np.clip(residual_ratio, 0.0, 1.0))


def pairwise_correlations(columns: Sequence[np.ndarray]) -> List[float]:
    corr_values: List[float] = []
    for a, b in itertools.combinations(columns, 2):
        mask = np.isfinite(a) & np.isfinite(b)
        if mask.sum() < 3:
            continue
        aa = a[mask]
        bb = b[mask]
        if np.std(aa) <= 1e-12 or np.std(bb) <= 1e-12:
            continue
        corr_values.append(abs(float(np.corrcoef(aa, bb)[0, 1])))
    return corr_values


def pairwise_complex_correlations(columns: Sequence[np.ndarray]) -> List[float]:
    corr_values: List[float] = []
    for a, b in itertools.combinations(columns, 2):
        mask = np.isfinite(a.real) & np.isfinite(a.imag) & np.isfinite(b.real) & np.isfinite(b.imag)
        if mask.sum() < 3:
            continue
        aa = a[mask].astype(np.complex128)
        bb = b[mask].astype(np.complex128)
        aa = aa - np.mean(aa)
        bb = bb - np.mean(bb)
        den = np.sqrt(np.sum(np.abs(aa) ** 2) * np.sum(np.abs(bb) ** 2))
        if den <= 1e-12:
            continue
        corr_values.append(float(np.abs(np.sum(aa * np.conj(bb)) / den)))
    return corr_values


def select_subaps(available: Sequence[int], count: int, mode: str) -> Tuple[int, ...]:
    available = tuple(sorted(available))
    if count > len(available):
        return tuple()
    if count == len(available):
        return available
    if mode == "first":
        return available[:count]
    idx = np.linspace(0, len(available) - 1, count).round().astype(int)
    return tuple(available[int(i)] for i in idx)


def make_suffix(look_set: LookSet) -> str:
    return f"{look_set.prefix}_{look_set.pol}" if look_set.prefix else look_set.pol


def sample_windows(
    product_dir: Path,
    look_set: LookSet,
    selected_subaps: Tuple[int, ...],
    samples_per_lookset: int,
    patch_size: int,
    rng: np.random.Generator,
) -> Iterable[SampleBlock]:
    first_sa = selected_subaps[0]
    with rasterio.open(look_set.paths[first_sa]["i"]) as src_ref:
        height = src_ref.height
        width = src_ref.width
        if height < 2 or width < 2:
            return
        readers = []
        try:
            for sa in selected_subaps:
                readers.append(
                    (
                        sa,
                        rasterio.open(look_set.paths[sa]["i"]),
                        rasterio.open(look_set.paths[sa]["q"]),
                    )
                )

            for _ in range(samples_per_lookset):
                win_h = min(patch_size, height)
                win_w = min(patch_size, width)
                row = int(rng.integers(0, max(1, height - win_h + 1)))
                col = int(rng.integers(0, max(1, width - win_w + 1)))
                window = Window(col, row, win_w, win_h)
                stack = np.stack(
                    [read_complex_window(src_i, src_q, window) for _, src_i, src_q in readers],
                    axis=0,
                )
                yield SampleBlock(
                    product=str(product_dir),
                    prefix=look_set.prefix or "NA",
                    pol=look_set.pol,
                    suffix=make_suffix(look_set),
                    subaps=selected_subaps,
                    stack=stack,
                )
        finally:
            for _, src_i, src_q in readers:
                src_i.close()
                src_q.close()


def block_features(
    block: SampleBlock,
    win_size: int,
    max_pixels: int,
    base_mode: str,
    rng: np.random.Generator,
) -> Tuple[np.ndarray, np.ndarray, List[np.ndarray], List[np.ndarray], float, Dict[str, np.ndarray]]:
    stack = block.stack
    subaps = block.subaps
    flat_count = stack.shape[1] * stack.shape[2]

    base_maps = []
    base_names = []
    redundancy_vectors = []
    redundancy_complex = []
    for idx, sa in enumerate(subaps):
        look = stack[idx]
        amplitude = np.abs(look).astype(np.float32)
        log_power = np.log1p(amplitude ** 2).astype(np.float32)
        redundancy_vectors.append(amplitude.reshape(-1))
        redundancy_complex.append(look.reshape(-1))
        if base_mode == "iq":
            base_maps.extend([look.real.astype(np.float32), look.imag.astype(np.float32)])
            base_names.extend([f"I_SA{sa}", f"Q_SA{sa}"])
        elif base_mode == "log_power":
            base_maps.append(log_power)
            base_names.append(f"log_power_SA{sa}")
        elif base_mode == "subap_features":
            base_maps.extend([amplitude, np.angle(look).astype(np.float32), log_power])
            base_names.extend([f"amplitude_SA{sa}", f"phase_SA{sa}", f"log_power_SA{sa}"])
        else:
            raise ValueError(f"Unsupported base_mode: {base_mode}")

    derived_maps: Dict[str, np.ndarray] = {}
    coh_pairs = list(itertools.combinations(range(stack.shape[0]), 2))
    coh_sum = None
    for i, j in coh_pairs:
        gamma = coherence(stack[i], stack[j], win=win_size).astype(np.float32)
        name = f"gamma{subaps[i]}{subaps[j]}"
        derived_maps[name] = gamma
        coh_sum = gamma if coh_sum is None else coh_sum + gamma
    if coh_sum is not None:
        derived_maps["gamma_mean"] = (coh_sum / len(coh_pairs)).astype(np.float32)

    cov = covariance_terms([stack[idx] for idx in range(stack.shape[0])], win=win_size)
    for name, arr in cov.items():
        derived_maps[name] = arr.astype(np.float32)

    derived_maps["phase_variance"] = phase_variance(stack).astype(np.float32)
    stability_maps = [arr for arr in list(derived_maps.values())[:8]]
    stability_delta = spatial_delta(np.stack(stability_maps, axis=0)) if stability_maps else float("nan")

    if flat_count > max_pixels:
        pixel_idx = rng.choice(flat_count, size=max_pixels, replace=False)
    else:
        pixel_idx = np.arange(flat_count)

    base = np.column_stack([arr.reshape(-1)[pixel_idx] for arr in base_maps])
    derived = np.column_stack([arr.reshape(-1)[pixel_idx] for arr in derived_maps.values()])
    redundancy_vectors = [arr[pixel_idx] for arr in redundancy_vectors]
    redundancy_complex = [arr[pixel_idx] for arr in redundancy_complex]
    names = {"base": np.array(base_names), "derived": np.array(list(derived_maps.keys()))}
    return base, derived, redundancy_vectors, redundancy_complex, stability_delta, names


def spatial_delta(feature_maps: np.ndarray) -> float:
    if feature_maps.ndim != 3:
        return float("nan")
    deltas = []
    for arr in feature_maps:
        std = float(np.nanstd(arr))
        scale = std if std > 1e-8 else 1.0
        if arr.shape[0] > 1:
            deltas.append(float(np.nanmean(np.abs(np.diff(arr, axis=0))) / scale))
        if arr.shape[1] > 1:
            deltas.append(float(np.nanmean(np.abs(np.diff(arr, axis=1))) / scale))
    return float(np.nanmean(deltas)) if deltas else float("nan")


def kmeans(matrix: np.ndarray, k: int, rng: np.random.Generator, iterations: int = 40) -> np.ndarray:
    if matrix.shape[0] < k:
        return np.zeros(matrix.shape[0], dtype=np.int64)
    seeds = rng.choice(matrix.shape[0], size=k, replace=False)
    centers = matrix[seeds].copy()
    labels = np.zeros(matrix.shape[0], dtype=np.int64)
    for _ in range(iterations):
        dist = np.sum((matrix[:, None, :] - centers[None, :, :]) ** 2, axis=2)
        new_labels = np.argmin(dist, axis=1)
        if np.array_equal(labels, new_labels):
            break
        labels = new_labels
        for idx in range(k):
            members = matrix[labels == idx]
            if members.size:
                centers[idx] = members.mean(axis=0)
            else:
                centers[idx] = matrix[int(rng.integers(0, matrix.shape[0]))]
    return labels


def silhouette_score_sample(matrix: np.ndarray, labels: np.ndarray, max_points: int, rng: np.random.Generator) -> float:
    unique = np.unique(labels)
    if unique.size < 2 or matrix.shape[0] < 3:
        return float("nan")
    if matrix.shape[0] > max_points:
        idx = rng.choice(matrix.shape[0], size=max_points, replace=False)
        matrix = matrix[idx]
        labels = labels[idx]
        unique = np.unique(labels)
        if unique.size < 2:
            return float("nan")

    dist = np.sqrt(np.sum((matrix[:, None, :] - matrix[None, :, :]) ** 2, axis=2))
    values = []
    for i in range(matrix.shape[0]):
        same = labels == labels[i]
        other_labels = [label for label in unique if label != labels[i]]
        if same.sum() <= 1 or not other_labels:
            continue
        a = float(np.mean(dist[i, same & (np.arange(matrix.shape[0]) != i)]))
        b = min(float(np.mean(dist[i, labels == label])) for label in other_labels)
        denom = max(a, b)
        if denom > 1e-12:
            values.append((b - a) / denom)
    return float(np.mean(values)) if values else float("nan")


def cluster_metrics(matrix: np.ndarray, clusters: int, silhouette_points: int, seed: int) -> Tuple[float, float]:
    if matrix.shape[0] < max(10, clusters * 3):
        return float("nan"), float("nan")
    z, _, _ = standardize(matrix)
    if HAVE_SKLEARN:
        model_a = KMeans(n_clusters=clusters, n_init=10, random_state=seed)
        model_b = KMeans(n_clusters=clusters, n_init=10, random_state=seed + 1)
        labels_a = model_a.fit_predict(z)
        labels_b = model_b.fit_predict(z)
        rng = np.random.default_rng(seed)
        if z.shape[0] > silhouette_points:
            idx = rng.choice(z.shape[0], size=silhouette_points, replace=False)
            sil = silhouette_score(z[idx], labels_a[idx])
        else:
            sil = silhouette_score(z, labels_a)
        stability = normalized_mutual_info_score(labels_a, labels_b, average_method="geometric")
        return float(sil), float(stability)

    rng_a = np.random.default_rng(seed)
    rng_b = np.random.default_rng(seed + 1)
    labels_a = kmeans(z, clusters, rng_a)
    labels_b = kmeans(z, clusters, rng_b)
    sil = silhouette_score_sample(z, labels_a, silhouette_points, rng_a)
    stability = normalized_mi_labels(labels_a, labels_b)
    return sil, stability


def score_metrics(parts: Dict[str, float]) -> float:
    values = {
        "low_redundancy": 1.0 - np.nanmean([parts["redundancy_corr_mean"], parts["redundancy_nmi_mean"]]),
        "complementarity": np.nanmean(
            [
                parts["complement_cond_entropy_mean"],
                parts["complement_unexplained_variance_mean"],
                parts["complement_added_feature_entropy_mean"],
            ]
        ),
        "stability": 1.0 - np.nanmean(
            [
                parts["stability_spatial_delta_mean"],
                parts["stability_subsample_mean_delta"],
                parts["stability_subsample_std_delta"],
            ]
        ),
        "structure": np.nanmean([parts["cluster_silhouette"], parts["cluster_stability_nmi"]]),
    }
    clipped = [float(np.clip(v, 0.0, 1.0)) for v in values.values() if np.isfinite(v)]
    return float(np.mean(clipped)) if clipped else float("nan")


def evaluate_config(
    blocks: Sequence[SampleBlock],
    group_level: str,
    base_mode: str,
    subap_count: int,
    win_size: int,
    max_pixels_per_block: int,
    bins: int,
    clusters: int,
    silhouette_points: int,
    seed: int,
) -> ConfigMetrics:
    rng = np.random.default_rng(seed + subap_count * 1000 + win_size)
    base_chunks = []
    derived_chunks = []
    red_vector_chunks: List[List[np.ndarray]] = []
    red_complex_chunks: List[List[np.ndarray]] = []
    spatial_deltas = []
    products = set()

    for block in blocks:
        products.add(block.product)
        base, derived, red_vectors, red_complex, block_spatial_delta, _ = block_features(
            block, win_size, max_pixels_per_block, base_mode, rng
        )
        mask = np.all(np.isfinite(base), axis=1) & np.all(np.isfinite(derived), axis=1)
        if mask.sum() == 0:
            continue
        base_chunks.append(base[mask])
        derived_chunks.append(derived[mask])
        red_vector_chunks.append([arr[mask] for arr in red_vectors])
        red_complex_chunks.append([arr[mask] for arr in red_complex])
        spatial_deltas.append(block_spatial_delta)

    if not base_chunks:
        return ConfigMetrics(
            group_level,
            "NA",
            "NA",
            "NA",
            "NA",
            base_mode,
            subap_count,
            "NA",
            win_size,
            0,
            0,
            *([float("nan")] * 13),
        )

    base = np.vstack(base_chunks)
    derived = np.vstack(derived_chunks)
    sample_count = int(base.shape[0])

    red_vectors = [
        np.concatenate([chunk[idx] for chunk in red_vector_chunks])
        for idx in range(subap_count)
    ]
    red_complex = [
        np.concatenate([chunk[idx] for chunk in red_complex_chunks])
        for idx in range(subap_count)
    ]
    red_corr = pairwise_complex_correlations(red_complex) if base_mode == "iq" else pairwise_correlations(red_vectors)
    red_nmi = []
    base_disc = []
    for values in red_vectors:
        edges = quantile_bins(values, bins)
        base_disc.append(digitize(values, edges))
    for i, j in itertools.combinations(range(len(base_disc)), 2):
        red_nmi.append(normalized_mi_labels(base_disc[i], base_disc[j]))

    base_summary = np.nanmean(base, axis=1)
    base_summary_disc = digitize(base_summary, quantile_bins(base_summary, bins))
    cond_entropy = []
    unexplained = []
    added_entropy = []
    for idx in range(derived.shape[1]):
        feature = derived[:, idx]
        feature_disc = digitize(feature, quantile_bins(feature, bins))
        h_feature = entropy_from_labels(feature_disc)
        h_joint = entropy_from_labels(joint_labels([base_summary_disc, feature_disc]))
        h_base = entropy_from_labels(base_summary_disc)
        h_cond = max(0.0, h_joint - h_base)
        if h_feature > 1e-12:
            cond_entropy.append(h_cond / h_feature)
            added_entropy.append(h_cond / math.log2(max(bins, 2)))
        unexplained.append(linear_unexplained_variance(feature, base))

    idx = np.arange(sample_count)
    rng.shuffle(idx)
    half = max(1, sample_count // 2)
    a = derived[idx[:half]]
    b = derived[idx[half:]]
    if b.shape[0] == 0:
        mean_delta = float("nan")
        std_delta = float("nan")
    else:
        pooled_std = np.nanstd(derived, axis=0)
        pooled_std[pooled_std < 1e-8] = 1.0
        mean_delta = float(np.nanmean(np.abs(np.nanmean(a, axis=0) - np.nanmean(b, axis=0)) / pooled_std))
        std_delta = float(np.nanmean(np.abs(np.nanstd(a, axis=0) - np.nanstd(b, axis=0)) / pooled_std))

    cluster_matrix = np.hstack([base, derived])
    sil, cluster_nmi = cluster_metrics(cluster_matrix, clusters, silhouette_points, seed + win_size)

    parts = {
        "redundancy_corr_mean": safe_float(np.nanmean(red_corr) if red_corr else float("nan")),
        "redundancy_nmi_mean": safe_float(np.nanmean(red_nmi) if red_nmi else float("nan")),
        "complement_cond_entropy_mean": safe_float(np.nanmean(cond_entropy)),
        "complement_unexplained_variance_mean": safe_float(np.nanmean(unexplained)),
        "complement_added_feature_entropy_mean": safe_float(np.nanmean(added_entropy)),
        "stability_spatial_delta_mean": safe_float(np.nanmean(spatial_deltas)),
        "stability_subsample_mean_delta": safe_float(mean_delta),
        "stability_subsample_std_delta": safe_float(std_delta),
        "cluster_silhouette": safe_float((sil + 1.0) / 2.0 if np.isfinite(sil) else float("nan")),
        "cluster_stability_nmi": safe_float(cluster_nmi),
    }
    first = blocks[0]
    product = first.product if len(products) == 1 else "MULTIPLE"
    prefix = first.prefix if len({block.prefix for block in blocks}) == 1 else "MULTIPLE"
    pol = first.pol if len({block.pol for block in blocks}) == 1 else "MULTIPLE"
    suffix = first.suffix if len({block.suffix for block in blocks}) == 1 else "MULTIPLE"

    return ConfigMetrics(
        group_level=group_level,
        product=product,
        prefix=prefix,
        pol=pol,
        suffix=suffix,
        base_mode=base_mode,
        subap_count=subap_count,
        selected_subaps=";".join(f"SA{sa}" for sa in first.subaps),
        win_size=win_size,
        product_count=len(products),
        sample_count=sample_count,
        redundancy_corr_mean=parts["redundancy_corr_mean"],
        redundancy_corr_max=safe_float(np.nanmax(red_corr) if red_corr else float("nan")),
        redundancy_nmi_mean=parts["redundancy_nmi_mean"],
        redundancy_nmi_max=safe_float(np.nanmax(red_nmi) if red_nmi else float("nan")),
        complement_cond_entropy_mean=parts["complement_cond_entropy_mean"],
        complement_unexplained_variance_mean=parts["complement_unexplained_variance_mean"],
        complement_added_feature_entropy_mean=parts["complement_added_feature_entropy_mean"],
        stability_spatial_delta_mean=parts["stability_spatial_delta_mean"],
        stability_subsample_mean_delta=parts["stability_subsample_mean_delta"],
        stability_subsample_std_delta=parts["stability_subsample_std_delta"],
        cluster_silhouette=safe_float(sil),
        cluster_stability_nmi=parts["cluster_stability_nmi"],
        score=score_metrics(parts),
    )


def collect_blocks(
    input_root: Path,
    subap_counts: Optional[Sequence[int]],
    config_mode: str,
    selection: str,
    samples_per_lookset: int,
    patch_size: int,
    max_products: Optional[int],
    seed: int,
) -> Dict[Tuple[str, str, int], List[SampleBlock]]:
    rng = np.random.default_rng(seed)
    products = find_tc_products(input_root)
    if max_products is not None:
        products = products[:max_products]

    blocks_by_group: Dict[Tuple[str, str, int], List[SampleBlock]] = defaultdict(list)
    requested = sorted(set(subap_counts)) if subap_counts else None

    for product_dir in products:
        look_sets = discover_look_sets(product_dir)
        for look_set in look_sets:
            if config_mode == "available":
                count_and_subaps = [(len(look_set.subaps), tuple(look_set.subaps))]
            else:
                if requested is None:
                    raise ValueError("--subap-counts is required when --config-mode subsets")
                count_and_subaps = [
                    (count, select_subaps(look_set.subaps, count, selection))
                    for count in requested
                ]

            for count, selected in count_and_subaps:
                if not selected:
                    continue
                if requested is not None and count not in requested:
                    continue
                key = (str(product_dir), make_suffix(look_set), count)
                blocks_by_group[key].extend(
                    sample_windows(
                        product_dir=product_dir,
                        look_set=look_set,
                        selected_subaps=selected,
                        samples_per_lookset=samples_per_lookset,
                        patch_size=patch_size,
                        rng=rng,
                    )
                )

    return blocks_by_group


def aggregate_blocks_by_count(
    blocks_by_group: Dict[Tuple[str, str, int], List[SampleBlock]]
) -> Dict[int, List[SampleBlock]]:
    blocks_by_count: Dict[int, List[SampleBlock]] = defaultdict(list)
    for (_, _, count), blocks in blocks_by_group.items():
        blocks_by_count[count].extend(blocks)
    return blocks_by_count


def write_summary_csv(path: Path, metrics: Sequence[ConfigMetrics]) -> None:
    fields = list(ConfigMetrics._fields)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for item in metrics:
            writer.writerow({field: getattr(item, field) for field in fields})


def write_recommendation(path: Path, metrics: Sequence[ConfigMetrics], args: argparse.Namespace) -> None:
    valid = [item for item in metrics if np.isfinite(item.score)]
    valid.sort(key=lambda item: item.score, reverse=True)
    payload = {
        "input_root": str(args.input_root),
        "subap_counts": args.subap_counts,
        "config_mode": args.config_mode,
        "win_sizes": args.win_sizes,
        "selection": args.subap_selection,
        "base_mode": args.base_mode,
        "metric_backend": "scikit-learn" if HAVE_SKLEARN else "numpy-fallback",
        "score_definition": {
            "higher_is_better": True,
            "components": [
                "low redundancy between selected sub-apertures",
                "derived-feature conditional entropy and variance not explained by base SAR samples",
                "low normalized spatial/subsample instability",
                "silhouette and clustering stability",
            ],
        },
        "best_configuration": valid[0]._asdict() if valid else None,
        "ranked_configurations": [item._asdict() for item in valid],
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate sub-aperture count and ILC window-size choices with information metrics."
    )
    parser.add_argument("--input-root", type=Path, required=True, help="TC product root or single *_TC.data directory.")
    parser.add_argument("--output-root", type=Path, required=True, help="Directory for validation CSV/JSON reports.")
    parser.add_argument(
        "--config-mode",
        choices=["available", "subsets"],
        default="available",
        help=(
            "available evaluates the full set of SA files present in each product; "
            "subsets evaluates selected K-look subsets from each product."
        ),
    )
    parser.add_argument(
        "--subap-counts",
        type=parse_int_list,
        default=None,
        help=(
            "Optional comma-separated counts to keep. In available mode this filters discovered configurations; "
            "in subsets mode these are the K values to select."
        ),
    )
    parser.add_argument("--win-sizes", type=parse_int_list, default=[3, 5, 7], help="Comma-separated odd ILC window sizes.")
    parser.add_argument("--subap-selection", choices=["even", "first"], default="even", help="How to select K looks from available looks.")
    parser.add_argument(
        "--base-mode",
        choices=["iq", "log_power", "subap_features"],
        default="iq",
        help="Base representation used to test complementarity against derived features.",
    )
    parser.add_argument(
        "--include-aggregate",
        action="store_true",
        help="Also write aggregate rows pooling all product/swath/polarization groups for each configuration.",
    )
    parser.add_argument("--samples-per-lookset", type=int, default=8, help="Random patches sampled per product/look-set/count.")
    parser.add_argument("--patch-size", type=int, default=128, help="Patch width and height used for sampling.")
    parser.add_argument("--max-pixels-per-block", type=int, default=2048, help="Pixel samples kept per patch.")
    parser.add_argument("--max-products", type=int, default=None, help="Optional limit for smoke tests.")
    parser.add_argument("--bins", type=int, default=16, help="Quantile bins for entropy and mutual information.")
    parser.add_argument("--clusters", type=int, default=4, help="K-means clusters for structural discriminability.")
    parser.add_argument("--silhouette-points", type=int, default=1000, help="Maximum points used for silhouette computation.")
    parser.add_argument("--seed", type=int, default=13, help="Random seed.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.subap_counts is not None and any(value < 2 for value in args.subap_counts):
        raise ValueError("--subap-counts values must be >= 2")
    if any(value < 1 or value % 2 == 0 for value in args.win_sizes):
        raise ValueError("--win-sizes values must be positive odd integers")
    if args.patch_size < max(args.win_sizes):
        raise ValueError("--patch-size must be at least as large as the largest window size")

    args.output_root.mkdir(parents=True, exist_ok=True)

    print("Collecting sampled sub-aperture blocks...")
    blocks_by_group = collect_blocks(
        input_root=args.input_root,
        subap_counts=args.subap_counts,
        config_mode=args.config_mode,
        selection=args.subap_selection,
        samples_per_lookset=args.samples_per_lookset,
        patch_size=args.patch_size,
        max_products=args.max_products,
        seed=args.seed,
    )

    metrics: List[ConfigMetrics] = []
    for (product, suffix, subap_count), blocks in sorted(blocks_by_group.items()):
        if not blocks:
            continue
        for win_size in args.win_sizes:
            print(
                f"Evaluating product={product}, suffix={suffix}, "
                f"subap_count={subap_count}, win_size={win_size} on {len(blocks)} sampled blocks"
            )
            metrics.append(
                evaluate_config(
                    blocks=blocks,
                    group_level="lookset",
                    base_mode=args.base_mode,
                    subap_count=subap_count,
                    win_size=win_size,
                    max_pixels_per_block=args.max_pixels_per_block,
                    bins=args.bins,
                    clusters=args.clusters,
                    silhouette_points=args.silhouette_points,
                    seed=args.seed,
                )
            )

    if args.include_aggregate:
        blocks_by_count = aggregate_blocks_by_count(blocks_by_group)
        aggregate_counts = sorted(set(args.subap_counts)) if args.subap_counts is not None else sorted(blocks_by_count)
        for subap_count in aggregate_counts:
            blocks = blocks_by_count.get(subap_count, [])
            if not blocks:
                print(f"[warn] No sampled blocks available for aggregate subap_count={subap_count}")
                continue
            for win_size in args.win_sizes:
                print(f"Evaluating aggregate subap_count={subap_count}, win_size={win_size} on {len(blocks)} sampled blocks")
                metrics.append(
                    evaluate_config(
                        blocks=blocks,
                        group_level="aggregate",
                        base_mode=args.base_mode,
                        subap_count=subap_count,
                        win_size=win_size,
                        max_pixels_per_block=args.max_pixels_per_block,
                        bins=args.bins,
                        clusters=args.clusters,
                        silhouette_points=args.silhouette_points,
                        seed=args.seed,
                    )
                )

    if args.subap_counts is not None:
        sampled_counts = {key[2] for key in blocks_by_group}
        for subap_count in sorted(set(args.subap_counts) - sampled_counts):
            print(f"[warn] No sampled blocks available for subap_count={subap_count}")

    summary_path = args.output_root / "subap_validation_summary.csv"
    recommendation_path = args.output_root / "subap_validation_recommendation.json"
    write_summary_csv(summary_path, metrics)
    write_recommendation(recommendation_path, metrics, args)
    print(f"Summary: {summary_path}")
    print(f"Recommendation: {recommendation_path}")


if __name__ == "__main__":
    main()
