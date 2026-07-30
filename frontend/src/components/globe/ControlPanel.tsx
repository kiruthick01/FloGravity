"use client";

import { useState } from "react";
import type { LonLat, RouteParams, RouteResult } from "./types";

type RunState =
  | { phase: "idle" }
  | { phase: "loading" }
  | { phase: "error"; message: string }
  | { phase: "done"; result: RouteResult };

interface ControlPanelProps {
  onSearchSubmit: (query: string) => void;
  searchNotFound: boolean;
  pickMode: "start" | "end" | null;
  onSetPickMode: (mode: "start" | "end" | null) => void;
  startPoint: LonLat | null;
  endPoint: LonLat | null;
  params: RouteParams;
  onParamsChange: (params: RouteParams) => void;
  runState: RunState;
  onRun: () => void;
}

function formatLonLat(p: LonLat) {
  return `${p.lat.toFixed(3)}°, ${p.lon.toFixed(3)}°`;
}

function NumberField({
  label,
  value,
  onChange,
  step = 0.1,
  min,
  max,
}: {
  label: string;
  value: number;
  onChange: (value: number) => void;
  step?: number;
  min?: number;
  max?: number;
}) {
  return (
    <label className="flex items-center justify-between gap-3 text-xs">
      <span className="text-muted">{label}</span>
      <input
        type="number"
        value={value}
        step={step}
        min={min}
        max={max}
        onChange={(e) => onChange(Number(e.target.value))}
        className="w-20 rounded-md border border-white/10 bg-white/5 px-2 py-1 text-right text-foreground outline-none focus:border-white/30"
      />
    </label>
  );
}

export default function ControlPanel({
  onSearchSubmit,
  searchNotFound,
  pickMode,
  onSetPickMode,
  startPoint,
  endPoint,
  params,
  onParamsChange,
  runState,
  onRun,
}: ControlPanelProps) {
  const [searchValue, setSearchValue] = useState("");
  const bothPointsSet = Boolean(startPoint && endPoint);

  return (
    <div
      id="route"
      className="pointer-events-auto fixed bottom-6 right-6 z-20 w-[min(90vw,380px)] space-y-4 rounded-2xl border border-white/10 bg-black/50 p-5 text-sm backdrop-blur-md"
    >
      <div>
        <p className="mb-2 text-xs uppercase tracking-[0.15em] text-muted">Search a place</p>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            onSearchSubmit(searchValue);
          }}
          className="flex gap-2"
        >
          <input
            type="text"
            value={searchValue}
            onChange={(e) => setSearchValue(e.target.value)}
            placeholder="e.g. Fort Worth, Texas"
            className="min-w-0 flex-1 rounded-md border border-white/10 bg-white/5 px-3 py-2 text-sm outline-none placeholder:text-muted focus:border-white/30"
          />
          <button
            type="submit"
            className="shrink-0 rounded-md bg-white/10 px-3 py-2 text-sm transition-colors hover:bg-white/20"
          >
            Go
          </button>
        </form>
        {searchNotFound && (
          <p className="mt-1 text-xs text-red-400">No results found — try a different search.</p>
        )}
      </div>

      <div className="space-y-2 border-t border-white/10 pt-4">
        <p className="text-xs uppercase tracking-[0.15em] text-muted">Route points</p>

        <button
          type="button"
          onClick={() => onSetPickMode(pickMode === "start" ? null : "start")}
          className={`flex w-full items-center justify-between rounded-md border px-3 py-2 text-left text-xs transition-colors ${
            pickMode === "start"
              ? "border-[#7CFFB2]/60 bg-[#7CFFB2]/10"
              : "border-white/10 bg-white/5 hover:bg-white/10"
          }`}
        >
          <span className="flex items-center gap-2">
            <span className="h-2 w-2 rounded-full bg-[#7CFFB2]" />
            Start
          </span>
          <span className="text-muted">
            {pickMode === "start" ? "Click the globe…" : startPoint ? formatLonLat(startPoint) : "Pick on globe"}
          </span>
        </button>

        <button
          type="button"
          onClick={() => onSetPickMode(pickMode === "end" ? null : "end")}
          className={`flex w-full items-center justify-between rounded-md border px-3 py-2 text-left text-xs transition-colors ${
            pickMode === "end"
              ? "border-[#F2617A]/60 bg-[#F2617A]/10"
              : "border-white/10 bg-white/5 hover:bg-white/10"
          }`}
        >
          <span className="flex items-center gap-2">
            <span className="h-2 w-2 rounded-full bg-[#F2617A]" />
            End
          </span>
          <span className="text-muted">
            {pickMode === "end" ? "Click the globe…" : endPoint ? formatLonLat(endPoint) : "Pick on globe"}
          </span>
        </button>
      </div>

      <details className="border-t border-white/10 pt-4">
        <summary className="cursor-pointer text-xs uppercase tracking-[0.15em] text-muted">
          Parameters
        </summary>
        <div className="mt-3 space-y-2">
          <NumberField
            label="Min slope %"
            value={params.minSlopePct}
            onChange={(v) => onParamsChange({ ...params, minSlopePct: v })}
          />
          <NumberField
            label="Max slope %"
            value={params.maxSlopePct}
            onChange={(v) => onParamsChange({ ...params, maxSlopePct: v })}
          />
          <NumberField
            label="Hard max slope %"
            value={params.hardMaxSlopePct}
            onChange={(v) => onParamsChange({ ...params, hardMaxSlopePct: v })}
          />
          <NumberField
            label="Slope weight"
            value={params.wSlope}
            onChange={(v) => onParamsChange({ ...params, wSlope: v })}
          />
          <NumberField
            label="Channel weight"
            value={params.wChannel}
            onChange={(v) => onParamsChange({ ...params, wChannel: v })}
          />
          <NumberField
            label="Direction weight"
            value={params.wDirection}
            onChange={(v) => onParamsChange({ ...params, wDirection: v })}
          />
          <div className="flex items-center justify-between text-xs">
            <span className="text-muted">Mode</span>
            <div className="flex overflow-hidden rounded-md border border-white/10">
              {(["isotropic", "anisotropic"] as const).map((mode) => (
                <button
                  key={mode}
                  type="button"
                  onClick={() => onParamsChange({ ...params, mode })}
                  className={`px-2 py-1 ${
                    params.mode === mode ? "bg-white/20" : "bg-transparent hover:bg-white/10"
                  }`}
                >
                  {mode}
                </button>
              ))}
            </div>
          </div>
        </div>
      </details>

      <div className="border-t border-white/10 pt-4">
        <button
          type="button"
          disabled={!bothPointsSet || runState.phase === "loading"}
          onClick={onRun}
          className="w-full rounded-full bg-foreground px-4 py-2.5 text-sm font-medium text-background transition-opacity hover:opacity-85 disabled:cursor-not-allowed disabled:opacity-30"
        >
          {runState.phase === "loading" ? "Computing route…" : "Compute route"}
        </button>

        {runState.phase === "error" && (
          <p className="mt-2 text-xs text-red-400">{runState.message}</p>
        )}

        {runState.phase === "done" && (
          <dl className="mt-3 grid grid-cols-2 gap-x-3 gap-y-1 text-xs">
            <dt className="text-muted">Length</dt>
            <dd className="text-right">{(runState.result.lengthM / 1000).toFixed(2)} km</dd>
            <dt className="text-muted">Cost</dt>
            <dd className="text-right">{runState.result.cost.toFixed(1)}</dd>
            <dt className="text-muted">Slope % (min/mean/max)</dt>
            <dd className="text-right">
              {runState.result.slopePct.min.toFixed(1)} / {runState.result.slopePct.mean.toFixed(1)} /{" "}
              {runState.result.slopePct.max.toFixed(1)}
            </dd>
            <dt className="text-muted">Channel crossings</dt>
            <dd className="text-right">{runState.result.significantChannelCrossings}</dd>
            <dt className="text-muted">Elevation drop</dt>
            <dd className="text-right">{runState.result.elevationDropM.toFixed(1)} m</dd>
          </dl>
        )}
      </div>
    </div>
  );
}
