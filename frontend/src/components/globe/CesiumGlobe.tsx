"use client";

import "cesium/Build/Cesium/Widgets/widgets.css";
import * as Cesium from "cesium";
import { useEffect, useRef, useState } from "react";

const ION_TOKEN = process.env.NEXT_PUBLIC_CESIUM_ION_TOKEN;

// Radians/second the globe drifts when the user isn't dragging it.
const IDLE_ROTATE_SPEED = 0.015;
// How long to wait after the user lets go before auto-rotate resumes.
const RESUME_ROTATE_DELAY_MS = 2500;

export default function CesiumGlobe() {
  const containerRef = useRef<HTMLDivElement>(null);
  const viewerRef = useRef<Cesium.Viewer | null>(null);
  const [status, setStatus] = useState<"loading" | "ready" | "error">("loading");

  useEffect(() => {
    if (!ION_TOKEN) {
      setStatus("error");
      return;
    }
    if (!containerRef.current || viewerRef.current) return;

    window.CESIUM_BASE_URL = "/cesium";
    Cesium.Ion.defaultAccessToken = ION_TOKEN;

    let cancelled = false;
    let rafId = 0;
    let isInteracting = false;
    let resumeTimer: ReturnType<typeof setTimeout> | undefined;

    async function init() {
      const terrain = Cesium.Terrain.fromWorldTerrain({
        requestVertexNormals: true,
      });

      const viewer = new Cesium.Viewer(containerRef.current as HTMLDivElement, {
        terrain,
        animation: false,
        timeline: false,
        baseLayerPicker: false,
        geocoder: false,
        homeButton: false,
        sceneModePicker: false,
        navigationHelpButton: false,
        fullscreenButton: false,
        infoBox: false,
        selectionIndicator: false,
      });

      if (cancelled) {
        viewer.destroy();
        return;
      }
      viewerRef.current = viewer;

      viewer.scene.globe.enableLighting = true;
      viewer.scene.globe.depthTestAgainstTerrain = true;
      viewer.scene.skyAtmosphere.show = true;

      viewer.camera.setView({
        destination: Cesium.Cartesian3.fromDegrees(12, 18, 22_000_000),
      });

      const canvas = viewer.scene.canvas;
      const pause = () => {
        isInteracting = true;
        if (resumeTimer) clearTimeout(resumeTimer);
      };
      const resume = () => {
        if (resumeTimer) clearTimeout(resumeTimer);
        resumeTimer = setTimeout(() => {
          isInteracting = false;
        }, RESUME_ROTATE_DELAY_MS);
      };
      canvas.addEventListener("pointerdown", pause);
      canvas.addEventListener("pointerup", resume);
      canvas.addEventListener("wheel", pause, { passive: true });

      let lastTime = performance.now();
      const tick = () => {
        if (cancelled) return;
        const now = performance.now();
        const dt = (now - lastTime) / 1000;
        lastTime = now;
        if (!isInteracting && viewerRef.current && !viewerRef.current.isDestroyed()) {
          viewerRef.current.scene.camera.rotate(Cesium.Cartesian3.UNIT_Z, -IDLE_ROTATE_SPEED * dt);
        }
        rafId = requestAnimationFrame(tick);
      };
      rafId = requestAnimationFrame(tick);

      setStatus("ready");
    }

    init().catch(() => {
      if (!cancelled) setStatus("error");
    });

    return () => {
      cancelled = true;
      if (rafId) cancelAnimationFrame(rafId);
      if (resumeTimer) clearTimeout(resumeTimer);
      if (viewerRef.current && !viewerRef.current.isDestroyed()) {
        viewerRef.current.destroy();
      }
      viewerRef.current = null;
    };
  }, []);

  if (status === "error") {
    return (
      <div className="flex h-full w-full items-center justify-center text-sm text-neutral-500">
        Globe unavailable — missing or invalid NEXT_PUBLIC_CESIUM_ION_TOKEN.
      </div>
    );
  }

  return <div ref={containerRef} className="h-full w-full [&_.cesium-credit-container]:opacity-40" />;
}
