// Plain data types shared between GlobeCanvas (eagerly bundled) and CesiumGlobe
// (lazy-loaded, the only file allowed to import "cesium"). Keeping this file
// Cesium-free means GlobeCanvas can import it without dragging Cesium into the
// main bundle.

export type LonLat = { lon: number; lat: number };

export type RouteParams = {
  minSlopePct: number;
  maxSlopePct: number;
  hardMaxSlopePct: number;
  wSlope: number;
  wChannel: number;
  wDirection: number;
  mode: "isotropic" | "anisotropic";
};

export type RouteResult = {
  path: [number, number][]; // [lon, lat][]
  lengthM: number;
  cost: number;
  slopePct: { min: number; mean: number; max: number };
  significantChannelCrossings: number;
  elevationDropM: number;
};

export const DEFAULT_ROUTE_PARAMS: RouteParams = {
  minSlopePct: 0.5,
  maxSlopePct: 15,
  hardMaxSlopePct: 45,
  wSlope: 0.5,
  wChannel: 0.3,
  wDirection: 0.2,
  mode: "anisotropic",
};

export interface CesiumGlobeProps {
  searchQuery: string | null;
  searchNonce: number;
  onSearchResult: (result: { found: boolean }) => void;
  pickMode: "start" | "end" | null;
  onPick: (point: LonLat) => void;
  startPoint: LonLat | null;
  endPoint: LonLat | null;
  pathCoordinates: [number, number][] | null;
}
