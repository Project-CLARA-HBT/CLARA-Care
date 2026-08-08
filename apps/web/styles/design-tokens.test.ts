import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

/**
 * Feature: product-polish-analytics — Task 8.5
 * Audit surfaces and replace hardcoded styles with design tokens.
 *
 * Validates: Requirements 5.1
 *
 * Requirement 5.1 asks for a consistent set of design tokens across the primary
 * surfaces. This regression guard scans the audited surface files and fails if a
 * hardcoded hex color literal is (re)introduced as a Tailwind arbitrary-value
 * utility (e.g. `text-[#1f2937]`, `bg-[#2563eb]`). Color values on these surfaces
 * must reference the shared design tokens (`--text-*`, `--surface-*`,
 * `--shell-border*`, `--brand-*`, `--radius-*`) via `var(--token)` instead.
 *
 * A tiny allowlist covers deliberate, non-tokenizable decoration (the dark
 * connection-map visualization panel on the admin knowledge-sources page, which
 * stays dark in both themes and has no matching surface token).
 */

const here = dirname(fileURLToPath(import.meta.url));
const appDir = resolve(here, "..", "app");

// Surfaces named by task 8.5: Chat, Research, SelfMed, CareGuard, Council,
// Scribe, Dashboard, and Admin.
const SURFACE_FILES = [
  "selfmed/add/page.tsx",
  "selfmed/page.tsx",
  "scribe/page.tsx",
  "council/page.tsx",
  "careguard/page.tsx",
  "research/source-hub/page.tsx",
  "admin/knowledge-sources/page.tsx"
];

const COUNCIL_FLOW_FILES = [
  "council/new/page.tsx",
  "council/new/intake/page.tsx",
  "council/new/specialists/page.tsx",
  "council/new/review/page.tsx",
  "council/result/page.tsx",
];

const PUBLIC_SURFACE_FILES = [
  resolve(here, "..", "components", "landing", "clara-kp3-landing.tsx"),
  resolve(here, "..", "components", "landing", "landing-faq-accordion.tsx"),
  resolve(appDir, "login/page.tsx"),
  resolve(appDir, "register/page.tsx"),
  resolve(appDir, "forgot-password/page.tsx"),
  resolve(appDir, "reset-password/page.tsx")
];

// Deliberate, non-tokenizable hardcoded colors that are exempt from the audit.
const ALLOWLIST = new Set<string>(["#001c38"]);

// Matches Tailwind arbitrary-value color utilities such as `text-[#1f2937]`,
// `bg-[#2563EB]`, `hover:border-[#93c5fd]`, `disabled:bg-[#dbeafe]`, etc.
const HARDCODED_HEX_UTILITY = /[a-z-]+-\[#([0-9a-fA-F]{3,8})\]/g;

function findHardcodedHex(source: string): string[] {
  const hits: string[] = [];
  for (const match of source.matchAll(HARDCODED_HEX_UTILITY)) {
    const hex = `#${match[1].toLowerCase()}`;
    if (!ALLOWLIST.has(hex)) {
      hits.push(match[0]);
    }
  }
  return hits;
}

describe("design tokens on primary surfaces (Task 8.5, Requirement 5.1)", () => {
  it("freezes the approved canonical default palette", () => {
    const globals = readFileSync(resolve(here, "globals.css"), "utf8");
    const root = globals.match(/:root\s*\{([\s\S]*?)\n\}/)?.[1] ?? "";
    expect(root).toContain("--bg-canvas: #101419;");
    expect(root).toContain("--surface-sidebar: #0b0e13;");
    expect(root).toContain("--surface-panel: #1d2025;");
    expect(root).toContain("--surface-muted: #272a30;");
    expect(root).toContain("--text-primary: #e1e2e9;");
    expect(root).toContain("--text-secondary: #c1c7d3;");
    expect(root).toContain("--shell-border: #414751;");
    expect(root).toContain("--shell-border-strong: #8b919d;");
  });

  it("freezes the approved semantic dark palette", () => {
    const globals = readFileSync(resolve(here, "globals.css"), "utf8");
    const dark =
      globals.match(
        /html\.dark,\s*html\[data-theme="dark"\]\s*\{([\s\S]*?)\n\}/,
      )?.[1] ?? "";
    expect(dark).toContain("--bg-canvas: #101419;");
    expect(dark).toContain("--surface-panel: #1d2025;");
    expect(dark).toContain("--surface-muted: #272a30;");
    expect(dark).toContain("--text-primary: #e1e2e9;");
    expect(dark).toContain("--text-secondary: #c1c7d3;");
    expect(dark).toContain("--shell-border: #414751;");
    expect(dark).toContain("--shell-border-strong: #8b919d;");
  });

  it.each(SURFACE_FILES)(
    "%s uses design tokens instead of hardcoded hex color utilities",
    (relativePath) => {
      const source = readFileSync(resolve(appDir, relativePath), "utf8");
      const offenders = findHardcodedHex(source);
      expect(offenders, `Hardcoded color utilities found in ${relativePath}`).toEqual([]);
    }
  );

  it("the audited surfaces reference shared design-token variables", () => {
    const combined = SURFACE_FILES.map((relativePath) =>
      readFileSync(resolve(appDir, relativePath), "utf8")
    ).join("\n");
    // At least the brand + text + surface + border token families are in use.
    expect(combined).toMatch(/var\(--brand-(500|600|700)\)/);
    expect(combined).toMatch(/var\(--text-(primary|secondary|muted|brand)\)/);
    expect(combined).toMatch(/var\(--surface-(muted|brand-soft)\)/);
    expect(combined).toMatch(/var\(--shell-border\)/);
  });

  it("keeps Source Hub status, chips and focus states on the CLARA palette", () => {
    const sourceHub = readFileSync(resolve(appDir, "research/source-hub/page.tsx"), "utf8");
    expect(sourceHub).toMatch(/var\(--surface-brand-soft\)/);
    expect(sourceHub).toMatch(/var\(--brand-primary\)/);
    expect(sourceHub).toMatch(/var\(--text-brand\)/);
    expect(sourceHub).not.toMatch(/(?:bg|text|border|ring)-blue-/);
  });

  it.each(COUNCIL_FLOW_FILES)(
    "%s keeps its card edge and action colors tokenized",
    (relativePath) => {
      const source = readFileSync(resolve(appDir, relativePath), "utf8");
      expect(findHardcodedHex(source), `Hardcoded color utilities found in ${relativePath}`).toEqual([]);
      expect(source).toMatch(/var\(--(card-top-border|on-secondary-container|status-danger-bg)\)/);
    },
  );

  it("keeps public landing and authentication surfaces on semantic palette families", () => {
    const combined = PUBLIC_SURFACE_FILES.map((path) => readFileSync(path, "utf8")).join("\n");
    expect(combined).toMatch(/var\(--bg-canvas\)/);
    expect(combined).toMatch(/var\(--surface-(panel|muted|brand-soft)\)/);
    expect(combined).toMatch(/var\(--text-(primary|secondary|brand)\)/);
    expect(combined).toMatch(/var\(--brand-(400|500|600|700)\)/);
    expect(combined).toMatch(/var\(--shell-border\)/);
    expect(combined).not.toContain("#00daf3");
    expect(combined).not.toContain("#60a5fa");
  });
});
