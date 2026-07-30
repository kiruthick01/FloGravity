"""DEM ingestion: load a GeoTIFF, reproject to a metric CRS, mask nodata."""

from pathlib import Path

import numpy as np
import rasterio
from rasterio.crs import CRS
from rasterio.warp import Resampling, calculate_default_transform, reproject


def _utm_crs_for_lonlat(lon: float, lat: float) -> CRS:
    zone = int((lon + 180) // 6) + 1
    epsg = (32600 if lat >= 0 else 32700) + zone
    return CRS.from_epsg(epsg)


def load_dem(path):
    """Load a DEM GeoTIFF, reprojecting to local UTM if the source CRS is geographic.

    Returns (elevation, transform, crs, nodata_mask, pixel_size_m).
    """
    with rasterio.open(path) as src:
        src_crs = src.crs
        src_nodata = src.nodata

        if src_crs is None:
            raise ValueError(f"DEM at {path} has no CRS defined")

        if src_crs.is_geographic:
            lon, lat = src.transform * (src.width / 2, src.height / 2)
            dst_crs = _utm_crs_for_lonlat(lon, lat)
            dst_transform, width, height = calculate_default_transform(
                src_crs, dst_crs, src.width, src.height, *src.bounds
            )

            fill_value = src_nodata if src_nodata is not None else np.nan
            elevation = np.full((height, width), fill_value, dtype=np.float32)
            reproject(
                source=rasterio.band(src, 1),
                destination=elevation,
                src_transform=src.transform,
                src_crs=src_crs,
                dst_transform=dst_transform,
                dst_crs=dst_crs,
                resampling=Resampling.bilinear,
                src_nodata=src_nodata,
                dst_nodata=fill_value,
            )
            transform = dst_transform
            crs = dst_crs
            nodata = fill_value
        else:
            elevation = src.read(1).astype(np.float32)
            transform = src.transform
            crs = src_crs
            nodata = src_nodata

    if nodata is not None and not np.isnan(nodata):
        nodata_mask = elevation == nodata
    else:
        nodata_mask = np.isnan(elevation)

    pixel_size_m = (abs(transform.a) + abs(transform.e)) / 2.0

    return elevation, transform, crs, nodata_mask, pixel_size_m


if __name__ == "__main__":
    sample_path = Path(__file__).resolve().parent.parent / "sample_data" / "dem.tif"
    elevation, transform, crs, nodata_mask, pixel_size_m = load_dem(sample_path)

    valid = elevation[~nodata_mask]
    print(f"CRS: {crs}")
    print(f"Pixel size: {pixel_size_m:.3f} m")
    print(f"Shape: {elevation.shape}")
    print(f"Elevation min/max: {valid.min():.1f} / {valid.max():.1f} m")
    print(f"Nodata cells: {int(nodata_mask.sum())} / {elevation.size}")
