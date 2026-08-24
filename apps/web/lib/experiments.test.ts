import { describe, expect, it, beforeEach, vi } from "vitest";
import {
  calculateExperimentStats,
  DEFAULT_EXPERIMENTS,
  listExperiments,
  overrideKillSwitch,
  resetInMemoryExperiments,
  updateExperiment,
} from "./experiments";

describe("experiments domain library (Spec v5 Section 6.67)", () => {
  beforeEach(() => {
    resetInMemoryExperiments();
    vi.clearAllMocks();
  });

  it("calculates accurate summary stats from experiment list", () => {
    const stats = calculateExperimentStats(DEFAULT_EXPERIMENTS);
    expect(stats.totalFlags).toBe(DEFAULT_EXPERIMENTS.length);
    expect(stats.safetyInvariants).toBe(2);
    expect(stats.fullyEnabled).toBeGreaterThan(0);
    expect(stats.activeRollouts).toBeGreaterThan(0);
  });

  it("lists default experiments when backend is offline", async () => {
    const list = await listExperiments();
    expect(list.length).toBe(DEFAULT_EXPERIMENTS.length);
    expect(list.some((e) => e.key === "rag_graphrag_pipeline")).toBe(true);
    expect(list.some((e) => e.key === "fides_critical_ddi_blocking")).toBe(true);
  });

  it("updates rollout percentage and updates status dynamically", async () => {
    const updated = await updateExperiment("exp-graphrag", {
      rolloutPercentage: 75,
    });
    expect(updated.rolloutPercentage).toBe(75);
    expect(updated.status).toBe("gradual_rollout");

    const fullRollout = await updateExperiment("exp-graphrag", {
      rolloutPercentage: 100,
    });
    expect(fullRollout.rolloutPercentage).toBe(100);
    expect(fullRollout.status).toBe("active");

    const turnedOff = await updateExperiment("exp-graphrag", {
      rolloutPercentage: 0,
    });
    expect(turnedOff.rolloutPercentage).toBe(0);
    expect(turnedOff.status).toBe("inactive");
  });

  it("enforces ANA-005 invariant: prevents reducing rollout on safety invariants", async () => {
    await expect(
      updateExperiment("exp-fides-gate", {
        rolloutPercentage: 50,
      })
    ).rejects.toThrow(/safety invariant/i);
  });

  it("enforces ANA-005 invariant: prevents kill switch on safety invariants", async () => {
    await expect(
      overrideKillSwitch("exp-fides-gate", true, "Testing emergency override")
    ).rejects.toThrow(/safety invariant/i);
  });

  it("activates and deactivates kill switch on normal experiment flags", async () => {
    const killed = await overrideKillSwitch(
      "exp-scribe-filter",
      true,
      "Acoustic noise degradation reported"
    );
    expect(killed.killSwitchActive).toBe(true);
    expect(killed.status).toBe("killed");
    expect(killed.killSwitchReason).toBe("Acoustic noise degradation reported");

    const restored = await overrideKillSwitch("exp-scribe-filter", false);
    expect(restored.killSwitchActive).toBe(false);
    expect(restored.status).toBe("gradual_rollout");
  });

  it("updates targeting roles and cohorts", async () => {
    const updated = await updateExperiment("exp-lifemap-reminders", {
      targetRoles: ["normal", "doctor"],
      targetCohorts: ["beta_testers", "vietnam_hospitals"],
    });
    expect(updated.targetRoles).toEqual(["normal", "doctor"]);
    expect(updated.targetCohorts).toEqual(["beta_testers", "vietnam_hospitals"]);
  });
});
