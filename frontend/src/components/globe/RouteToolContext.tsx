"use client";

import { createContext, useCallback, useContext, useState } from "react";
import type { LonLat, RouteParams, RouteResult } from "./types";
import { DEFAULT_ROUTE_PARAMS } from "./types";

export type PickMode = "start" | "end" | null;
export type RunState =
  | { phase: "idle" }
  | { phase: "loading" }
  | { phase: "error"; message: string }
  | { phase: "done"; result: RouteResult };

interface RouteToolState {
  searchQuery: string | null;
  searchNonce: number;
  searchNotFound: boolean;
  handleSearchSubmit: (query: string) => void;
  handleSearchResult: (result: { found: boolean }) => void;

  pickMode: PickMode;
  setPickMode: (mode: PickMode) => void;
  startPoint: LonLat | null;
  endPoint: LonLat | null;
  handlePick: (point: LonLat) => void;

  params: RouteParams;
  setParams: (params: RouteParams) => void;
  runState: RunState;
  handleRun: () => void;
}

const RouteToolCtx = createContext<RouteToolState | null>(null);

// Shared between GlobeBackground (the fixed, viewport-filling Cesium canvas) and
// RoutePanel (a normal-flow block placed wherever the page layout wants it) --
// they live in completely different parts of the DOM, so plain prop drilling
// from one shared parent isn't an option.
export function RouteToolProvider({ children }: { children: React.ReactNode }) {
  const [searchQuery, setSearchQuery] = useState<string | null>(null);
  const [searchNonce, setSearchNonce] = useState(0);
  const [searchNotFound, setSearchNotFound] = useState(false);

  const [pickMode, setPickMode] = useState<PickMode>(null);
  const [startPoint, setStartPoint] = useState<LonLat | null>(null);
  const [endPoint, setEndPoint] = useState<LonLat | null>(null);

  const [params, setParams] = useState<RouteParams>(DEFAULT_ROUTE_PARAMS);
  const [runState, setRunState] = useState<RunState>({ phase: "idle" });

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
        message: err instanceof Error ? err.message : "Couldn't reach the routing backend.",
      });
    }
  }, [startPoint, endPoint, params]);

  const value: RouteToolState = {
    searchQuery,
    searchNonce,
    searchNotFound,
    handleSearchSubmit,
    handleSearchResult,
    pickMode,
    setPickMode,
    startPoint,
    endPoint,
    handlePick,
    params,
    setParams,
    runState,
    handleRun,
  };

  return <RouteToolCtx.Provider value={value}>{children}</RouteToolCtx.Provider>;
}

export function useRouteTool() {
  const ctx = useContext(RouteToolCtx);
  if (!ctx) throw new Error("useRouteTool must be used within a RouteToolProvider");
  return ctx;
}
