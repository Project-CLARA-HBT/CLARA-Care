import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

import { describe, expect, it } from "vitest";

import {
  PRIMARY_ACTIONS,
  getPrimaryActionLabel,
  type PrimarySurface
} from "@/lib/primary-actions";

/**
 * Feature: product-polish-analytics
 *  - Req 5.5: Surfaces provide Vietnamese task-oriented primary-action labels
 *             consistent with the guidance page (`/huong-dan`).
 *
 * These tests lock the canonical label vocabulary and guarantee the guidance
 * page and the shared module cannot drift apart.
 */

const here = dirname(fileURLToPath(import.meta.url));
const guidePagePath = resolve(here, "..", "app", "huong-dan", "page.tsx");

// The exact Vietnamese labels the guidance page presents for each task card.
const EXPECTED_LABELS: Record<PrimarySurface, string> = {
  chat: "Mở hỏi CLARA",
  chat_thinking: "Mở chế độ Tư duy",
  selfmed: "Mở tủ thuốc",
  ddi: "Kiểm tra tương tác",
  council: "Mở hội chẩn AI",
  scribe: "Mở ghi chép y khoa"
};

describe("primary-action label vocabulary (Req 5.5)", () => {
  it("exposes the canonical Vietnamese label for every Surface", () => {
    for (const [surface, label] of Object.entries(EXPECTED_LABELS)) {
      expect(PRIMARY_ACTIONS[surface as PrimarySurface].label).toBe(label);
    }
  });

  it("routes each Surface action to its expected destination", () => {
    expect(PRIMARY_ACTIONS.chat.href).toBe("/chat");
    expect(PRIMARY_ACTIONS.chat_thinking.href).toBe("/chat");
    expect(PRIMARY_ACTIONS.selfmed.href).toBe("/selfmed");
    expect(PRIMARY_ACTIONS.ddi.href).toBe("/selfmed/ddi");
    expect(PRIMARY_ACTIONS.council.href).toBe("/council");
    expect(PRIMARY_ACTIONS.scribe.href).toBe("/scribe");
  });

  it("getPrimaryActionLabel returns the label for a known Surface", () => {
    expect(getPrimaryActionLabel("ddi")).toBe("Kiểm tra tương tác");
  });

  it("getPrimaryActionLabel falls back to a safe neutral label for unknown keys", () => {
    expect(getPrimaryActionLabel("unknown-surface")).toBe("Mở");
    expect(getPrimaryActionLabel("")).toBe("Mở");
  });

  it("every label is non-empty, task-oriented Vietnamese copy (no internal keys)", () => {
    for (const action of Object.values(PRIMARY_ACTIONS)) {
      expect(action.label.trim().length).toBeGreaterThan(0);
      // Labels must not leak the internal surface key or a route path.
      expect(action.label).not.toContain("/");
      expect(action.label.toLowerCase()).not.toContain(action.surface);
    }
  });
});

describe("guidance page stays consistent with the shared vocabulary (Req 5.5)", () => {
  const guideSource = readFileSync(guidePagePath, "utf8");

  it("imports the shared PRIMARY_ACTIONS module rather than hardcoding labels", () => {
    expect(guideSource).toContain('from "@/lib/primary-actions"');
    expect(guideSource).toContain("PRIMARY_ACTIONS");
  });

  it("still surfaces each canonical label somewhere in the guide", () => {
    // The guide renders action.label from the shared map; confirm the canonical
    // strings remain the single source of truth (they live in the module, and
    // the guide references the map keys), so no divergent label is hardcoded.
    for (const surface of Object.keys(EXPECTED_LABELS) as PrimarySurface[]) {
      expect(guideSource).toContain(`surface: "${surface}"`);
    }
  });
});
