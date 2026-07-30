// Cesium ships its Workers/Widgets/Assets/ThirdParty as static files that must be
// served as-is (not bundled) - copy them into public/ so Next.js serves them at /cesium/*
// regardless of whether webpack or Turbopack is doing the bundling.
import { cpSync, existsSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const src = join(__dirname, "..", "node_modules", "cesium", "Build", "Cesium");
const dest = join(__dirname, "..", "public", "cesium");

if (!existsSync(src)) {
  console.error(`[copy-cesium-assets] source not found: ${src}`);
  process.exit(1);
}

mkdirSync(dest, { recursive: true });
cpSync(src, dest, { recursive: true });
console.log(`[copy-cesium-assets] copied ${src} -> ${dest}`);
