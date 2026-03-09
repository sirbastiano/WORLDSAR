from pathlib import Path
import rasterio
import numpy as np
from rasterio.windows import Window
import imageio.v2 as imageio

# Root directory containing SAFE products
root_dir = Path("/lustre/projects/1001/rdelprete/WORLDSAR/phidown_data")

# Output directory
out_dir = Path("/lustre/projects/1001/rdelprete/WORLDSAR/OUT/slc_patches_png")
out_dir.mkdir(parents=True, exist_ok=True)

patch_size = 4000

vmin = 0.0
vmax = 500.0

n_products = 0
n_expected = 0
n_saved = 0
n_null = 0
failed = []

stats_by_pol = {
    "VV": {"saved": 0, "null": 0, "failed": 0},
    "VH": {"saved": 0, "null": 0, "failed": 0},
}


def build_center_window(width, height, patch):

    w = min(patch, width)
    h = min(patch, height)

    col0 = max(0, (width - w) // 2)
    row0 = max(0, (height - h) // 2)

    return Window(col0, row0, w, h)


def intensity_to_png(inten):

    inten = np.clip(inten, vmin, vmax)

    img = (inten - vmin) / (vmax - vmin)

    return (img * 255).astype(np.uint8)


def is_null_patch(arr):

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


for safe in sorted(root_dir.glob("*.SAFE")):

    n_products += 1

    meas_dir = safe / "measurement"

    if not meas_dir.exists():
        continue

    for tif in meas_dir.glob("*.tiff"):

        name = tif.name.lower()

        if "vv" in name:
            pol = "VV"
        elif "vh" in name:
            pol = "VH"
        else:
            continue

        n_expected += 1

        try:

            with rasterio.open(tif) as src:

                win = build_center_window(src.width, src.height, patch_size)

                im = src.read(1, window=win)

                i = im.real.astype(np.float32, copy=False)
                q = im.imag.astype(np.float32, copy=False)

                inten = i * i + q * q

                if is_null_patch(inten):

                    n_null += 1
                    stats_by_pol[pol]["null"] += 1

                    print(f"[NULL] {safe.name} [{pol}]")
                    continue

                img = intensity_to_png(inten)

                out_name = f"{safe.name[:-5]}_{pol}_center_patch.png"
                out_path = out_dir / out_name

                imageio.imwrite(out_path, img)

                n_saved += 1
                stats_by_pol[pol]["saved"] += 1

                print(f"[OK] {safe.name} [{pol}] -> {out_name}")

        except Exception as e:

            failed.append((safe.name, pol, str(e)))
            stats_by_pol[pol]["failed"] += 1

            print(f"[ERR] {safe.name} [{pol}] {e}")


print("\n========== SUMMARY ==========")

print("Products:", n_products)
print("Expected images:", n_expected)
print("Saved patches:", n_saved)
print("Null patches:", n_null)
print("Failed:", len(failed))

print("\n--- BY POLARIZATION ---")

for pol in stats_by_pol:
    s = stats_by_pol[pol]
    print(pol, s)

if failed:

    print("\nFailed items:")

    for f in failed:
        print(f)