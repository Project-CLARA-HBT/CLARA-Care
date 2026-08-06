import { render, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  pathname: "/today",
  getConsentStatus: vi.fn(),
  setConsent: vi.fn(),
  identify: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  usePathname: () => mocks.pathname,
}));

vi.mock("@/lib/consent", () => ({
  getConsentStatus: mocks.getConsentStatus,
}));

vi.mock("@/lib/analytics", () => ({
  getAnalyticsClient: () => ({
    setConsent: mocks.setConsent,
    identify: mocks.identify,
  }),
}));

vi.mock("@/lib/auth-store", () => ({ getRole: () => "normal" }));

import AnalyticsConsentBootstrap from "./analytics-consent-bootstrap";

describe("AnalyticsConsentBootstrap public capabilities", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.pathname = "/today";
    mocks.getConsentStatus.mockResolvedValue({ accepted: true, user_id: 12 });
  });

  it("suppresses consent traffic and analytics on an opaque public PHR share", async () => {
    mocks.pathname = "/phr/shared/opaque-token";

    render(<AnalyticsConsentBootstrap />);

    await waitFor(() => expect(mocks.setConsent).toHaveBeenCalledWith(false));
    expect(mocks.getConsentStatus).not.toHaveBeenCalled();
    expect(mocks.identify).not.toHaveBeenCalled();
  });

  it("does not request authenticated consent from the public landing page", async () => {
    mocks.pathname = "/";
    render(<AnalyticsConsentBootstrap />);
    await waitFor(() => expect(mocks.setConsent).toHaveBeenCalledWith(false));
    expect(mocks.getConsentStatus).not.toHaveBeenCalled();
  });
});
