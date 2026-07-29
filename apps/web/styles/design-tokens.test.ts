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
  it("freezes the approved semantic light palette", () => {
    const globals = readFileSync(resolve(here, "globals.css"), "utf8");
    const root = globals.match(/:root\s*\{([\s\S]*?)\n\}/)?.[1] ?? "";
    expect(root).toContain("--bg-canvas: #f4f6fb;");
    expect(root).toContain("--surface-sidebar: #f8faff;");
    expect(root).toContain("--surface-panel: #ffffff;");
    expect(root).toContain("--surface-muted: #f6f8fc;");
    expect(root).toContain("--text-primary: #172033;");
    expect(root).toContain("--text-secondary: #46556a;");
    expect(root).toContain("--shell-border: #dfe5ef;");
    expect(root).toContain("--shell-border-strong: #94a3bd;");
  });

  it("freezes the approved semantic dark palette", () => {
    const globals = readFileSync(resolve(here, "globals.css"), "utf8");
    const dark =
      globals.match(
        /html\.dark,\s*html\[data-theme="dark"\]\s*\{([\s\S]*?)\n\}/,
      )?.[1] ?? "";
    expect(dark).toContain("--bg-canvas: #1b1a19;");
    expect(dark).toContain("--surface-panel: #292929;");
    expect(dark).toContain("--surface-muted: #333333;");
    expect(dark).toContain("--text-primary: #ffffff;");
    expect(dark).toContain("--text-secondary: #d6d6d6;");
    expect(dark).toContain("--shell-border: #484848;");
    expect(dark).toContain("--shell-border-strong: #8a8886;");
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
});
