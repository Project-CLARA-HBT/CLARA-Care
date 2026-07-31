import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it, vi } from "vitest";

/**
 * Research is intentionally a single Chat workflow. These old bookmarks must
 * remain thin server redirects, never resurrect the archived workspace.
 */
const redirect = vi.fn();
vi.mock("next/navigation", () => ({
  redirect: (path: string) => redirect(path),
}));

const legacyRoutes = [
  { path: "/research", file: "page.tsx", load: () => import("./page") },
  {
    path: "/research/analyze",
    file: "analyze/page.tsx",
    load: () => import("./analyze/page"),
  },
  {
    path: "/research/citations",
    file: "citations/page.tsx",
    load: () => import("./citations/page"),
  },
  {
    path: "/research/deepdive",
    file: "deepdive/page.tsx",
    load: () => import("./deepdive/page"),
  },
  {
    path: "/research/details",
    file: "details/page.tsx",
    load: () => import("./details/page"),
  },
] as const;

describe("research route consolidation", () => {
  it.each(legacyRoutes)(
    "redirects $path into the unified Chat workflow",
    async ({ load }) => {
      redirect.mockClear();
      const route = await load();
      route.default();
      expect(redirect).toHaveBeenCalledWith("/chat");
    },
  );

  it("does not leave an active route importing the archived Research workspace", async () => {
    const activeRouteSources = legacyRoutes.map(({ file }) =>
      readFileSync(resolve(__dirname, file), "utf8"),
    );

    expect(activeRouteSources.join("\n")).not.toContain("research-workspace");
  });
});
