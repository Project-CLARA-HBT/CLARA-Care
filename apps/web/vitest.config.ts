import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

const rootDir = dirname(fileURLToPath(import.meta.url));

/**
 * Vitest harness for the CLARA_Web property/unit tests.
 *
 * - `jsdom` environment so React Testing Library component tests (AsyncSection)
 *   can render and query the DOM.
 * - The `@/*` path alias mirrors `tsconfig.json` so tests import modules the
 *   same way the app does.
 * - Single-run by default (the `test` script uses `vitest run`, not watch).
 */
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": rootDir,
    },
  },
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: [resolve(rootDir, "vitest.setup.ts")],
    include: ["**/*.test.ts", "**/*.test.tsx"],
    exclude: ["node_modules/**", ".next/**"],
  },
});
