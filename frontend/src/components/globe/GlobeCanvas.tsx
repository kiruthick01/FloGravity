"use client";

import dynamic from "next/dynamic";

// Cesium touches window/WebGL at import time, so it can only run in the browser.
const CesiumGlobe = dynamic(() => import("./CesiumGlobe"), {
  ssr: false,
  loading: () => (
    <div className="flex h-full w-full items-center justify-center text-sm text-neutral-500">
      Loading globe…
    </div>
  ),
});

export default function GlobeCanvas() {
  return <CesiumGlobe />;
}
