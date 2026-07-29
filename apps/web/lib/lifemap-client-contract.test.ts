import { beforeEach, describe, expect, it, vi } from "vitest";

import api from "@/lib/http-client";
import {
  getLifeMapClientContract,
  LIFE_MAP_CLIENT_STATES,
} from "@/lib/lifemap";

vi.mock("@/lib/http-client", () => ({
  default: { get: vi.fn() },
}));

describe("LifeMap client contract", () => {
  beforeEach(() => vi.clearAllMocks());

  it("uses the exact server-authoritative state vocabulary", async () => {
    const states = Object.fromEntries(
      LIFE_MAP_CLIENT_STATES.map((state) => [
        state,
        { truth_authority: state === "confirmed", can_mutate: true, vi: state, en: state },
      ]),
    );
    vi.mocked(api.get).mockResolvedValue({
      data: {
        version: "lifemap-client-contract-v1",
        states,
        capabilities: {
          capture: { enabled: false, mutation_policy: "online_only" },
        },
        offline_policy: {
          mutations: "disabled",
          queued_health_mutations_supported: false,
          cached_safety_status_current: false,
          requires_encrypted_cache: true,
          requires_cached_at: true,
          requires_valid_until: true,
        },
      },
    });

    const contract = await getLifeMapClientContract();
    expect(Object.keys(contract.states)).toEqual(LIFE_MAP_CLIENT_STATES);
    expect(contract.states.confirmed.truth_authority).toBe(true);
    expect(contract.states.offline.truth_authority).toBe(false);
    expect(contract.offline_policy.queued_health_mutations_supported).toBe(false);
    expect(api.get).toHaveBeenCalledWith("/lifemap/v2/client-contract");
  });
});
