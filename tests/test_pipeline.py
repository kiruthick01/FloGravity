"""Phase 7: unit tests + one integration test against the sample DEM."""

import re
from pathlib import Path

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin

from drainage_lcp import cli
from drainage_lcp.cost_surface import route_isotropic
from drainage_lcp.dem_io import load_dem
from drainage_lcp.terrain import compute_aspect, compute_slope

SAMPLE_DEM = Path(__file__).resolve().parent.parent / "sample_data" / "dem.tif"


def _write_synthetic_dem(path, crs, transform, nodata=-9999.0):
    shape = (10, 10)
    data = np.arange(100, dtype=np.float32).reshape(shape)
    data[0, 0] = nodata
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=shape[0],
        width=shape[1],
        count=1,
        dtype=data.dtype,
        crs=crs,
        transform=transform,
        nodata=nodata,
    ) as dst:
        dst.write(data, 1)


def test_load_dem_reprojects_geographic_crs(tmp_path):
    dem_path = tmp_path / "geographic.tif"
    transform = from_origin(-97.4, 32.7, 0.001, 0.001)
    _write_synthetic_dem(dem_path, "EPSG:4326", transform)

    elevation, out_transform, crs, nodata_mask, pixel_size_m = load_dem(dem_path)

    assert not crs.is_geographic
    assert pixel_size_m > 0
    assert nodata_mask.sum() >= 1
    assert elevation.shape == nodata_mask.shape


def test_load_dem_nodata_mask_exact_when_already_projected(tmp_path):
    dem_path = tmp_path / "projected.tif"
    transform = from_origin(500000, 3600000, 30, 30)
    _write_synthetic_dem(dem_path, "EPSG:32614", transform)

    elevation, out_transform, crs, nodata_mask, pixel_size_m = load_dem(dem_path)

    assert crs.to_epsg() == 32614
    assert pixel_size_m == pytest.approx(30.0)
    assert nodata_mask.sum() == 1
    assert nodata_mask[0, 0]


def test_compute_slope_on_tilted_plane_matches_expected_constant():
    cellsize_m = 10.0
    rows, cols = 20, 20
    rise_per_cell = 2.0
    elevation = np.fromfunction(lambda r, c: c * rise_per_cell, (rows, cols))

    slope_deg, slope_pct = compute_slope(elevation, cellsize_m)
    expected_pct = 100.0 * (rise_per_cell / cellsize_m)

    np.testing.assert_allclose(slope_pct, expected_pct, rtol=1e-6)

    aspect_deg = compute_aspect(elevation, cellsize_m)
    np.testing.assert_allclose(aspect_deg, 270.0, atol=1e-6)


def test_route_isotropic_returns_connected_path_on_trivial_grid():
    cost = np.ones((5, 5), dtype=np.float64)
    path, path_cost = route_isotropic(cost, (0, 0), (4, 4))

    assert tuple(path[0]) == (0, 0)
    assert tuple(path[-1]) == (4, 4)
    for (r0, c0), (r1, c1) in zip(path[:-1], path[1:]):
        assert max(abs(int(r1) - int(r0)), abs(int(c1) - int(c0))) == 1
    assert path_cost > 0


def test_cli_rejects_out_of_bounds_start(tmp_path):
    with pytest.raises(ValueError, match="outside the DEM extent"):
        cli.main(
            [
                "--dem",
                str(SAMPLE_DEM),
                "--start",
                "-50.0,10.0",
                "--end",
                "-97.25,32.75",
                "--output-dir",
                str(tmp_path / "out"),
            ]
        )


def test_cli_full_run_on_sample_dem_produces_sane_outputs(tmp_path):
    out_dir = tmp_path / "run"
    cli.main(
        [
            "--dem",
            str(SAMPLE_DEM),
            "--start",
            "-97.35,32.60",
            "--end",
            "-97.25,32.75",
            "--mode",
            "anisotropic",
            "--output-dir",
            str(out_dir),
        ]
    )

    for name in ("path.geojson", "cost_surface.png", "profile.png", "report.md", "run_config.json"):
        assert (out_dir / name).exists(), f"missing output: {name}"

    report_text = (out_dir / "report.md").read_text()
    assert "nan" not in report_text.lower()

    length_match = re.search(r"Path length: ([\d.]+) m", report_text)
    assert length_match and float(length_match.group(1)) > 0

    slope_match = re.search(
        r"min (-?[\d.]+) / mean (-?[\d.]+) / max (-?[\d.]+)", report_text
    )
    assert slope_match
    slope_min, slope_mean, slope_max = (float(v) for v in slope_match.groups())
    assert 0 <= slope_min <= slope_mean <= slope_max < 100
