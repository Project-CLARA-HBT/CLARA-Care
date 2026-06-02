import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";
import fc from "fast-check";

/**
 * Feature: product-polish-analytics, Property 22
 * Used foreground/background design-token pairs meet WCAG 2.1 AA contrast.
 *
 * Validates: Requirements 5.3
 *
 * The contrast math mirrors `apps/web/_contrast_audit.mjs`: each color (possibly
 * an `rgba`) is composited over an opaque base, relative luminance is computed,
 * and the ratio must clear the AA threshold for its usage:
 *   - normal text: >= 4.5:1
 *   - large text / UI components / borders: >= 3:1
 *
 * The token values are read from `globals.css` so the test fails if a token is
 * regressed below AA. We assert against the actual `:root` (light) and
 * `html.dark` (dark) token blocks parsed from that file.
 */

type Rgb = [number, number, number];
type Rgba = [number, number, number, number];

const here = dirname(fileURLToPath(import.meta.url));
const GLOBALS_CSS = readFileSync(resolve(here, "globals.css"), "utf8");

// --- color math (WCAG 2.1) -------------------------------------------------

function hexToRgb(hex: string): Rgb {
  let value = hex.replace("#", "").trim();
  if (value.length === 3) {
    value = value
      .split("")
      .map((c) => c + c)
      .join("");
  }
  return [
    parseInt(value.slice(0, 2), 16),
    parseInt(value.slice(2, 4), 16),
    parseInt(value.slice(4, 6), 16)
  ];
}

function composite([r, g, b, a]: Rgba, base: Rgb): Rgb {
  return [
    Math.round(r * a + base[0] * (1 - a)),
    Math.round(g * a + base[1] * (1 - a)),
    Math.round(b * a + base[2] * (1 - a))
  ];
}

function luminance([r, g, b]: Rgb): number {
  const channel = (v: number) => {
    const s = v / 255;
    return s <= 0.03928 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4);
  };
  return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b);
}

function contrastRatio(fg: Rgb, bg: Rgb): number {
  const l1 = luminance(fg);
  const l2 = luminance(bg);
  const [hi, lo] = l1 > l2 ? [l1, l2] : [l2, l1];
  return (hi + 0.05) / (lo + 0.05);
}

// --- token parsing from globals.css ---------------------------------------

/** Extracts the `:root { ... }` (light) declaration block. */
function lightBlock(): string {
  const match = GLOBALS_CSS.match(/:root\s*\{([\s\S]*?)\n\}/);
  if (!match) throw new Error("Could not locate :root block in globals.css");
  return match[1];
}

/** Extracts the `html.dark, html[data-theme="dark"] { ... }` declaration block. */
function darkBlock(): string {
  const match = GLOBALS_CSS.match(
    /html\.dark,\s*\n?\s*html\[data-theme="dark"\]\s*\{([\s\S]*?)\n\}/
  );
  if (!match) throw new Error("Could not locate html.dark block in globals.css");
  return match[1];
}

function readToken(block: string, name: string): string {
  const re = new RegExp(`--${name}\\s*:\\s*([^;]+);`);
  const match = block.match(re);
  if (!match) throw new Error(`Token --${name} not found`);
  return match[1].trim();
}

/** Parse a token value (`#hex` or `rgba(...)`/`rgb(...)`) into an Rgba. */
function parseColor(value: string): Rgba {
  const v = value.trim();
  if (v.startsWith("#")) {
    const [r, g, b] = hexToRgb(v);
    return [r, g, b, 1];
  }
  const m = v.match(/rgba?\(([^)]+)\)/i);
  if (!m) throw new Error(`Unsupported color token: ${value}`);
  const parts = m[1].split(",").map((p) => parseFloat(p.trim()));
  const [r, g, b, a = 1] = parts;
  return [r, g, b, a];
}

const LIGHT = lightBlock();
const DARK = darkBlock();

const LIGHT_CANVAS = parseColor(readToken(LIGHT, "bg-canvas")) as Rgba;
const DARK_CANVAS = parseColor(readToken(DARK, "bg-canvas")) as Rgba;
const LIGHT_CANVAS_RGB = composite(LIGHT_CANVAS, [255, 255, 255]);
const DARK_CANVAS_RGB = composite(DARK_CANVAS, [255, 255, 255]);
const WHITE: Rgb = [255, 255, 255];

type Pair = {
  label: string;
  fg: Rgba;
  bg: Rgba;
  base: Rgb;
  min: number;
};

function token(block: string, name: string): Rgba {
  return parseColor(readToken(block, name));
}

// Foreground/background token pairs that are actually used together across the
// primary surfaces, with the AA threshold appropriate to their usage.
const PAIRS: Pair[] = [
  // ---- LIGHT: text on canvas (normal text >= 4.5) ----
  {
    label: "LIGHT text-primary on canvas",
    fg: token(LIGHT, "text-primary"),
    bg: LIGHT_CANVAS,
    base: WHITE,
    min: 4.5
  },
  {
    label: "LIGHT text-secondary on canvas",
    fg: token(LIGHT, "text-secondary"),
    bg: LIGHT_CANVAS,
    base: WHITE,
    min: 4.5
  },
  {
    label: "LIGHT text-muted on surface-muted",
    fg: token(LIGHT, "text-muted"),
    bg: token(LIGHT, "surface-muted"),
    base: WHITE,
    min: 4.5
  },
  {
    label: "LIGHT text-brand on canvas",
    fg: token(LIGHT, "text-brand"),
    bg: LIGHT_CANVAS,
    base: WHITE,
    min: 4.5
  },
  {
    label: "LIGHT text-brand on surface-brand-soft",
    fg: token(LIGHT, "text-brand"),
    bg: token(LIGHT, "surface-brand-soft"),
    base: WHITE,
    min: 4.5
  },
  // ---- LIGHT: white label on brand buttons (normal text >= 4.5) ----
  {
    label: "LIGHT white text on brand-700 button",
    fg: [255, 255, 255, 1],
    bg: token(LIGHT, "brand-700"),
    base: WHITE,
    min: 4.5
  },
  // ---- LIGHT: brand-600 as UI/large-text (>= 3) ----
  {
    label: "LIGHT brand-600 on white (link/large)",
    fg: token(LIGHT, "brand-600"),
    bg: [255, 255, 255, 1],
    base: WHITE,
    min: 3.0
  },
  // ---- LIGHT: status text on status bg (normal text >= 4.5) ----
  {
    label: "LIGHT status-ok-text on status-ok-bg",
    fg: token(LIGHT, "status-ok-text"),
    bg: token(LIGHT, "status-ok-bg"),
    base: WHITE,
    min: 4.5
  },
  {
    label: "LIGHT status-warn-text on status-warn-bg",
    fg: token(LIGHT, "status-warn-text"),
    bg: token(LIGHT, "status-warn-bg"),
    base: WHITE,
    min: 4.5
  },
  {
    label: "LIGHT status-danger-text on status-danger-bg",
    fg: token(LIGHT, "status-danger-text"),
    bg: token(LIGHT, "status-danger-bg"),
    base: WHITE,
    min: 4.5
  },
  {
    label: "LIGHT status-neutral-text on status-neutral-bg",
    fg: token(LIGHT, "status-neutral-text"),
    bg: token(LIGHT, "status-neutral-bg"),
    base: WHITE,
    min: 4.5
  },
  // ---- DARK: text on canvas (normal text >= 4.5) ----
  {
    label: "DARK text-primary on canvas",
    fg: token(DARK, "text-primary"),
    bg: DARK_CANVAS,
    base: DARK_CANVAS_RGB,
    min: 4.5
  },
  {
    label: "DARK text-secondary on canvas",
    fg: token(DARK, "text-secondary"),
    bg: DARK_CANVAS,
    base: DARK_CANVAS_RGB,
    min: 4.5
  },
  {
    label: "DARK text-muted on surface-muted",
    fg: token(DARK, "text-muted"),
    bg: token(DARK, "surface-muted"),
    base: DARK_CANVAS_RGB,
    min: 4.5
  },
  {
    label: "DARK text-brand on canvas (large/link)",
    fg: token(DARK, "text-brand"),
    bg: DARK_CANVAS,
    base: DARK_CANVAS_RGB,
    min: 3.0
  },
  {
    label: "DARK status-ok-text on status-ok-bg",
    fg: token(DARK, "status-ok-text"),
    bg: token(DARK, "status-ok-bg"),
    base: DARK_CANVAS_RGB,
    min: 4.5
  },
  {
    label: "DARK status-warn-text on status-warn-bg",
    fg: token(DARK, "status-warn-text"),
    bg: token(DARK, "status-warn-bg"),
    base: DARK_CANVAS_RGB,
    min: 4.5
  },
  {
    label: "DARK status-danger-text on status-danger-bg",
    fg: token(DARK, "status-danger-text"),
    bg: token(DARK, "status-danger-bg"),
    base: DARK_CANVAS_RGB,
    min: 4.5
  },
  {
    label: "DARK status-neutral-text on status-neutral-bg",
    fg: token(DARK, "status-neutral-text"),
    bg: token(DARK, "status-neutral-bg"),
    base: DARK_CANVAS_RGB,
    min: 4.5
  }
];

function ratioFor(pair: Pair): number {
  return contrastRatio(composite(pair.fg, pair.base), composite(pair.bg, pair.base));
}

describe("design-token contrast (Feature: product-polish-analytics, Property 22)", () => {
  it("parses the canvas tokens from globals.css", () => {
    expect(LIGHT_CANVAS_RGB).toHaveLength(3);
    expect(DARK_CANVAS_RGB).toHaveLength(3);
  });

  it.each(PAIRS.map((p) => [p.label, p] as const))(
    "%s meets its AA threshold",
    (_label, pair) => {
      const ratio = ratioFor(pair);
      expect(ratio).toBeGreaterThanOrEqual(pair.min);
    }
  );

  it("Property 22: every used token pair meets its AA contrast threshold", () => {
    fc.assert(
      fc.property(fc.constantFrom(...PAIRS), (pair) => {
        return ratioFor(pair) >= pair.min;
      }),
      { numRuns: 200 }
    );
  });
});
