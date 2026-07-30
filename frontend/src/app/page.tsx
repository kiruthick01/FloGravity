import GlobeCanvas from "@/components/globe/GlobeCanvas";

export default function Home() {
  return (
    <main className="relative flex min-h-screen flex-col overflow-hidden">
      {/* Globe sits off-center, bleeding past the right/bottom edge of the viewport. */}
      <div className="absolute -right-[18vw] top-1/2 h-[135vh] w-[135vh] -translate-y-1/2">
        <GlobeCanvas />
      </div>

      {/* Vignette so headline stays legible over the globe on narrower viewports. */}
      <div className="pointer-events-none absolute inset-0 bg-gradient-to-r from-background via-background/70 to-transparent" />

      <nav className="pointer-events-none relative z-10 flex items-center justify-between px-6 py-6 sm:px-10 sm:py-8">
        <span className="font-display pointer-events-auto text-lg tracking-tight">drainage_lcp</span>
        <a
          href="https://github.com/kiruthick01/FloGravity"
          className="pointer-events-auto text-sm text-muted transition-colors hover:text-foreground"
        >
          Source
        </a>
      </nav>

      {/* pointer-events-none so the empty space to the right (over the globe) doesn't
          block clicks; individual interactive children opt back in. */}
      <div className="pointer-events-none relative z-10 flex flex-1 flex-col justify-center px-6 pb-24 sm:px-10">
        <p className="mb-4 text-sm uppercase tracking-[0.2em] text-muted">
          Hydraulically-constrained least-cost routing
        </p>
        <h1 className="font-display max-w-2xl text-5xl leading-[1.05] font-medium tracking-tight sm:text-6xl md:text-7xl">
          Pick two points on Earth.
          <br />
          Get the route gravity
          <br />
          would actually take.
        </h1>
        <p className="mt-6 max-w-md text-base text-muted sm:text-lg">
          Real terrain, real flow direction, real slope constraints — not just
          &ldquo;shortest path.&rdquo; Search a place, drop a start and end
          point, and compute the least-cost drainage alignment between them.
        </p>
        <div className="mt-10 flex items-center gap-4">
          <a
            href="#route"
            className="pointer-events-auto rounded-full bg-foreground px-6 py-3 text-sm font-medium text-background transition-opacity hover:opacity-85"
          >
            Plan a route
          </a>
          <a
            href="#how-it-works"
            className="pointer-events-auto text-sm text-muted transition-colors hover:text-foreground"
          >
            How it works
          </a>
        </div>
      </div>
    </main>
  );
}
