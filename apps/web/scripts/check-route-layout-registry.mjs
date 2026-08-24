#!/usr/bin/env node

/**
 * Route layout registry contract & filesystem coverage check.
 *
 * Recursively scans `apps/web/app subdirectories`, normalizes route groups `(...)`
 * and dynamic parameters `[...]`, and verifies 100% dynamic route coverage against
 * `apps/web/lib/route-layout.registry.ts` with strict contract enforcement.
 */
import { readdirSync, readFileSync, statSync } from "node:fs";
import { dirname, join, relative, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const SCRIPT_DIR = dirname(fileURLToPath(import.meta.url));
const WEB_ROOT = resolve(SCRIPT_DIR, "..");
const REPO_ROOT = resolve(WEB_ROOT, "..", "..");
const APP_DIR = resolve(WEB_ROOT, "app");

const SPEC_PATH = resolve(REPO_ROOT, "CLARA_Care_All_Pages_UIUX_Master_Spec_v5.md");
const CONTRACT_PATH = resolve(WEB_ROOT, "lib/route-layout.contract.ts");
const REGISTRY_PATH = resolve(WEB_ROOT, "lib/route-layout.registry.ts");

const VALID_ACCESS = new Set([
  "public",
  "personal",
  "clinical",
  "research",
  "admin",
  "utility",
]);

const VALID_EXPERIENCES = new Set([
  "personal",
  "clinical",
  "research",
  "admin",
  "public",
  "utility",
]);

const VALID_SHELL_MODES = new Set([
  "PUBLIC_MARKETING",
  "PUBLIC_AUTH",
  "PUBLIC_LEGAL",
  "PUBLIC_SHARE",
  "EXPLORE",
  "FOCUS",
  "IMMERSIVE",
  "READ",
  "READ_COMPOSE",
  "DENSE",
  "ADMIN_COMMAND",
  "ROLE_ADAPTER",
  "UTILITY_FOCUS",
  "ALIAS_REDIRECT",
  "ALIAS_CONTEXT",
]);

const VALID_ROLES = new Set(["normal", "researcher", "doctor", "admin"]);

let errors = [];

function check(condition, message) {
  if (!condition) {
    errors.push(message);
  }
}

// 1. Validate contract file contains required RouteLayoutContract interface
const contractContent = readFileSync(CONTRACT_PATH, "utf8");
check(
  contractContent.includes("interface RouteLayoutContract") ||
    contractContent.includes("type RouteLayoutContract"),
  "route-layout.contract.ts must define RouteLayoutContract",
);

for (const prop of [
  "routeId",
  "path",
  "access",
  "roles",
  "canonicalExperience",
  "shellMode",
  "layoutArchetype",
]) {
  check(
    contractContent.includes(prop),
    `route-layout.contract.ts missing property '${prop}' in RouteLayoutContract definition`,
  );
}

// 2. Discover and normalize all page routes from filesystem (apps/web/app/**/page.tsx)
function scanPageRoutes(dir, baseDir = dir) {
  const entries = readdirSync(dir, { withFileTypes: true });
  const routes = [];
  for (const entry of entries) {
    const fullPath = join(dir, entry.name);
    if (entry.isDirectory()) {
      routes.push(...scanPageRoutes(fullPath, baseDir));
    } else if (entry.name === "page.tsx") {
      const rel = relative(baseDir, fullPath).replaceAll("\\", "/");
      const dirName = rel.endsWith("/page.tsx")
        ? rel.slice(0, -"/page.tsx".length)
        : rel === "page.tsx"
          ? ""
          : rel;
      // Strip route groups such as (consumer)
      const segments = dirName
        ? dirName.split("/").filter((s) => !/^\(.*\)$/.test(s))
        : [];
      const route = "/" + segments.join("/");
      routes.push(route);
    }
  }
  return routes;
}

const fsRoutes = scanPageRoutes(APP_DIR).sort();
const fsRouteSet = new Set(fsRoutes);

check(
  fsRoutes.length > 0,
  "Filesystem scan must discover at least 1 page.tsx route",
);
check(
  fsRoutes.length === fsRouteSet.size,
  `Discovered duplicate normalized route paths in filesystem (${fsRoutes.length} found, ${fsRouteSet.size} unique)`,
);

// 3. Load ROUTE_LAYOUT_REGISTRY dynamically
let registryModule;
try {
  registryModule = await import(pathToFileURL(REGISTRY_PATH).href);
} catch (e) {
  errors.push(`Failed to import route-layout.registry.ts: ${e.message}`);
}

const registryEntries = registryModule?.ROUTE_LAYOUT_REGISTRY ?? [];

check(
  Array.isArray(registryEntries),
  "export ROUTE_LAYOUT_REGISTRY must be an array",
);

// 4. Validate entries integrity & contract compliance
const seenRouteIds = new Set();
const seenPaths = new Set();
const regPathMap = new Map();

for (let i = 0; i < registryEntries.length; i++) {
  const entry = registryEntries[i];

  if (!entry) {
    check(false, `Registry entry #${i + 1} is undefined or null`);
    continue;
  }

  // RouteId
  check(
    typeof entry.routeId === "string" && entry.routeId.trim().length > 0,
    `Registry entry #${i + 1} missing valid routeId`,
  );
  check(!seenRouteIds.has(entry.routeId), `Duplicate routeId '${entry.routeId}'`);
  seenRouteIds.add(entry.routeId);

  // Path
  check(
    typeof entry.path === "string" && entry.path.trim().length > 0,
    `Registry entry #${i + 1} missing valid path`,
  );
  check(!seenPaths.has(entry.path), `Duplicate path '${entry.path}'`);
  seenPaths.add(entry.path);
  regPathMap.set(entry.path, entry);

  // Roles
  check(
    Array.isArray(entry.roles) && entry.roles.length > 0,
    `Route '${entry.path}' must have non-empty roles array`,
  );
  if (Array.isArray(entry.roles)) {
    for (const r of entry.roles) {
      check(VALID_ROLES.has(r), `Invalid role '${r}' on route '${entry.path}'`);
    }
  }

  // Valid enums
  check(
    VALID_ACCESS.has(entry.access),
    `Invalid access '${entry.access}' for route '${entry.path}'`,
  );
  check(
    VALID_EXPERIENCES.has(entry.canonicalExperience),
    `Invalid canonicalExperience '${entry.canonicalExperience}' for route '${entry.path}'`,
  );
  check(
    VALID_SHELL_MODES.has(entry.shellMode),
    `Invalid shellMode '${entry.shellMode}' for route '${entry.path}'`,
  );

  // TargetPath invariant for aliases
  if (entry.shellMode === "ALIAS_REDIRECT" || entry.shellMode === "ALIAS_CONTEXT") {
    check(
      typeof entry.targetPath === "string" && entry.targetPath.length > 0,
      `Alias route '${entry.path}' (${entry.shellMode}) must define targetPath`,
    );
  }
}

// 5. Compare filesystem routes against registry (assert 100% dynamic coverage)
const missingInRegistry = fsRoutes.filter((r) => !regPathMap.has(r));
const extraInRegistry = registryEntries
  .map((e) => e.path)
  .filter((p) => !fsRouteSet.has(p));

if (missingInRegistry.length > 0) {
  check(
    false,
    `Missing ${missingInRegistry.length} filesystem route(s) in ROUTE_LAYOUT_REGISTRY:\n    ${missingInRegistry.join("\n    ")}`,
  );
}

if (extraInRegistry.length > 0) {
  check(
    false,
    `Registry contains ${extraInRegistry.length} extra route(s) not present in filesystem:\n    ${extraInRegistry.join("\n    ")}`,
  );
}

check(
  registryEntries.length === fsRoutes.length,
  `Route count mismatch: filesystem has ${fsRoutes.length} routes, registry has ${registryEntries.length} routes`,
);

// 6. Cross-check Spec v5 Section 5 (if spec exists) to guarantee spec alignment
try {
  const specContent = readFileSync(SPEC_PATH, "utf8");
  const section5Match = specContent.match(
    /## 5\. 79-route layout matrix[\s\S]*?(?=\n## 6\.|\n---\n## 6\.|\n#[^#]|$)/,
  );
  if (section5Match) {
    const rowRegex =
      /\|\s*(\d+)\s*\|\s*`([^`]+)`\s*\|\s*([^|]+?)\s*\|\s*`([^`]+)`\s*\|\s*([^|]+?)\s*\|/g;
    for (const match of section5Match[0].matchAll(rowRegex)) {
      const specPath = match[2].trim();
      const specShellMode = match[4].trim();
      const specLayoutArchetype = match[5].trim();

      const registered = regPathMap.get(specPath);
      if (!registered) {
        check(false, `Spec v5 route '${specPath}' missing from registry`);
      } else {
        check(
          registered.shellMode === specShellMode,
          `Route '${specPath}' shellMode mismatch with Spec v5: registry='${registered.shellMode}', spec='${specShellMode}'`,
        );
        check(
          registered.layoutArchetype === specLayoutArchetype,
          `Route '${specPath}' layoutArchetype mismatch with Spec v5: registry='${registered.layoutArchetype}', spec='${specLayoutArchetype}'`,
        );
      }
    }
  }
} catch {
  // Spec file optional
}

if (errors.length > 0) {
  console.error(`Route layout registry validation failed with ${errors.length} error(s):`);
  for (const err of errors) {
    console.error(`  - ${err}`);
  }
  process.exit(1);
}

console.log(
  `[OK] Route layout registry verified: 100% dynamic coverage (${registryEntries.length}/${fsRoutes.length} routes registered and conformant).`,
);
