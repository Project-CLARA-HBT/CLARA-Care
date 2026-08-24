import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const here = dirname(fileURLToPath(import.meta.url));
const repositoryRoot = resolve(here, "..", "..", "..");
const contractPath = resolve(repositoryRoot, "contracts/design-tokens/tokens.json");
const tokensCssPath = resolve(here, "tokens.css");

describe("Design tokens contract and CSS custom properties", () => {
  const contract = JSON.parse(readFileSync(contractPath, "utf8"));
  const tokensCss = readFileSync(tokensCssPath, "utf8");

  it("conforms to the clara.design-tokens contract metadata", () => {
    expect(contract.contract).toBe("clara.design-tokens");
    expect(contract.version).toBe("2026-08-19.v1");
    expect(contract.tokens).toBeDefined();
  });

  it("contains all required semantic token families", () => {
    const families = [
      "color",
      "space",
      "radius",
      "typography",
      "elevation",
      "status",
      "health_state",
      "source_state",
    ];
    for (const family of families) {
      expect(contract.tokens[family], `missing family ${family}`).toBeDefined();
    }
  });

  it("contains all required health states", () => {
    const states = [
      "confirmed",
      "user_reported",
      "imported",
      "device",
      "unconfirmed",
      "stopped",
      "conflict",
      "stale",
    ];
    for (const state of states) {
      expect(contract.tokens.health_state[state], `missing health state ${state}`).toBeDefined();
      expect(contract.tokens.health_state[state].label_vi).toBeTruthy();
      expect(contract.tokens.health_state[state].label_en).toBeTruthy();
      expect(contract.tokens.health_state[state].tone).toBeTruthy();
      expect(contract.tokens.health_state[state].icon).toBeTruthy();
    }
  });

  it("contains all required source states", () => {
    const states = [
      "verified",
      "self_reported",
      "imported",
      "device",
      "pending",
      "unverified",
    ];
    for (const state of states) {
      expect(contract.tokens.source_state[state], `missing source state ${state}`).toBeDefined();
      expect(contract.tokens.source_state[state].label_vi).toBeTruthy();
      expect(contract.tokens.source_state[state].label_en).toBeTruthy();
      expect(contract.tokens.source_state[state].tone).toBeTruthy();
      expect(contract.tokens.source_state[state].icon).toBeTruthy();
    }
  });

  it("tokens.css exposes semantic CSS variables matching the token contract", () => {
    expect(tokensCss).toContain("--color-surface-canvas:");
    expect(tokensCss).toContain("--color-surface-base:");
    expect(tokensCss).toContain("--color-content-primary:");
    expect(tokensCss).toContain("--color-content-secondary:");
    expect(tokensCss).toContain("--color-border-subtle:");
    expect(tokensCss).toContain("--color-action-primary:");
    expect(tokensCss).toContain("--color-feedback-ok-bg:");
    expect(tokensCss).toContain("--color-feedback-warn-bg:");
    expect(tokensCss).toContain("--color-feedback-danger-bg:");
    expect(tokensCss).toContain("--radius-pill:");
    expect(tokensCss).toContain("--touch-target-min:");
    expect(tokensCss).toContain("--glass-bg-header:");
    expect(tokensCss).toContain("--glass-bg-navbar:");
    expect(tokensCss).toContain("--glass-bg-sheet:");
    expect(tokensCss).toContain("--glass-bg-menu:");
    expect(tokensCss).toContain("--glass-border-subtle:");
    expect(tokensCss).toContain("--glass-blur-header:");
    expect(tokensCss).toContain("--glass-blur-navbar:");
  });
});
