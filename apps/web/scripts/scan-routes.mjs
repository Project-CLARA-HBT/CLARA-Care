#!/usr/bin/env node

/**
 * Dynamic route scanner for Next.js App Router in CLARA-Care.
 * Recursively discovers all `page.tsx` files under `apps/web/app`,
 * strips route groups e.g. `(consumer)`, handles dynamic segments e.g. `[token]`,
 * and yields normalized canonical route paths.
 */
import { readdirSync } from "node:fs";
import { dirname, join, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const SCRIPT_DIR = dirname(fileURLToPath(import.meta.url));
export const DEFAULT_APP_DIR = resolve(SCRIPT_DIR, "../app");

/**
 * Normalizes relative file path from Next.js app directory to route path.
 * Strips route groups e.g. (consumer), (marketing)
 * Handles root page.tsx -> "/"
 *
 * @param {string} relFilePath - Relative path from app directory (e.g. "(consumer)/home/page.tsx")
 * @returns {string} Normalized route path (e.g. "/home")
 */
export function normalizeRoutePath(relFilePath) {
  const normalized = relFilePath.replaceAll("\\", "/");
  const dirName = normalized.endsWith("/page.tsx")
    ? normalized.slice(0, -"/page.tsx".length)
    : normalized === "page.tsx"
      ? ""
      : normalized;

  const segments = dirName
    ? dirName.split("/").filter((segment) => !/^\(.*\)$/.test(segment))
    : [];

  return "/" + segments.join("/");
}

/**
 * Recursively scans directory for Next.js page.tsx files and returns normalized route paths.
 *
 * @param {string} [dir=DEFAULT_APP_DIR] - Directory to scan
 * @param {string} [baseDir=dir] - Base app root directory for relative path computation
 * @returns {string[]} Sorted array of unique normalized route paths
 */
export function scanPageRoutes(dir = DEFAULT_APP_DIR, baseDir = dir) {
  const entries = readdirSync(dir, { withFileTypes: true });
  const routes = [];

  for (const entry of entries) {
    const fullPath = join(dir, entry.name);
    if (entry.isDirectory()) {
      routes.push(...scanPageRoutes(fullPath, baseDir));
    } else if (entry.name === "page.tsx") {
      const rel = relative(baseDir, fullPath);
      routes.push(normalizeRoutePath(rel));
    }
  }

  return [...new Set(routes)].sort();
}

// CLI entry point
if (
  process.argv[1] &&
  (fileURLToPath(import.meta.url) === resolve(process.argv[1]) ||
    process.argv[1].endsWith("scan-routes.mjs"))
) {
  const jsonOutput = process.argv.includes("--json");
  const routes = scanPageRoutes();

  if (jsonOutput) {
    console.log(JSON.stringify(routes, null, 2));
  } else {
    console.log(`Discovered ${routes.length} Next.js page route(s):`);
    for (const route of routes) {
      console.log(`  ${route}`);
    }
  }
}
