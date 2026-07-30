"""Phase 5: anisotropic (directional) least-cost routing.

Upgrades the Phase 4 isotropic cost surface with a per-edge penalty for
crossing a flow channel perpendicular to its direction, so the route can
express "cheap to run alongside a channel, costly to cross it head-on."
"""

import heapq
import math
from pathlib import Path

import numpy as np

from drainage_lcp.cost_surface import IMPASSABLE_COST

# fdir codes from hydrology.DIRMAP (N, NE, E, SE, S, SW, W, NW) -> compass bearing.
FDIR_TO_BEARING = {64: 0.0, 128: 45.0, 1: 90.0, 2: 135.0, 4: 180.0, 8: 225.0, 16: 270.0, 32: 315.0}

# (row_delta, col_delta, travel_bearing_deg, step_distance_in_cells)
NEIGHBORS = [
    (-1, 0, 0.0, 1.0),
    (-1, 1, 45.0, math.sqrt(2)),
    (0, 1, 90.0, 1.0),
    (1, 1, 135.0, math.sqrt(2)),
    (1, 0, 180.0, 1.0),
    (1, -1, 225.0, math.sqrt(2)),
    (0, -1, 270.0, 1.0),
    (-1, -1, 315.0, math.sqrt(2)),
]


def _alignment(travel_bearing, flow_bearing):
    """1.0 when travel is parallel/anti-parallel to flow, 0.0 when perpendicular."""
    return abs(math.cos(math.radians(travel_bearing - flow_bearing)))


def route_anisotropic(total_cost, fdir, channel_penalty, start_rc, end_rc, w_direction=0.2):
    """Dijkstra over an 8-connected directed graph with a channel-crossing penalty.

    edge_cost(u, v) = total_cost[v] * direction_factor * step_distance. The
    step_distance term (1 or sqrt(2)) is not in the original formula but is
    necessary: without it, diagonal steps cover more ground per unit cost than
    orthogonal ones, and Dijkstra will zigzag diagonally to exploit that.

    Returns (path, total_cost_of_path); path is a list of (row, col) tuples.
    """
    nrows, ncols = total_cost.shape
    start = (int(start_rc[0]), int(start_rc[1]))
    end = (int(end_rc[0]), int(end_rc[1]))

    for label, rc in (("start", start), ("end", end)):
        if not (0 <= rc[0] < nrows and 0 <= rc[1] < ncols):
            raise ValueError(f"{label} point {rc} is outside the grid {total_cost.shape}")
        if total_cost[rc] >= IMPASSABLE_COST:
            raise ValueError(f"{label} point {rc} sits on an impassable (nodata/hard-max-slope) cell")

    dist = np.full((nrows, ncols), np.inf, dtype=np.float64)
    dist[start] = 0.0
    visited = np.zeros((nrows, ncols), dtype=bool)
    prev = {}

    heap = [(0.0, start)]
    while heap:
        d, u = heapq.heappop(heap)
        if visited[u]:
            continue
        visited[u] = True
        if u == end:
            break

        ur, uc = u
        for dr, dc, travel_bearing, step_dist in NEIGHBORS:
            vr, vc = ur + dr, uc + dc
            if not (0 <= vr < nrows and 0 <= vc < ncols):
                continue
            v = (vr, vc)
            if visited[v]:
                continue

            v_cost = total_cost[v]
            if v_cost >= IMPASSABLE_COST:
                continue

            flow_bearing = FDIR_TO_BEARING.get(int(fdir[v]))
            alignment = 1.0 if flow_bearing is None else _alignment(travel_bearing, flow_bearing)

            chan_pen = channel_penalty[v]
            chan_pen = 0.0 if np.isnan(chan_pen) else chan_pen
            direction_factor = 1.0 + w_direction * (1.0 - alignment) * chan_pen

            new_dist = d + v_cost * direction_factor * step_dist
            if new_dist < dist[v]:
                dist[v] = new_dist
                prev[v] = u
                heapq.heappush(heap, (new_dist, v))

    if not visited[end]:
        raise RuntimeError(f"No path found from {start} to {end}")

    path = [end]
    while path[-1] != start:
        path.append(prev[path[-1]])
    path.reverse()

    return path, dist[end]


if __name__ == "__main__":
    import matplotlib.pyplot as plt

    from drainage_lcp.cost_surface import compute_total_cost, route_isotropic
    from drainage_lcp.dem_io import load_dem
    from drainage_lcp.hydrology import compute_hydrology
    from drainage_lcp.terrain import compute_slope

    sample_path = Path(__file__).resolve().parent.parent / "sample_data" / "dem.tif"
    elevation, transform, crs, nodata_mask, pixel_size_m = load_dem(sample_path)
    slope_deg, slope_pct = compute_slope(elevation, pixel_size_m, nodata_mask)
    fdir_arr, acc_arr = compute_hydrology(elevation, transform, crs, nodata_mask)
    total_cost, channel_pen = compute_total_cost(slope_pct, acc_arr, nodata_mask)

    # Pixel indices straddling the DEM's largest channel (row 200, ~col 283 has
    # accumulation ~28000, by far the highest in that row) so the isotropic
    # path is forced into a near-perpendicular crossing -- the scenario Phase 5
    # is specifically meant to handle differently.
    start_rc = (200, 250)
    end_rc = (200, 320)
    # w_direction=0.2 (the CLI default) barely moves this particular path;
    # cranked up here purely to make the divergence obvious in this demo plot.
    w_direction_demo = 3.0

    iso_path, iso_cost = route_isotropic(total_cost, start_rc, end_rc)
    aniso_path, aniso_cost = route_anisotropic(
        total_cost, fdir_arr, channel_pen, start_rc, end_rc, w_direction=w_direction_demo
    )

    iso_set = set(iso_path)
    aniso_set = set(aniso_path)
    divergent_aniso = [rc for rc in aniso_path if rc not in iso_set]
    print(f"Isotropic path: {len(iso_path)} cells, cost {iso_cost:.1f}")
    print(f"Anisotropic path: {len(aniso_path)} cells, cost {aniso_cost:.1f}")
    print(f"Cells where anisotropic diverges from isotropic: {len(divergent_aniso)}")
    if divergent_aniso:
        rows = [rc[0] for rc in divergent_aniso]
        cols = [rc[1] for rc in divergent_aniso]
        print(f"Divergent stretch row range: {min(rows)}-{max(rows)}, col range: {min(cols)}-{max(cols)}")

    out_dir = Path(__file__).resolve().parent.parent / "outputs"
    out_dir.mkdir(exist_ok=True)
    plt.figure(figsize=(8, 9))
    plt.imshow(np.log1p(acc_arr), cmap="Blues")
    plt.colorbar(label="log1p(flow accumulation)")
    plt.plot([c for _, c in iso_path], [r for r, _ in iso_path], color="orange", linewidth=1.5, label="isotropic (Phase 4)")
    plt.plot([c for _, c in aniso_path], [r for r, _ in aniso_path], color="magenta", linewidth=1.5, linestyle="--", label="anisotropic (Phase 5)")
    plt.scatter(start_rc[1], start_rc[0], color="lime", zorder=5, label="start")
    plt.scatter(end_rc[1], end_rc[0], color="black", zorder=5, label="end")
    plt.legend()
    plt.title("Phase 5: anisotropic vs isotropic path over flow accumulation")
    plt.savefig(out_dir / "phase5_anisotropic_vs_isotropic_check.png", dpi=150)
    print(f"Saved check plot to {out_dir / 'phase5_anisotropic_vs_isotropic_check.png'}")
