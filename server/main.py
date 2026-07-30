"""FastAPI backend: fetch a DEM for wherever the user picked on the globe, run
the drainage_lcp pipeline against it, return the route as JSON.
"""

import os
import tempfile

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from drainage_lcp.pipeline import run_pipeline
from server.opentopography import compute_padded_bbox, fetch_dem_bytes

app = FastAPI(title="drainage_lcp API")

_default_origins = "http://localhost:3000"
allowed_origins = [o.strip() for o in os.environ.get("CORS_ORIGINS", _default_origins).split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)


class LonLat(BaseModel):
    lon: float = Field(ge=-180, le=180)
    lat: float = Field(ge=-90, le=90)


class RouteRequest(BaseModel):
    start: LonLat
    end: LonLat
    min_slope_pct: float = 0.5
    max_slope_pct: float = 15.0
    hard_max_slope_pct: float = 45.0
    w_slope: float = 0.5
    w_channel: float = 0.3
    w_direction: float = 0.2
    mode: str = "anisotropic"


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/route")
def compute_route(req: RouteRequest):
    if req.mode not in ("isotropic", "anisotropic"):
        raise HTTPException(400, "mode must be 'isotropic' or 'anisotropic'")

    start = (req.start.lon, req.start.lat)
    end = (req.end.lon, req.end.lat)

    try:
        bbox = compute_padded_bbox(start, end)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

    try:
        dem_bytes = fetch_dem_bytes(bbox)
    except RuntimeError as exc:
        raise HTTPException(502, f"Failed to fetch elevation data: {exc}") from exc

    with tempfile.NamedTemporaryFile(suffix=".tif", delete=False) as f:
        f.write(dem_bytes)
        dem_path = f.name

    try:
        result = run_pipeline(
            dem_path,
            start,
            end,
            min_slope_pct=req.min_slope_pct,
            max_slope_pct=req.max_slope_pct,
            hard_max_slope_pct=req.hard_max_slope_pct,
            w_slope=req.w_slope,
            w_channel=req.w_channel,
            w_direction=req.w_direction,
            mode=req.mode,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    finally:
        os.unlink(dem_path)

    return {
        "path": result.path_lonlat,
        "length_m": result.length_m,
        "cost": result.cost,
        "slope_pct": {
            "min": result.slope_min,
            "mean": result.slope_mean,
            "max": result.slope_max,
        },
        "significant_channel_crossings": result.significant_channel_crossings,
        "elevation_drop_m": result.elevation_drop_m,
    }
