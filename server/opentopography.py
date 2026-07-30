"""Fetch a DEM covering a bounding box from OpenTopography's Global DEM API."""

import os

import httpx

OPENTOPOGRAPHY_URL = "https://portal.opentopography.org/API/globaldem"
DEFAULT_DATASET = "SRTMGL1"  # 30m global coverage

# Padding around the start/end points, and a hard cap so one request can't
# pull an unreasonably large area (cost/latency/OpenTopography area limits).
PAD_FRACTION = 0.25
MIN_PAD_DEG = 0.05
MAX_SPAN_DEG = 1.5


def compute_padded_bbox(start_lonlat, end_lonlat):
    """Bounding box (west, south, east, north) covering both points with margin
    for the route to maneuver in. Raises ValueError if the two points are too
    far apart for this MVP's single-DEM-fetch approach.
    """
    lons = [start_lonlat[0], end_lonlat[0]]
    lats = [start_lonlat[1], end_lonlat[1]]
    west, east = min(lons), max(lons)
    south, north = min(lats), max(lats)

    lon_pad = max((east - west) * PAD_FRACTION, MIN_PAD_DEG)
    lat_pad = max((north - south) * PAD_FRACTION, MIN_PAD_DEG)
    west -= lon_pad
    east += lon_pad
    south -= lat_pad
    north += lat_pad

    if (east - west) > MAX_SPAN_DEG or (north - south) > MAX_SPAN_DEG:
        span = max(east - west, north - south)
        raise ValueError(
            f"start and end are too far apart ({span:.2f} deg span) -- "
            f"this MVP fetches a single DEM tile up to {MAX_SPAN_DEG} deg per side"
        )

    return west, south, east, north


def fetch_dem_bytes(bbox, dataset=DEFAULT_DATASET, api_key=None):
    """Fetch a GeoTIFF DEM for `bbox` = (west, south, east, north). Returns raw bytes."""
    api_key = api_key or os.environ.get("OPENTOPOGRAPHY_API_KEY")
    if not api_key:
        raise RuntimeError("OPENTOPOGRAPHY_API_KEY is not set")

    west, south, east, north = bbox
    params = {
        "demtype": dataset,
        "south": south,
        "north": north,
        "west": west,
        "east": east,
        "outputFormat": "GTiff",
        "API_Key": api_key,
    }

    response = httpx.get(OPENTOPOGRAPHY_URL, params=params, timeout=60.0)
    if response.status_code != 200:
        raise RuntimeError(f"OpenTopography request failed ({response.status_code}): {response.text[:300]}")

    content = response.content
    if len(content) < 1000:
        # A real GeoTIFF for even a small area is well over 1KB; anything smaller
        # is almost certainly an error message OpenTopography returned with a 200.
        raise RuntimeError(f"OpenTopography returned an unexpectedly small response: {content[:300]!r}")

    return content
