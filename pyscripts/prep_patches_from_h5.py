#!/usr/bin/env python3
import os
import glob
import argparse
import numpy as np
import torch
import h5py
from itertools import product
from safetensors.torch import save_file
from joblib import Parallel, delayed

# torch.set_num_threads(4)
# os.environ["OMP_NUM_THREADS"] = "4"

SUFFIXES = ["", "_SA1", "_SA2", "_SA3"]
POLS = ["VV", "VH"]


def iter_h5_files(root_dir, recursive=True):
    pattern = "**/*.h5" if recursive else "*.h5"
    return sorted(glob.glob(os.path.join(root_dir, pattern), recursive=recursive))


def get_patch_coords_from_shape(h, w, ps):
    h_cords = np.arange(0, h, ps)
    w_cords = np.arange(0, w, ps)
    h_cords = h_cords[h_cords + ps <= h]
    w_cords = w_cords[w_cords + ps <= w]
    return list(product(h_cords, w_cords))


def get_hw_from_h5(h5_path, group):
    with h5py.File(h5_path, "r") as f:
        g = f[group]
        for ref in ["i_VV", "i_VH"]:
            if ref in g:
                return g[ref].shape
        for k in g.keys():
            obj = g[k]
            if isinstance(obj, h5py.Dataset) and obj.ndim == 2:
                return obj.shape
    raise RuntimeError(f"Could not infer (H,W) from {h5_path}")


def read_intensity_patch(f, h0, w0, ps, group):
    g = f[group]
    chans = []
    for sfx in SUFFIXES:
        for pol in POLS:
            i_name = f"i_{pol}{sfx}"
            q_name = f"q_{pol}{sfx}"
            if i_name not in g or q_name not in g:
                raise KeyError(f"Missing {group}/{i_name} or {group}/{q_name}")
            i = g[i_name][h0:h0 + ps, w0:w0 + ps].astype(np.float32, copy=False)
            q = g[q_name][h0:h0 + ps, w0:w0 + ps].astype(np.float32, copy=False)
            p = i * i + q * q
            chans.append(p)
    return np.stack(chans, axis=0).astype(np.float32, copy=False)


def process_one_h5(h5_path, out_dir, ps, group, zero_thr, ratio_thr):
    base = os.path.splitext(os.path.basename(h5_path))[0]
    try:
        H, W = get_hw_from_h5(h5_path, group)
        coords = get_patch_coords_from_shape(H, W, ps)

        n_total = len(coords)
        n_saved = 0
        n_skipped = 0

        with h5py.File(h5_path, "r") as f:
            for h0, w0 in coords:
                x = read_intensity_patch(f, h0, w0, ps, group)  # (C, ps, ps)

                # Filter based on zeros in channel 0 (VV original)
                if ratio_thr is not None:
                    no_data_ratio = float((x[0] <= zero_thr).sum() / (ps * ps))
                    if no_data_ratio > ratio_thr:
                        n_skipped += 1
                        continue

                x_t = torch.from_numpy(x)
                fname = f"{base}_{h0}_{w0}.safetensors"
                out_path = os.path.join(out_dir, fname)
                save_file({"x": x_t}, out_path)
                n_saved += 1

        return (h5_path, n_saved, n_total, n_skipped, None)

    except Exception as e:
        return (h5_path, 0, 0, 0, str(e))


def _auto_workers():
    env = os.environ.get("JOBS", "").strip()
    if env:
        try:
            n = int(env)
        except ValueError:
            n = 0
    else:
        n = 0

    if n <= 0:
        n = os.cpu_count() or 1

    return max(1, min(n, 32))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in_dir", required=True, help="Root directory containing .h5 files")
    ap.add_argument("--out_dir", required=True, help="Output directory for .safetensors patches")
    ap.add_argument("--patch_size", type=int, default=96)
    ap.add_argument("--group", default="bands", help="H5 group name, default: bands")
    ap.add_argument("--no_recursive", action="store_true", help="Do not search recursively for .h5")
    ap.add_argument("--ratio_thr", type=float, default=1.1, help="Skip patch if zero ratio > ratio_thr (channel 0)")
    ap.add_argument("--zero_thr", type=float, default=0.0, help="Consider values <= zero_thr as zero")
    args = ap.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)

    h5_files = iter_h5_files(args.in_dir, recursive=(not args.no_recursive))
    print(f"Found {len(h5_files)} .h5 files under: {args.in_dir}")
    if not h5_files:
        return

    n_jobs = _auto_workers()

    results = Parallel(n_jobs=n_jobs, prefer="threads")(
        delayed(process_one_h5)(p, args.out_dir, args.patch_size, args.group, args.zero_thr, args.ratio_thr)
        for p in h5_files
    )

    ok = [r for r in results if r[4] is None]
    bad = [r for r in results if r[4] is not None]

    total_saved = sum(r[1] for r in ok)
    total_total = sum(r[2] for r in ok)
    total_skipped = sum(r[3] for r in ok)

    print("\nSummary")
    print(f"  OK files:   {len(ok)}")
    print(f"  Bad files:  {len(bad)}")
    print(f"  Patches total candidates: {total_total}")
    print(f"  Patches saved:            {total_saved}")
    print(f"  Patches skipped:          {total_skipped}")
    print(f"  Output dir: {args.out_dir}")

    if bad:
        print("\nErrors (first 20):")
        for p, *_rest, err in bad[:20]:
            print(f"  {p}: {err}")


if __name__ == "__main__":
    main()