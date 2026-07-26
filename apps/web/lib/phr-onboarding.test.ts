import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  get: vi.fn(),
  patch: vi.fn(),
}));

vi.mock("@/lib/http-client", () => ({
  default: {
    get: mocks.get,
    patch: mocks.patch,
  },
}));

import {
  getPhrOnboarding,
  updatePhrOnboarding,
} from "@/lib/phr-onboarding";

describe("PHR onboarding API", () => {
  beforeEach(() => vi.clearAllMocks());

  it("loads the durable server-owned onboarding state", async () => {
    mocks.get.mockResolvedValue({
      data: { status: "pending", needs_onboarding: true },
    });
    await expect(getPhrOnboarding()).resolves.toMatchObject({
      status: "pending",
      needs_onboarding: true,
    });
    expect(mocks.get).toHaveBeenCalledWith("/api/v1/phr/onboarding");
  });

  it("completes only with explicit self-declared confirmation", async () => {
    mocks.patch.mockResolvedValue({
      data: { status: "completed", needs_onboarding: false },
    });
    await updatePhrOnboarding({
      action: "complete",
      confirm_self_declared: true,
      personalization_consent: true,
    });
    expect(mocks.patch).toHaveBeenCalledWith("/api/v1/phr/onboarding", {
      action: "complete",
      confirm_self_declared: true,
      personalization_consent: true,
    });
  });
});
