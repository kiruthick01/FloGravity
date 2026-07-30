"""Core pipeline: DEM path + start/end lon/lat -> a routed path, decoupled from
argparse and file I/O so both the CLI and the API can call the same code.
"""

import math
from dataclasses import dataclass

import numpy as np
import rasterio
from pyproj import Transformer

from drainage_lcp.cost_surface import IMPASSABLE_COST, compute_total_cost, route_isotropic
from drainage_lcp.dem_io import load_dem
from drainage_lcp.hydrology import compute_hydrology
from drainage_lcp.routing import FDIR_TO_BEARING, route_anisotropic
from drainage_lcp.terrain import compute_slope

SIGNIFICANT_CHANNEL_THRESHOLD = 0.5
PERPENDICULAR_ALIGNMENT_THRESHOLD = 0.5


@dataclass
class PipelineResult:
    path_rc: list
    path_lonlat: list
    cost: float
    length_m: float
    slope_min: float
    slope_mean: float
    slope_max: float
    significant_channel_crossings: int
    elevation_drop_m: float
    # Raw arrays, for callers (the CLI) that need to render plots/reports.
    elevation: np.ndarray
    slope_deg: np.ndarray
    slope_pct: np.ndarray
    acc_arr: np.ndarray
    fdir_arr: np.ndarray
    transform: object
    crs: object
    original_crs: object
    pixel_size_m: float


def lonlat_to_pixel(lon, lat, dem_crs, transform, shape, label):
    transformer = Transformer.from_crs("EPSG:4326", dem_crs, always_xy=True)
    x, y = transformer.transform(lon, lat)
    row, col = rasterio.transform.rowcol(transform, x, y)
    nrows, ncols = shape
    if not (0 <= row < nrows and 0 <= col < ncols):
        raise ValueError(
            f"{label} point (lon={lon}, lat={lat}) falls outside the DEM extent "
            f"(maps to pixel {row},{col}, grid is {shape})"
        )
    return int(row), int(col)


def _step_bearing(dr, dc):
    return math.degrees(math.atan2(dc, -dr)) % 360.0


def _alignment(travel_bearing, flow_bearing):
    return abs(math.cos(math.radians(travel_bearing - flow_bearing)))


def _path_diagnostics(path, fdir_arr, channel_pen):
    """Per-step alignment with local flow direction, for the channel-crossing count."""
    crossings = 0
    for (r0, c0), (r1, c1) in zip(path[:-1], path[1:]):
        flow_bearing = FDIR_TO_BEARING.get(int(fdir_arr[r1, c1]))
        if flow_bearing is None:
            continue
        travel_bearing = _step_bearing(r1 - r0, c1 - c0)
        alignment = _alignment(travel_bearing, flow_bearing)
        chan_pen = channel_pen[r1, c1]
        if (
            not np.isnan(chan_pen)
            and chan_pen > SIGNIFICANT_CHANNEL_THRESHOLD
            and alignment < PERPENDICULAR_ALIGNMENT_THRESHOLD
        ):
            crossings += 1
    return crossings


def _path_to_lonlat(path_rc, transform, working_crs):
    xs, ys = [], []
    for row, col in path_rc:
        x, y = rasterio.transform.xy(transform, row, col)
        xs.append(x)
        ys.append(y)

    length_m = float(np.sum(np.hypot(np.diff(xs), np.diff(ys))))

    transformer = Transformer.from_crs(working_crs, "EPSG:4326", always_xy=True)
    lons, lats = transformer.transform(xs, ys)
    path_lonlat = [[float(lon), float(lat)] for lon, lat in zip(lons, lats)]
    return path_lonlat, length_m


def run_pipeline(
    dem_path,
    start_lonlat,
    end_lonlat,
    *,
    min_slope_pct=0.5,
    max_slope_pct=15.0,
    hard_max_slope_pct=45.0,
    w_slope=0.5,
    w_channel=0.3,
    w_direction=0.2,
    mode="anisotropic",
):
    """Run the full DEM -> least-cost-route pipeline for one start/end pair.

    start_lonlat / end_lonlat are (lon, lat) in WGS84. Raises ValueError for
    out-of-bounds or impassable start/end points.
    """
    with rasterio.open(dem_path) as src:
        original_crs = src.crs

    elevation, transform, crs, nodata_mask, pixel_size_m = load_dem(dem_path)
    slope_deg, slope_pct = compute_slope(elevation, pixel_size_m, nodata_mask)
    fdir_arr, acc_arr = compute_hydrology(elevation, transform, crs, nodata_mask)
    total_cost, channel_pen = compute_total_cost(
        slope_pct,
        acc_arr,
        nodata_mask,
        min_slope_pct=min_slope_pct,
        max_slope_pct=max_slope_pct,
        hard_max_slope_pct=hard_max_slope_pct,
        w_slope=w_slope,
        w_channel=w_channel,
    )

    start_rc = lonlat_to_pixel(start_lonlat[0], start_lonlat[1], crs, transform, elevation.shape, "start")
    end_rc = lonlat_to_pixel(end_lonlat[0], end_lonlat[1], crs, transform, elevation.shape, "end")

    for label, rc in (("start", start_rc), ("end", end_rc)):
        if total_cost[rc] >= IMPASSABLE_COST:
            raise ValueError(f"{label} point {rc} sits on an impassable (nodata/hard-max-slope) cell")

    if mode == "isotropic":
        path, path_cost = route_isotropic(total_cost, start_rc, end_rc)
    else:
        path, path_cost = route_anisotropic(
            elevation,
            pixel_size_m,
            fdir_arr,
            channel_pen,
            nodata_mask,
            start_rc,
            end_rc,
            min_slope_pct=min_slope_pct,
            max_slope_pct=max_slope_pct,
            hard_max_slope_pct=hard_max_slope_pct,
            w_slope=w_slope,
            w_channel=w_channel,
            w_direction=w_direction,
        )

    path_lonlat, length_m = _path_to_lonlat(path, transform, crs)

    rows = [r for r, _ in path]
    cols = [c for _, c in path]
    slope_profile = slope_pct[rows, cols]
    crossings = _path_diagnostics(path, fdir_arr, channel_pen)
    elevation_drop = float(elevation[rows[0], cols[0]] - elevation[rows[-1], cols[-1]])

    return PipelineResult(
        path_rc=path,
        path_lonlat=path_lonlat,
        cost=float(path_cost),
        length_m=length_m,
        slope_min=float(np.nanmin(slope_profile)),
        slope_mean=float(np.nanmean(slope_profile)),
        slope_max=float(np.nanmax(slope_profile)),
        significant_channel_crossings=crossings,
        elevation_drop_m=elevation_drop,
        elevation=elevation,
        slope_deg=slope_deg,
        slope_pct=slope_pct,
        acc_arr=acc_arr,
        fdir_arr=fdir_arr,
        transform=transform,
        crs=crs,
        original_crs=original_crs,
        pixel_size_m=pixel_size_m,
    )
