"use client";

import dynamic from "next/dynamic";
import { useRouteTool } from "./RouteToolContext";

// Cesium touches window/WebGL at import time, so it can only run in the browser.
const CesiumGlobe = dynamic(() => import("./CesiumGlobe"), {
  ssr: false,
  loading: () => (
    <div className="flex h-full w-full items-center justify-center text-sm text-neutral-500">
      Loading globe…
    </div>
  ),
});

export default function GlobeBackground() {
  const { searchQuery, searchNonce, handleSearchResult, pickMode, handlePick, startPoint, endPoint, runState } =
    useRouteTool();

  return (
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
  );
}
