import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

/**
 * Feature: clara-ui-ux-redesign — Req 1.1, 1.4
 * Every standard (non-immersive) page must share ONE content width so the
 * layout never jumps between routes. This guards against reintroducing the
 * old `isWideWorkspace` fork that gave some pages full-bleed and others a
 * centered cap.
 */

const here = dirname(fileURLToPath(import.meta.url));
const appShell = readFileSync(resolve(here, "app-shell.tsx"), "utf8");

describe("consistent content width (Req 1.1, 1.4)", () => {
  it("does not fork content width by a wide-workspace route list", () => {
    expect(appShell).not.toContain("isWideWorkspace");
    expect(appShell).not.toContain("WIDE_WORKSPACE_PREFIXES");
  });

  it("uses a single shared max-width for non-immersive pages", () => {
    // Exactly one centered content column token for standard pages.
    const matches = appShell.match(/mx-auto max-w-\[\d+px\]/g) ?? [];
    expect(matches.length).toBe(1);
  });
});
