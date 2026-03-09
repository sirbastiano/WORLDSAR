import rasterio
import numpy as np
from rasterio.windows import Window
from rasterio.windows import transform as window_transform
import matplotlib.pyplot as plt
# Inputs
path_in = "/lustre/projects/1001/rdelprete/WORLDSAR/OUT/worldsar_output/S1A_S4_SLC__1SDV_20160629T224400_20160629T224425_011932_012621_65C3_ORB.data/"
i_path = f"{path_in}i_VV.img"   # adjust if your files are named i_IW1_VV.img, etc.
q_path = f"{path_in}q_VV.img"

path_out = "/lustre/projects/1001/rdelprete/WORLDSAR/OUT/S1A_S4_SLC__1SDV_20160629T224400_20160629T224425_011932_012621_65C3_ORBVV_v2.tif"

# Your window (pixel coordinates in the raster)
row0 = 5000   # start row
col0 = 5000   # start col
patch = 4000  # size (rows=cols)

with rasterio.open(i_path) as src_i, rasterio.open(q_path) as src_q:
    win = Window(col0, row0, patch, patch)

    i = src_i.read(1, window=win).astype(np.float32, copy=False)
    q = src_q.read(1, window=win).astype(np.float32, copy=False)

    inten = i * i + q * q

    plt.figure(figsize=[10,5])
    plt.imshow(inten)
    plt.show()
    profile = src_i.profile.copy()
    profile.update(
        driver="GTiff",
        height=patch,
        width=patch,
        count=1,
        dtype="float32",
        transform=window_transform(win, src_i.transform),
    )

    with rasterio.open(path_out, "w", **profile) as dst:
        dst.write(inten, 1)

print("Saved:", path_out)