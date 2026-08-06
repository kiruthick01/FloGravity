"use client";

import "cesium/Build/Cesium/Widgets/widgets.css";
import * as Cesium from "cesium";
import { useEffect, useRef, useState } from "react";
import type { CesiumGlobeProps } from "./types";

const ION_TOKEN = process.env.NEXT_PUBLIC_CESIUM_ION_TOKEN;

// Radians/second the globe drifts when the user isn't dragging it.
const IDLE_ROTATE_SPEED = 0.015;
// How long to wait after the user lets go before auto-rotate resumes.
const RESUME_ROTATE_DELAY_MS = 2500;
// Only auto-rotate in the zoomed-out hero view. Rotating around Earth's axis
// while the camera is close to the surface (e.g. after a search flyTo) sweeps
// wildly across the horizon instead of gently spinning - so stop well above
// where anyone would actually be picking route points.
const MIN_IDLE_ROTATE_HEIGHT_M = 5_000_000;

const START_COLOR = Cesium.Color.fromCssColorString("#7CFFB2");
const END_COLOR = Cesium.Color.fromCssColorString("#F2617A");
const PATH_COLOR = Cesium.Color.fromCssColorString("#F2C744");

export default function CesiumGlobe({
  searchQuery,
  searchNonce,
  onSearchResult,
  pickMode,
  onPick,
  startPoint,
  endPoint,
  pathCoordinates,
}: CesiumGlobeProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const viewerRef = useRef<Cesium.Viewer | null>(null);
  const geocoderRef = useRef<Cesium.IonGeocoderService | null>(null);
  const clickHandlerRef = useRef<Cesium.ScreenSpaceEventHandler | null>(null);
  const startEntityRef = useRef<Cesium.Entity | null>(null);
  const endEntityRef = useRef<Cesium.Entity | null>(null);
  const pathEntityRef = useRef<Cesium.Entity | null>(null);
  const isFlyingRef = useRef(false);
  const [status, setStatus] = useState<"loading" | "ready" | "error">(ION_TOKEN ? "loading" : "error");

  // Kept in refs so the click handler (registered once) always sees current values.
  const pickModeRef = useRef(pickMode);
  const onPickRef = useRef(onPick);
  useEffect(() => {
    pickModeRef.current = pickMode;
  }, [pickMode]);
  useEffect(() => {
    onPickRef.current = onPick;
  }, [onPick]);

  useEffect(() => {
    if (!ION_TOKEN) return;
    if (!containerRef.current || viewerRef.current) return;

    window.CESIUM_BASE_URL = "/cesium";
    Cesium.Ion.defaultAccessToken = ION_TOKEN;

    let cancelled = false;
    let rafId = 0;
    let isInteracting = false;
    let resumeTimer: ReturnType<typeof setTimeout> | undefined;

    async function init() {
      // requestVertexNormals triples terrain mesh memory to support per-vertex
      // lighting -- pointless here since enableLighting is off below, and this
      // combined with an uncapped-resolution 203vh canvas was crashing the
      // renderer/GPU process on real hardware (confirmed: Chrome's tab-crashed
      // page, not a caught JS error) once the actual JS-syntax bug that had
      // been silently preventing Cesium from ever initializing was fixed.
      const terrain = Cesium.Terrain.fromWorldTerrain();

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
      geocoderRef.current = new Cesium.IonGeocoderService({ scene: viewer.scene });

      // Cap the GPU framebuffer resolution instead of rendering at full device
      // pixel ratio. The hero globe's canvas is huge (203vh) purely for visual
      // bleed off-screen; at 2x devicePixelRatio (any Retina/HiDPI display)
      // that's a 4x larger framebuffer than necessary and was a large part of
      // what pushed this over the edge on integrated GPUs.
      viewer.resolutionScale = Math.min(window.devicePixelRatio, 1);

      // Sun-based day/night lighting looks realistic but leaves half the globe
      // permanently dark for a product UI where every location should read clearly.
      viewer.scene.globe.enableLighting = false;
      viewer.scene.globe.depthTestAgainstTerrain = true;
      if (viewer.scene.skyAtmosphere) {
        viewer.scene.skyAtmosphere.show = true;
      }

      viewer.camera.setView({
        destination: Cesium.Cartesian3.fromDegrees(12, 18, 22_000_000),
      });

      const handler = new Cesium.ScreenSpaceEventHandler(viewer.scene.canvas);
      handler.setInputAction((click: Cesium.ScreenSpaceEventHandler.PositionedEvent) => {
        if (!pickModeRef.current) return;
        const cartesian = viewer.camera.pickEllipsoid(click.position, viewer.scene.globe.ellipsoid);
        if (!cartesian) return;
        const cartographic = Cesium.Cartographic.fromCartesian(cartesian);
        onPickRef.current({
          lon: Cesium.Math.toDegrees(cartographic.longitude),
          lat: Cesium.Math.toDegrees(cartographic.latitude),
        });
      }, Cesium.ScreenSpaceEventType.LEFT_CLICK);
      clickHandlerRef.current = handler;

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

      // The globe canvas is a huge fixed rectangle (203vh) that mostly covers empty
      // space around the visible sphere, sitting over real scrollable page content.
      // Only let wheel zoom the globe when the cursor is actually over the planet;
      // everywhere else on the canvas, let the wheel event through to scroll the page.
      // Runs in the capture phase so it fires before Cesium's own wheel handler.
      const wheelGate = (event: WheelEvent) => {
        const rect = canvas.getBoundingClientRect();
        const x = event.clientX - rect.left;
        const y = event.clientY - rect.top;
        const overGlobe = viewer.camera.pickEllipsoid(
          new Cesium.Cartesian2(x, y),
          viewer.scene.globe.ellipsoid
        );
        if (!overGlobe) {
          event.stopImmediatePropagation();
        }
      };
      canvas.addEventListener("wheel", wheelGate, { capture: true });

      let lastTime = performance.now();
      const tick = () => {
        if (cancelled) return;
        const now = performance.now();
        const dt = (now - lastTime) / 1000;
        lastTime = now;
        const currentViewer = viewerRef.current;
        if (!isInteracting && !isFlyingRef.current && currentViewer && !currentViewer.isDestroyed()) {
          const height = currentViewer.camera.positionCartographic?.height ?? 0;
          if (height > MIN_IDLE_ROTATE_HEIGHT_M) {
            currentViewer.scene.camera.rotate(Cesium.Cartesian3.UNIT_Z, -IDLE_ROTATE_SPEED * dt);
          }
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
      clickHandlerRef.current?.destroy();
      if (viewerRef.current && !viewerRef.current.isDestroyed()) {
        viewerRef.current.destroy();
      }
      viewerRef.current = null;
    };
  }, []);

  // Search: geocode + fly to the first result.
  useEffect(() => {
    const viewer = viewerRef.current;
    const geocoder = geocoderRef.current;
    if (!searchQuery || !geocoder || !viewer || status !== "ready") return;

    let cancelled = false;
    geocoder
      .geocode(searchQuery)
      .then((results) => {
        if (cancelled) return;
        if (!results.length) {
          onSearchResult({ found: false });
          return;
        }
        isFlyingRef.current = true;
        viewer.camera.flyTo({
          destination: results[0].destination,
          duration: 2,
          complete: () => {
            isFlyingRef.current = false;
          },
          cancel: () => {
            isFlyingRef.current = false;
          },
        });
        onSearchResult({ found: true });
      })
      .catch(() => {
        if (!cancelled) onSearchResult({ found: false });
      });

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- fire only when a new search is submitted
  }, [searchNonce, status]);

  // Keep the start marker entity in sync with the start point prop.
  useEffect(() => {
    const viewer = viewerRef.current;
    if (!viewer || viewer.isDestroyed()) return;

    if (startEntityRef.current) {
      viewer.entities.remove(startEntityRef.current);
      startEntityRef.current = null;
    }
    if (startPoint) {
      startEntityRef.current = viewer.entities.add({
        position: Cesium.Cartesian3.fromDegrees(startPoint.lon, startPoint.lat),
        point: {
          pixelSize: 14,
          color: START_COLOR,
          outlineColor: Cesium.Color.BLACK,
          outlineWidth: 2,
          heightReference: Cesium.HeightReference.CLAMP_TO_GROUND,
        },
      });
    }
  }, [startPoint]);

  useEffect(() => {
    const viewer = viewerRef.current;
    if (!viewer || viewer.isDestroyed()) return;

    if (endEntityRef.current) {
      viewer.entities.remove(endEntityRef.current);
      endEntityRef.current = null;
    }
    if (endPoint) {
      endEntityRef.current = viewer.entities.add({
        position: Cesium.Cartesian3.fromDegrees(endPoint.lon, endPoint.lat),
        point: {
          pixelSize: 14,
          color: END_COLOR,
          outlineColor: Cesium.Color.BLACK,
          outlineWidth: 2,
          heightReference: Cesium.HeightReference.CLAMP_TO_GROUND,
        },
      });
    }
  }, [endPoint]);

  // Draw the computed route once the backend returns one.
  useEffect(() => {
    const viewer = viewerRef.current;
    if (!viewer || viewer.isDestroyed()) return;

    if (pathEntityRef.current) {
      viewer.entities.remove(pathEntityRef.current);
      pathEntityRef.current = null;
    }
    if (pathCoordinates && pathCoordinates.length >= 2) {
      const flat = pathCoordinates.flatMap(([lon, lat]) => [lon, lat]);
      pathEntityRef.current = viewer.entities.add({
        polyline: {
          positions: Cesium.Cartesian3.fromDegreesArray(flat),
          width: 4,
          material: PATH_COLOR,
          clampToGround: true,
        },
      });
    }
  }, [pathCoordinates]);

  if (status === "error") {
    return (
      <div className="flex h-full w-full items-center justify-center text-sm text-neutral-500">
        Globe unavailable — missing or invalid NEXT_PUBLIC_CESIUM_ION_TOKEN.
      </div>
    );
  }

  return <div ref={containerRef} className="h-full w-full [&_.cesium-credit-container]:opacity-40" />;
}
