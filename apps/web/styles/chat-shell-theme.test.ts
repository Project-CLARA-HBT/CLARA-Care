import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const styles = readFileSync(join(process.cwd(), "styles/globals.css"), "utf8");

describe("CLARA Chat theme integration", () => {
  it("inherits the application canvas and sidebar tokens in every theme", () => {
    const chatRule = styles.match(
      /\n\.clara-chat-v2 \{\n([\s\S]*?)\n\}/,
    )?.[1];

    expect(chatRule).toBeDefined();
    expect(chatRule).not.toMatch(/--bg-canvas\s*:/);
    expect(chatRule).not.toMatch(/--surface-sidebar\s*:/);
    expect(chatRule).toContain("var(--bg-canvas)");
  });

  it("uses the resolved dark canvas without a light fallback", () => {
    expect(styles).toMatch(
      /html\.dark \.clara-chat-v2,[\s\S]*?html\[data-theme="dark"\] \.clara-chat-v2\s*\{\s*background:\s*var\(--bg-canvas\);\s*\}/,
    );
  });
});
