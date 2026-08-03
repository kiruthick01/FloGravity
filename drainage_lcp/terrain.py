"""Terrain derivatives: slope (degrees and percent) and aspect."""

from pathlib import Path

import numpy as np


def compute_slope(elevation, cellsize_m, nodata_mask=None):
    """Return (slope_deg, slope_pct), same shape as elevation, nodata -> nan."""
    # float32 (not float64): halves memory for these DEM-sized arrays, which
    # matters on memory-constrained deployment targets (512MB free-tier
    # containers). Slope precision loss at float32 is well below anything
    # that affects routing decisions.
    elev = elevation.astype(np.float32)
    if nodata_mask is not None:
        elev = np.where(nodata_mask, np.nan, elev)

    dz_dy, dz_dx = np.gradient(elev, cellsize_m)
    slope_rad = np.arctan(np.hypot(dz_dx, dz_dy))
    slope_deg = np.degrees(slope_rad)
    slope_pct = 100.0 * np.tan(slope_rad)

    if nodata_mask is not None:
        slope_deg = np.where(nodata_mask, np.nan, slope_deg)
        slope_pct = np.where(nodata_mask, np.nan, slope_pct)

    return slope_deg, slope_pct


def compute_aspect(elevation, cellsize_m, nodata_mask=None):
    """Return aspect_deg (0-360, compass bearing of steepest descent), nodata -> nan.

    Row index increases southward (north-up raster) and column index increases
    eastward, so the raw np.gradient outputs need a sign flip on the y-axis to
    get a true north-positive component before converting to a compass bearing.
    """
    elev = elevation.astype(np.float32)
    if nodata_mask is not None:
        elev = np.where(nodata_mask, np.nan, elev)

    dz_dy, dz_dx = np.gradient(elev, cellsize_m)
    aspect_deg = np.degrees(np.arctan2(-dz_dx, dz_dy)) % 360.0

    if nodata_mask is not None:
        aspect_deg = np.where(nodata_mask, np.nan, aspect_deg)

    return aspect_deg


if __name__ == "__main__":
    from drainage_lcp.dem_io import load_dem

    sample_path = Path(__file__).resolve().parent.parent / "sample_data" / "dem.tif"
    elevation, transform, crs, nodata_mask, pixel_size_m = load_dem(sample_path)

    slope_deg, slope_pct = compute_slope(elevation, pixel_size_m, nodata_mask)
    aspect_deg = compute_aspect(elevation, pixel_size_m, nodata_mask)

    print(f"Shapes match elevation: {slope_deg.shape == elevation.shape == aspect_deg.shape}")
    print(f"Slope deg min/mean/max: {np.nanmin(slope_deg):.2f} / {np.nanmean(slope_deg):.2f} / {np.nanmax(slope_deg):.2f}")
    print(f"Slope pct min/mean/max: {np.nanmin(slope_pct):.2f} / {np.nanmean(slope_pct):.2f} / {np.nanmax(slope_pct):.2f}")
    print(f"Aspect deg min/max: {np.nanmin(aspect_deg):.2f} / {np.nanmax(aspect_deg):.2f}")
    print(f"NaN count slope/aspect: {np.isnan(slope_deg).sum()} / {np.isnan(aspect_deg).sum()} (nodata cells: {int(nodata_mask.sum())})")
