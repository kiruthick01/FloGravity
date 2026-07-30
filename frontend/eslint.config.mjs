import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  // Override default ignores of eslint-config-next.
  globalIgnores([
    // Default ignores of eslint-config-next:
    ".next/**",
    "out/**",
    "build/**",
    "next-env.d.ts",
    // This array replaces ESLint's own defaults (which include node_modules),
    // so it has to be listed explicitly or the whole dependency tree gets linted.
    "node_modules/**",
    "public/**",
  ]),
]);

export default eslintConfig;
