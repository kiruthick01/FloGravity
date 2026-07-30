"use client";

import dynamic from "next/dynamic";
import { useCallback, useState, useSyncExternalStore } from "react";
import { createPortal } from "react-dom";
import ControlPanel from "./ControlPanel";
import type { LonLat, RouteParams, RouteResult } from "./types";
import { DEFAULT_ROUTE_PARAMS } from "./types";

// Cesium touches window/WebGL at import time, so it can only run in the browser.
const CesiumGlobe = dynamic(() => import("./CesiumGlobe"), {
  ssr: false,
  loading: () => (
    <div className="flex h-full w-full items-center justify-center text-sm text-neutral-500">
      Loading globe…
    </div>
  ),
});

// Portal needs document.body, which doesn't exist during SSR. useSyncExternalStore's
// server/client snapshot split gives us "has hydration finished" without an
// effect+setState (which would trigger an extra render pass).
const noopSubscribe = () => () => {};
const getClientSnapshot = () => true;
const getServerSnapshot = () => false;

type PickMode = "start" | "end" | null;
type RunState =
  | { phase: "idle" }
  | { phase: "loading" }
  | { phase: "error"; message: string }
  | { phase: "done"; result: RouteResult };

export default function GlobeCanvas() {
  const [searchQuery, setSearchQuery] = useState<string | null>(null);
  const [searchNonce, setSearchNonce] = useState(0);
  const [searchNotFound, setSearchNotFound] = useState(false);

  const [pickMode, setPickMode] = useState<PickMode>(null);
  const [startPoint, setStartPoint] = useState<LonLat | null>(null);
  const [endPoint, setEndPoint] = useState<LonLat | null>(null);

  const [params, setParams] = useState<RouteParams>(DEFAULT_ROUTE_PARAMS);
  const [runState, setRunState] = useState<RunState>({ phase: "idle" });

  // The globe's off-center hero placement uses a CSS transform, which makes
  // any `position: fixed` descendant relative to that transformed ancestor
  // instead of the viewport. Portal the panel straight to <body> to escape it,
  // once hydration has actually finished (document.body isn't available server-side).
  const mounted = useSyncExternalStore(noopSubscribe, getClientSnapshot, getServerSnapshot);

  const handleSearchSubmit = useCallback((query: string) => {
    if (!query.trim()) return;
    setSearchNotFound(false);
    setSearchQuery(query.trim());
    setSearchNonce((n) => n + 1);
  }, []);

  const handleSearchResult = useCallback(({ found }: { found: boolean }) => {
    setSearchNotFound(!found);
  }, []);

  const handlePick = useCallback(
    (point: LonLat) => {
      if (pickMode === "start") {
        setStartPoint(point);
      } else if (pickMode === "end") {
        setEndPoint(point);
      }
      setPickMode(null);
      setRunState({ phase: "idle" });
    },
    [pickMode]
  );

  const handleRun = useCallback(async () => {
    if (!startPoint || !endPoint) return;
    setRunState({ phase: "loading" });
    const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
    try {
      const res = await fetch(`${apiUrl}/route`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          start: startPoint,
          end: endPoint,
          min_slope_pct: params.minSlopePct,
          max_slope_pct: params.maxSlopePct,
          hard_max_slope_pct: params.hardMaxSlopePct,
          w_slope: params.wSlope,
          w_channel: params.wChannel,
          w_direction: params.wDirection,
          mode: params.mode,
        }),
      });
      if (!res.ok) {
        const text = await res.text().catch(() => "");
        throw new Error(text || `Request failed with status ${res.status}`);
      }
      const data = await res.json();
      const result: RouteResult = {
        path: data.path,
        lengthM: data.length_m,
        cost: data.cost,
        slopePct: data.slope_pct,
        significantChannelCrossings: data.significant_channel_crossings,
        elevationDropM: data.elevation_drop_m,
      };
      setRunState({ phase: "done", result });
    } catch (err) {
      setRunState({
        phase: "error",
        message:
          err instanceof Error
            ? err.message
            : "Couldn't reach the routing backend.",
      });
    }
  }, [startPoint, endPoint, params]);

  return (
    <>
      <div className="pointer-events-auto h-full w-full">
        <CesiumGlobe
          searchQuery={searchQuery}
          searchNonce={searchNonce}
          onSearchResult={handleSearchResult}
          pickMode={pickMode}
          onPick={handlePick}
          startPoint={startPoint}
          endPoint={endPoint}
          pathCoordinates={runState.phase === "done" ? runState.result.path : null}
        />
      </div>
      {mounted &&
        createPortal(
          <ControlPanel
            onSearchSubmit={handleSearchSubmit}
            searchNotFound={searchNotFound}
            pickMode={pickMode}
            onSetPickMode={setPickMode}
            startPoint={startPoint}
            endPoint={endPoint}
            params={params}
            onParamsChange={setParams}
            runState={runState}
            onRun={handleRun}
          />,
          document.body
        )}
    </>
  );
}
