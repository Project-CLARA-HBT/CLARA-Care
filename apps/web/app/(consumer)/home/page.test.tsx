import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import ConsumerHomePage from "./page";
import { v2Client } from "@/lib/api/v2-client";

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: vi.fn(),
    replace: vi.fn(),
    prefetch: vi.fn(),
    back: vi.fn(),
  }),
}));

afterEach(cleanup);
beforeEach(() => {
  vi.clearAllMocks();
});

describe("ConsumerHomePage (/home route)", () => {
  it("mounts HomeView and initiates data fetching", () => {
    vi.spyOn(v2Client, "getHome").mockImplementation(() => new Promise(() => {}));

    render(<ConsumerHomePage />);

    expect(screen.getByTestId("consumer-home-view")).toBeInTheDocument();
    expect(screen.getByTestId("health-page-header")).toBeInTheDocument();
    expect(screen.getByTestId("home-ask-section")).toBeInTheDocument();
  });
});
