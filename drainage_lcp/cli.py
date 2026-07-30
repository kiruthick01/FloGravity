"""Phase 6: CLI wiring the full pipeline (Phases 1-5) into a single run."""

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np
import rasterio

from drainage_lcp.pipeline import run_pipeline
from drainage_lcp.terrain import compute_aspect


def _normalize_argv(argv):
    """Rewrite '--start -97.35,32.60' as '--start=-97.35,32.60'.

    argparse can't tell a negative-lon coordinate apart from an option flag
    when it's a separate token, so the space form of --start/--end (as shown
    in this project's own CLI examples) would otherwise fail to parse.
    """
    argv = list(argv)
    for flag in ("--start", "--end"):
        if flag in argv:
            idx = argv.index(flag)
            if idx + 1 < len(argv):
                argv[idx] = f"{flag}={argv[idx + 1]}"
                del argv[idx + 1]
    return argv


def parse_args(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    argv = _normalize_argv(argv)

    parser = argparse.ArgumentParser(
        description="Hydraulically-constrained least-cost path for a gravity-fed "
        "drainage route over an arbitrary DEM."
    )
    parser.add_argument("--dem", required=True, type=Path, help="Path to a DEM GeoTIFF")
    parser.add_argument("--start", required=True, help="Start point, 'lon,lat'")
    parser.add_argument("--end", required=True, help="End point, 'lon,lat'")
    parser.add_argument("--coord-format", choices=["lonlat"], default="lonlat")
    parser.add_argument("--min-slope-pct", type=float, default=0.5)
    parser.add_argument("--max-slope-pct", type=float, default=15.0)
    parser.add_argument("--hard-max-slope-pct", type=float, default=45.0)
    parser.add_argument("--w-slope", type=float, default=0.5)
    parser.add_argument("--w-channel", type=float, default=0.3)
    parser.add_argument("--w-direction", type=float, default=0.2)
    parser.add_argument("--mode", choices=["isotropic", "anisotropic"], default="anisotropic")
    parser.add_argument("--output-dir", required=True, type=Path)
    return parser.parse_args(argv)


def _parse_lonlat(text, label):
    parts = text.split(",")
    if len(parts) != 2:
        raise ValueError(f"--{label} must be 'lon,lat', got {text!r}")
    try:
        return float(parts[0]), float(parts[1])
    except ValueError as exc:
        raise ValueError(f"--{label} must be numeric 'lon,lat', got {text!r}") from exc


def _hillshade(slope_deg, aspect_deg, azimuth_deg=315.0, altitude_deg=45.0):
    az = math.radians(azimuth_deg)
    alt = math.radians(altitude_deg)
    slope_rad = np.radians(slope_deg)
    aspect_rad = np.radians(aspect_deg)
    shade = np.cos(alt) * np.cos(slope_rad) + np.sin(alt) * np.sin(slope_rad) * np.cos(az - aspect_rad)
    return np.clip(shade, 0.0, 1.0)


def _write_geojson(path_lonlat, length_m, original_crs, working_crs, out_path):
    if original_crs is not None and original_crs != working_crs:
        from pyproj import Transformer

        transformer = Transformer.from_crs("EPSG:4326", original_crs, always_xy=True)
        lons = [p[0] for p in path_lonlat]
        lats = [p[1] for p in path_lonlat]
        xs, ys = transformer.transform(lons, lats)
        coords = [[float(x), float(y)] for x, y in zip(xs, ys)]
        out_crs = original_crs
    else:
        coords = path_lonlat
        out_crs = working_crs

    geojson = {
        "type": "FeatureCollection",
        "crs": {"type": "name", "properties": {"name": out_crs.to_string()}},
        "features": [
            {
                "type": "Feature",
                "properties": {"length_m": length_m},
                "geometry": {"type": "LineString", "coordinates": coords},
            }
        ],
    }
    out_path.write_text(json.dumps(geojson, indent=2))


def _write_cost_surface_plot(elevation, slope_deg, slope_pct, acc_arr, path_rc, out_path):
    import matplotlib.pyplot as plt

    aspect_deg = compute_aspect(elevation, 1.0)  # cellsize doesn't affect aspect direction
    hillshade = _hillshade(slope_deg, aspect_deg)
    log_acc = np.log1p(np.clip(acc_arr, 0, None))
    channel_mask = log_acc < np.nanpercentile(log_acc, 90)
    channel_display = np.ma.masked_where(channel_mask, log_acc)

    plt.figure(figsize=(9, 10))
    plt.imshow(hillshade, cmap="gray")
    plt.imshow(slope_pct, cmap="YlOrBr", alpha=0.35)
    plt.imshow(channel_display, cmap="Blues", alpha=0.7)
    rows = [r for r, _ in path_rc]
    cols = [c for _, c in path_rc]
    plt.plot(cols, rows, color="red", linewidth=2, label="route")
    plt.scatter([cols[0]], [rows[0]], color="lime", zorder=5, label="start")
    plt.scatter([cols[-1]], [rows[-1]], color="black", zorder=5, label="end")
    plt.legend()
    plt.title("Hillshade + slope % + flow accumulation, with computed route")
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close()


def _write_profile_plot(elevation, slope_pct, path_rc, transform, out_path):
    import matplotlib.pyplot as plt

    xs, ys = [], []
    for row, col in path_rc:
        x, y = rasterio.transform.xy(transform, row, col)
        xs.append(x)
        ys.append(y)
    dist = np.concatenate([[0.0], np.cumsum(np.hypot(np.diff(xs), np.diff(ys)))])

    rows = [r for r, _ in path_rc]
    cols = [c for _, c in path_rc]
    elev_profile = elevation[rows, cols]
    slope_profile = slope_pct[rows, cols]

    fig, axes = plt.subplots(2, 1, figsize=(9, 6), sharex=True)
    axes[0].plot(dist, elev_profile, color="tab:brown")
    axes[0].set_ylabel("Elevation (m)")
    axes[0].set_title("Elevation and slope % along route")
    axes[1].plot(dist, slope_profile, color="tab:blue")
    axes[1].set_ylabel("Slope (%)")
    axes[1].set_xlabel("Distance along route (m)")
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def _write_report(out_path, mode, result, args):
    lines = [
        "# Drainage Least-Cost Path Report",
        "",
        f"- Mode: {mode}",
        f"- Path length: {result.length_m:.1f} m",
        f"- Total accumulated cost: {result.cost:.2f}",
        f"- Slope % along path: min {result.slope_min:.2f} / "
        f"mean {result.slope_mean:.2f} / max {result.slope_max:.2f}",
        f"- Significant channel crossings: {result.significant_channel_crossings}",
        f"- Total elevation drop (start - end): {result.elevation_drop_m:.1f} m",
        "",
        "## Parameters",
        "",
    ]
    for key, value in sorted(vars(args).items()):
        lines.append(f"- {key}: {value}")
    out_path.write_text("\n".join(lines) + "\n")


def main(argv=None):
    args = parse_args(argv)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    start_lon, start_lat = _parse_lonlat(args.start, "start")
    end_lon, end_lat = _parse_lonlat(args.end, "end")

    result = run_pipeline(
        args.dem,
        (start_lon, start_lat),
        (end_lon, end_lat),
        min_slope_pct=args.min_slope_pct,
        max_slope_pct=args.max_slope_pct,
        hard_max_slope_pct=args.hard_max_slope_pct,
        w_slope=args.w_slope,
        w_channel=args.w_channel,
        w_direction=args.w_direction,
        mode=args.mode,
    )

    _write_geojson(result.path_lonlat, result.length_m, result.original_crs, result.crs, args.output_dir / "path.geojson")
    _write_cost_surface_plot(
        result.elevation, result.slope_deg, result.slope_pct, result.acc_arr, result.path_rc,
        args.output_dir / "cost_surface.png",
    )
    _write_profile_plot(
        result.elevation, result.slope_pct, result.path_rc, result.transform, args.output_dir / "profile.png"
    )
    _write_report(args.output_dir / "report.md", args.mode, result, args)

    config = {k: (str(v) if isinstance(v, Path) else v) for k, v in vars(args).items()}
    (args.output_dir / "run_config.json").write_text(json.dumps(config, indent=2))

    print(f"Route: {len(result.path_rc)} cells, {result.length_m:.1f} m, cost {result.cost:.2f}")
    print(f"Outputs written to {args.output_dir}")


if __name__ == "__main__":
    try:
        main()
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
