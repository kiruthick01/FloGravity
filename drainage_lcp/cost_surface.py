"""Phase 4: isotropic (per-cell) cost surface and MVP routing."""

from pathlib import Path

import numpy as np
from skimage.graph import route_through_array

IMPASSABLE_COST = 1e6


def compute_channel_penalty(acc, nodata_mask=None):
    """log1p(flow accumulation), min-max normalized to [0, 1]. nodata -> nan."""
    log_acc = np.log1p(np.clip(acc, a_min=0, a_max=None).astype(np.float64))
    valid = ~nodata_mask if nodata_mask is not None else np.ones_like(acc, dtype=bool)

    lo = log_acc[valid].min()
    hi = log_acc[valid].max()
    span = hi - lo
    if span <= 0:
        penalty = np.zeros_like(log_acc)
    else:
        penalty = np.clip((log_acc - lo) / span, 0.0, 1.0)

    if nodata_mask is not None:
        penalty = np.where(nodata_mask, np.nan, penalty)
    return penalty


def compute_slope_penalty(slope_pct, min_slope_pct=0.5, max_slope_pct=15.0, hard_max_slope_pct=45.0):
    """0 inside [min, max] band, linear penalty outside it, IMPASSABLE_COST beyond hard max."""
    penalty = np.zeros_like(slope_pct, dtype=np.float64)

    below = slope_pct < min_slope_pct
    denom_below = max(min_slope_pct, 1e-6)
    penalty = np.where(below, (min_slope_pct - slope_pct) / denom_below, penalty)

    above_soft = (slope_pct > max_slope_pct) & (slope_pct <= hard_max_slope_pct)
    denom_soft = max(hard_max_slope_pct - max_slope_pct, 1e-6)
    penalty = np.where(above_soft, (slope_pct - max_slope_pct) / denom_soft, penalty)

    above_hard = slope_pct > hard_max_slope_pct
    penalty = np.where(above_hard, IMPASSABLE_COST, penalty)

    return penalty


def compute_total_cost(
    slope_pct,
    acc,
    nodata_mask,
    min_slope_pct=0.5,
    max_slope_pct=15.0,
    hard_max_slope_pct=45.0,
    w_slope=0.5,
    w_channel=0.3,
    base_cost=1.0,
):
    """Returns (total_cost, channel_penalty) rasters, nodata forced to IMPASSABLE_COST."""
    slope_pen = compute_slope_penalty(slope_pct, min_slope_pct, max_slope_pct, hard_max_slope_pct)
    channel_pen = compute_channel_penalty(acc, nodata_mask)

    total = base_cost + w_slope * slope_pen + w_channel * np.nan_to_num(channel_pen, nan=0.0)
    total = np.where(nodata_mask, IMPASSABLE_COST, total)

    return total, channel_pen


def route_isotropic(cost, start_rc, end_rc):
    """Least-cost path over `cost` from start_rc to end_rc, both (row, col) tuples."""
    path_indices, path_cost = route_through_array(
        cost, start_rc, end_rc, fully_connected=True, geometric=True
    )
    return path_indices, path_cost


if __name__ == "__main__":
    import matplotlib.pyplot as plt
    import rasterio
    from pyproj import Transformer
    from skimage.draw import line as raster_line

    from drainage_lcp.dem_io import load_dem
    from drainage_lcp.hydrology import compute_hydrology
    from drainage_lcp.terrain import compute_slope

    sample_path = Path(__file__).resolve().parent.parent / "sample_data" / "dem.tif"
    elevation, transform, crs, nodata_mask, pixel_size_m = load_dem(sample_path)
    slope_deg, slope_pct = compute_slope(elevation, pixel_size_m, nodata_mask)
    fdir_arr, acc_arr = compute_hydrology(elevation, transform, crs, nodata_mask)

    total_cost, channel_pen = compute_total_cost(slope_pct, acc_arr, nodata_mask)

    to_dem_crs = Transformer.from_crs("EPSG:4326", crs, always_xy=True)
    start_lonlat = (-97.35, 32.60)
    end_lonlat = (-97.25, 32.75)
    start_x, start_y = to_dem_crs.transform(*start_lonlat)
    end_x, end_y = to_dem_crs.transform(*end_lonlat)
    start_rc = rasterio.transform.rowcol(transform, start_x, start_y)
    end_rc = rasterio.transform.rowcol(transform, end_x, end_y)
    print(f"start_rc={start_rc}, end_rc={end_rc}, shape={elevation.shape}")

    path_indices, path_cost = route_isotropic(total_cost, start_rc, end_rc)
    path_rows = [p[0] for p in path_indices]
    path_cols = [p[1] for p in path_indices]

    straight_rows, straight_cols = raster_line(*start_rc, *end_rc)

    path_mean_slope = np.nanmean(slope_pct[path_rows, path_cols])
    straight_mean_slope = np.nanmean(slope_pct[straight_rows, straight_cols])
    print(f"Path cost: {path_cost:.1f}, length: {len(path_indices)} cells")
    print(f"Mean slope% along LCP path: {path_mean_slope:.2f}")
    print(f"Mean slope% along straight line: {straight_mean_slope:.2f}")

    out_dir = Path(__file__).resolve().parent.parent / "outputs"
    out_dir.mkdir(exist_ok=True)
    plt.figure(figsize=(8, 9))
    plt.imshow(slope_pct, cmap="terrain")
    plt.colorbar(label="slope %")
    plt.plot(straight_cols, straight_rows, color="red", linewidth=1, linestyle="--", label="straight line")
    plt.plot(path_cols, path_rows, color="cyan", linewidth=1.5, label="isotropic LCP")
    plt.scatter(*start_rc[::-1], color="lime", zorder=5, label="start")
    plt.scatter(*end_rc[::-1], color="black", zorder=5, label="end")
    plt.legend()
    plt.title("Phase 4: isotropic least-cost path vs straight line")
    plt.savefig(out_dir / "phase4_isotropic_path_check.png", dpi=150)
    print(f"Saved check plot to {out_dir / 'phase4_isotropic_path_check.png'}")
