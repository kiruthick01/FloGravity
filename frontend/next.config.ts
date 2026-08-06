import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  webpack: (config) => {
    // @spz-loader/core (a transitive dependency of cesium@1.143's Gaussian
    // Splat 3D Tiles support, which this app never uses) ships Emscripten
    // glue code that embeds its .wasm binary as a string. Something about
    // how that string is emitted breaks strict-mode parsing once webpack
    // bundles it: "SyntaxError: Octal escape sequences are not allowed in
    // template strings" -- confirmed by fetching the exact deployed chunk
    // and finding raw near-binary bytes inside a file that otherwise starts
    // as valid JS, right where this package's glue code is inlined. Because
    // `import * as Cesium from "cesium"` is a namespace import, webpack
    // can't prove GaussianSplat-related exports (and this dependency) are
    // unused, so it bundles the broken code regardless. Since the corrupted
    // chunk isn't just a parse error but crashes the tab outright when a
    // Worker actually tries to instantiate it, this can't be worked around
    // client-side -- aliasing the whole package to false (webpack's
    // canonical "exclude this module" mechanism) removes it from the
    // bundle entirely.
    config.resolve.alias = {
      ...config.resolve.alias,
      "@spz-loader/core": false,
    };
    return config;
  },
};

export default nextConfig;
