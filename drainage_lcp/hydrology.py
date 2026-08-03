"""Hydrological derivatives: DEM conditioning, D8 flow direction, flow accumulation."""

import gc
from pathlib import Path

import numpy as np
from pysheds.grid import Grid
from pysheds.sview import Raster, ViewFinder

# ESRI D8 direction codes, in (N, NE, E, SE, S, SW, W, NW) order.
DIRMAP = (64, 128, 1, 2, 4, 8, 16, 32)


def compute_hydrology(elevation, transform, crs, nodata_mask):
    """Condition the DEM and compute D8 flow direction + flow accumulation.

    Returns (fdir, acc) as numpy arrays aligned to the input elevation grid.
    fdir cell values follow DIRMAP (N, NE, E, SE, S, SW, W, NW -> 64,128,1,2,4,8,16,32).
    """
    dem_arr = elevation.astype(np.float64).copy()
    dem_arr[nodata_mask] = np.nan

    viewfinder = ViewFinder(affine=transform, shape=dem_arr.shape, nodata=np.nan, crs=crs)
    dem = Raster(dem_arr, viewfinder=viewfinder)
    grid = Grid(viewfinder=viewfinder)

    # Conditioning order matters: pits, then depressions, then flats. pysheds
    # forces float64 internally regardless of our input dtype, and each stage
    # holds a full DEM-sized copy -- del + gc.collect() as we go so at most
    # two conditioning copies are ever resident at once, not four.
    pit_filled = grid.fill_pits(dem)
    del dem
    flooded = grid.fill_depressions(pit_filled)
    del pit_filled
    inflated = grid.resolve_flats(flooded)
    del flooded
    gc.collect()

    fdir = grid.flowdir(inflated, dirmap=DIRMAP)
    del inflated
    acc = grid.accumulation(fdir, dirmap=DIRMAP)
    gc.collect()

    # fdir values are one of 8 small direction codes (max 255); acc is a cell
    # count that fits comfortably in float32 for any DEM this project fetches.
    fdir_arr = np.asarray(fdir).astype(np.int16)
    acc_arr = np.asarray(acc).astype(np.float32)
    del fdir, acc
    gc.collect()

    if fdir_arr.shape != elevation.shape or acc_arr.shape != elevation.shape:
        raise ValueError(
            f"pysheds grid shape {fdir_arr.shape} does not match elevation grid "
            f"{elevation.shape}"
        )

    return fdir_arr, acc_arr


if __name__ == "__main__":
    from drainage_lcp.dem_io import load_dem

    sample_path = Path(__file__).resolve().parent.parent / "sample_data" / "dem.tif"
    elevation, transform, crs, nodata_mask, pixel_size_m = load_dem(sample_path)

    fdir_arr, acc_arr = compute_hydrology(elevation, transform, crs, nodata_mask)

    print(f"fdir shape: {fdir_arr.shape}, acc shape: {acc_arr.shape}")
    print(f"fdir unique values: {sorted(np.unique(fdir_arr[~nodata_mask]).tolist())}")
    print(f"acc min/mean/max: {np.nanmin(acc_arr):.1f} / {np.nanmean(acc_arr):.1f} / {np.nanmax(acc_arr):.1f}")

    import matplotlib.pyplot as plt

    out_dir = Path(__file__).resolve().parent.parent / "outputs"
    out_dir.mkdir(exist_ok=True)
    log_acc = np.log1p(acc_arr)
    plt.figure(figsize=(8, 8))
    plt.imshow(log_acc, cmap="Blues")
    plt.title("log1p(flow accumulation)")
    plt.colorbar(label="log1p(acc)")
    plt.savefig(out_dir / "phase3_flow_accumulation_check.png", dpi=150)
    print(f"Saved check plot to {out_dir / 'phase3_flow_accumulation_check.png'}")
