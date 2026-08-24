#!/usr/bin/env node

/**
 * Route layout registry contract check.
 *
 * Verifies that `apps/web/lib/route-layout.registry.ts` exactly defines and matches
 * all 79 routes from Section 5 of `CLARA_Care_All_Pages_UIUX_Master_Spec_v5.md`,
 * adheres to the `RouteLayoutContract` interface, and enforces alias invariants.
 */
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const SCRIPT_DIR = dirname(fileURLToPath(import.meta.url));
const WEB_ROOT = resolve(SCRIPT_DIR, "..");
const REPO_ROOT = resolve(WEB_ROOT, "..", "..");

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

const specContent = readFileSync(SPEC_PATH, "utf8");
const contractContent = readFileSync(CONTRACT_PATH, "utf8");

let errors = [];

function check(condition, message) {
  if (!condition) {
    errors.push(message);
  }
}

// 1. Validate contract file contains required RouteLayoutContract interface
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

// 2. Parse Section 5 of Spec v5
const section5Match = specContent.match(/## 5\. 79-route layout matrix[\s\S]*?(?=\n## 6\.|\n---\n## 6\.|\n#[^#]|$)/);
check(Boolean(section5Match), "Could not find Section 5 in CLARA_Care_All_Pages_UIUX_Master_Spec_v5.md");

const specRoutes = [];
if (section5Match) {
  const rowRegex = /\|\s*(\d+)\s*\|\s*`([^`]+)`\s*\|\s*([^|]+?)\s*\|\s*`([^`]+)`\s*\|\s*([^|]+?)\s*\|/g;
  for (const match of section5Match[0].matchAll(rowRegex)) {
    specRoutes.push({
      num: parseInt(match[1], 10),
      path: match[2].trim(),
      purpose: match[3].trim(),
      shellMode: match[4].trim(),
      layoutArchetype: match[5].trim(),
    });
  }
}

check(
  specRoutes.length === 79,
  `Spec v5 Section 5 must contain exactly 79 routes, found ${specRoutes.length}`,
);

// 3. Load ROUTE_LAYOUT_REGISTRY
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

check(
  registryEntries.length === 79,
  `ROUTE_LAYOUT_REGISTRY must contain exactly 79 entries, found ${registryEntries.length}`,
);

// 4. Validate entries integrity
const seenRouteIds = new Set();
const seenPaths = new Set();

for (let i = 0; i < Math.max(registryEntries.length, specRoutes.length); i++) {
  const entry = registryEntries[i];
  const spec = specRoutes[i];

  if (!entry) {
    check(false, `Missing registry entry for route #${i + 1} (${spec?.path})`);
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

  // Exact 1:1 match with Spec v5 Section 5
  if (spec) {
    check(
      entry.path === spec.path,
      `Route #${i + 1} path mismatch: registry='${entry.path}', spec='${spec.path}'`,
    );
    check(
      entry.shellMode === spec.shellMode,
      `Route #${i + 1} (${entry.path}) shellMode mismatch: registry='${entry.shellMode}', spec='${spec.shellMode}'`,
    );
    check(
      entry.layoutArchetype === spec.layoutArchetype,
      `Route #${i + 1} (${entry.path}) layoutArchetype mismatch: registry='${entry.layoutArchetype}', spec='${spec.layoutArchetype}'`,
    );
  }
}

if (errors.length > 0) {
  console.error(`Route layout registry validation failed with ${errors.length} error(s):`);
  for (const err of errors) {
    console.error(`  - ${err}`);
  }
  process.exit(1);
}

console.log(
  `[OK] Route layout registry verified: 79/79 routes match CLARA_Care_All_Pages_UIUX_Master_Spec_v5.md Section 5 exactly.`,
);
