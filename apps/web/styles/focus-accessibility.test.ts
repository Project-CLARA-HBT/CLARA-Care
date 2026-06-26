import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

import { describe, expect, it } from "vitest";

/**
 * Feature: product-polish-analytics
 *  - Req 5.4: When navigating with a keyboard, CLARA_Web exposes a visible
 *             focus indicator and a logical tab order on interactive controls.
 *
 * These checks assert the focus indicator is defined once via design tokens and
 * applied to interactive controls with a real (forced-colors-safe) outline, and
 * that the app shell provides a skip link for a logical tab order.
 */

const here = dirname(fileURLToPath(import.meta.url));
const globalsCss = readFileSync(resolve(here, "globals.css"), "utf8");
const appShell = readFileSync(
  resolve(here, "..", "components", "app-shell.tsx"),
  "utf8"
);

describe("focus ring tokens (Req 5.4)", () => {
  it("defines the focus-ring design tokens once in :root", () => {
    expect(globalsCss).toContain("--focus-ring-color:");
    expect(globalsCss).toContain("--focus-ring-width:");
    expect(globalsCss).toContain("--focus-ring-offset:");
  });

  it("provides a dark-theme focus-ring color override", () => {
    const darkBlock = globalsCss.slice(globalsCss.indexOf('html.dark,'));
    expect(darkBlock).toContain("--focus-ring-color:");
  });
});

describe("visible focus indicator (Req 5.4)", () => {
  // Isolate the global :focus-visible rule block for inspection.
  const focusRuleStart = globalsCss.indexOf(".focus-ring:focus-visible {");
  const focusRule = globalsCss.slice(focusRuleStart, focusRuleStart + 200);

  it("draws a real outline from the focus tokens (not just a box-shadow)", () => {
    expect(focusRule).toContain("outline: var(--focus-ring-width) solid var(--focus-ring-color)");
    expect(focusRule).toContain("outline-offset: var(--focus-ring-offset)");
  });

  it("does not suppress the keyboard focus outline with outline: none", () => {
    expect(focusRule).not.toContain("outline: none");
  });

  it("applies the indicator to interactive and custom-role controls", () => {
    // The selector group preceding the focus rule must cover these controls.
    const selectorBlock = globalsCss.slice(focusRuleStart - 600, focusRuleStart);
    for (const selector of [
      "button",
      "input",
      "textarea",
      "select",
      "summary",
      '[role="button"]',
      '[role="tab"]',
      '[role="menuitem"]'
    ]) {
      expect(selectorBlock).toContain(selector);
    }
  });

  it("keeps the focus indicator visible under forced-colors mode", () => {
    expect(globalsCss).toContain("@media (forced-colors: active)");
    expect(globalsCss).toContain("outline-color: Highlight");
  });
});

describe("skip link for logical tab order (Req 5.4)", () => {
  it("defines a .skip-link style that is hidden until focused", () => {
    const start = globalsCss.indexOf(".skip-link {");
    expect(start).toBeGreaterThan(-1);
    const block = globalsCss.slice(start, start + 400);
    // Hidden offscreen by default, revealed on focus.
    expect(block).toContain("transform: translateY(-180%)");
    expect(globalsCss).toContain(".skip-link:focus");
    expect(globalsCss).toContain("transform: translateY(0)");
  });

  it("renders the skip link as the first focusable element targeting #main-content", () => {
    expect(appShell).toContain('href="#main-content"');
    expect(appShell).toContain('className="skip-link"');
    expect(appShell).toContain("Bỏ qua, tới nội dung chính");
  });

  it("marks the main content landmark with the skip-link target id", () => {
    expect(appShell).toContain('id="main-content"');
  });
});
