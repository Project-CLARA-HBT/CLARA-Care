import { describe, expect, it } from "vitest";
import { CommitKernelClient } from "./commit-kernel-client";

describe("CommitKernelClient OCC Dependency Vector Builder", () => {
  it("builds valid write dependency vector with observed partition version", () => {
    const deps = CommitKernelClient.buildDependencyVector("medications:patient-1", 4);
    expect(deps).toHaveLength(1);
    expect(deps[0]).toEqual({
      dependencyKind: "ENTITY",
      dependencyKey: "medications:patient-1",
      accessMode: "WRITE",
      observedVersion: 4,
    });
  });

  it("prepares commit payload with ISO timestamp and dependencies", () => {
    const payload = CommitKernelClient.prepareCommit(
      "UPDATE_MEDICINE",
      "medications:patient-1",
      4,
      { dosage: "500mg" }
    );
    expect(payload.transitionType).toBe("UPDATE_MEDICINE");
    expect(payload.dependencies).toHaveLength(1);
    expect(payload.data).toEqual({ dosage: "500mg" });
    expect(payload.clientTimestamp).toBeDefined();
  });

  it("correctly identifies 409 stale-version conflict responses", () => {
    expect(CommitKernelClient.isStaleVersionConflict(409)).toBe(true);
    expect(CommitKernelClient.isStaleVersionConflict(400, "glhs_stale_dependency_version")).toBe(true);
    expect(CommitKernelClient.isStaleVersionConflict(200)).toBe(false);
    expect(CommitKernelClient.isStaleVersionConflict(404)).toBe(false);
  });
});
