from pathlib import Path
import rasterio
import numpy as np
from rasterio.windows import Window
import imageio.v2 as imageio

# Root containing all processed products
root_dir = Path("/lustre/projects/1001/rdelprete/WORLDSAR/OUT/worldsar_output")

# Output directory for patches
out_dir = Path("/lustre/projects/1001/rdelprete/WORLDSAR/OUT/patches_center_png")
out_dir.mkdir(parents=True, exist_ok=True)

# Patch size
patch_size = 4000

# Polarizations to use
pols = ["VV", "VH"]

# Fixed normalization range for intensity
vmin = 0.0
vmax = 500.0

# Count stats
n_products = 0
n_expected = 0
n_saved = 0
n_null = 0
failed = []

stats_by_pol = {
    "VV": {"saved": 0, "null": 0, "failed": 0},
    "VH": {"saved": 0, "null": 0, "failed": 0},
}


def build_center_window(width: int, height: int, patch: int) -> Window:
    w = min(patch, width)
    h = min(patch, height)

    col0 = max(0, (width - w) // 2)
    row0 = max(0, (height - h) // 2)

    return Window(col_off=col0, row_off=row0, width=w, height=h)


def is_null_patch(arr: np.ndarray) -> bool:
    if not np.isfinite(arr).any():
        return True

    finite = arr[np.isfinite(arr)]

    if finite.size == 0:
        return True
    if np.all(finite == 0):
        return True
    if not np.any(finite > 0):
        return True

    return False


def intensity_to_png(inten: np.ndarray, vmin: float = 0.0, vmax: float = 500.0) -> np.ndarray:
    """
    Normalize intensity using fixed min/max and convert to uint8 PNG.
    """
    inten = np.asarray(inten, dtype=np.float32)
    inten = np.clip(inten, vmin, vmax)
    img = (inten - vmin) / (vmax - vmin)
    img = (img * 255.0).round().astype(np.uint8)
    return img


for tc_dir in sorted(root_dir.glob("*_ORB.data")):
    n_products += 1

    for pol in pols:
        n_expected += 1

        i_path = tc_dir / f"i_{pol}.img"
        q_path = tc_dir / f"q_{pol}.img"

        if not i_path.exists() or not q_path.exists():
            failed.append((tc_dir.name, pol, "missing i/q files"))
            stats_by_pol[pol]["failed"] += 1
            print(f"[MISS] {tc_dir.name} [{pol}] missing i/q")
            continue

        try:
            with rasterio.open(i_path) as src_i, rasterio.open(q_path) as src_q:
                if src_i.width != src_q.width or src_i.height != src_q.height:
                    failed.append((tc_dir.name, pol, "shape mismatch between i and q"))
                    stats_by_pol[pol]["failed"] += 1
                    print(f"[FAIL] {tc_dir.name} [{pol}] shape mismatch")
                    continue

                win = build_center_window(src_i.width, src_i.height, patch_size)

                i = src_i.read(1, window=win).astype(np.float32, copy=False)
                q = src_q.read(1, window=win).astype(np.float32, copy=False)

                inten = i * i + q * q

                if is_null_patch(inten):
                    n_null += 1
                    stats_by_pol[pol]["null"] += 1
                    print(f"[NULL] {tc_dir.name} [{pol}]")
                    continue

                img_png = intensity_to_png(inten, vmin=vmin, vmax=vmax)

                out_path = out_dir / f"{tc_dir.name[:-5]}_{pol}_center_patch.png"
                imageio.imwrite(out_path, img_png)

                n_saved += 1
                stats_by_pol[pol]["saved"] += 1
                print(f"[OK]   {tc_dir.name} [{pol}] -> {out_path.name}")

        except Exception as e:
            failed.append((tc_dir.name, pol, str(e)))
            stats_by_pol[pol]["failed"] += 1
            print(f"[ERR]  {tc_dir.name} [{pol}]: {e}")

print("\n=== SUMMARY ===")
print(f"Total products found   : {n_products}")
print(f"Total expected patches : {n_expected}")
print(f"Total PNGs saved       : {n_saved}")
print(f"Total null patches     : {n_null}")
print(f"Total failed           : {len(failed)}")

print("\n=== BY POLARIZATION ===")
for pol in pols:
    print(
        f"{pol}: saved={stats_by_pol[pol]['saved']}, "
        f"null={stats_by_pol[pol]['null']}, "
        f"failed={stats_by_pol[pol]['failed']}"
    )

if failed:
    print("\nFailed items:")
    for name, pol, reason in failed:
        print(f" - {name} [{pol}]: {reason}")