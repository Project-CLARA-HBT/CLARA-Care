import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

/**
 * Feature: clara-chat-redesign, Property P1 (flag isolation), Requirement 8.2.
 *
 * The chat route gate must render the LEGACY page when CHAT_V2 is off, and the
 * v2 shell only when the flag is on. We mock the heavy legacy component and the
 * lazily-loaded v2 shell with light sentinels and drive the gate via the flag.
 */

const legacySentinel = vi.fn(() => <div data-testid="legacy-chat">legacy</div>);
const v2Sentinel = vi.fn(() => <div data-testid="v2-chat">v2</div>);
const isChatV2Enabled = vi.fn();
let dynamicCall = 0;

vi.mock("@/app/chat/_legacy/page-legacy", () => ({ default: legacySentinel }));
vi.mock("@/app/chat/_v2/flag", () => ({ isChatV2Enabled }));
// `next/dynamic` is replaced with eager sentinels so both independently
// code-split rollback paths render synchronously in the test.
vi.mock("next/dynamic", () => ({
  default: () => (dynamicCall++ === 0 ? v2Sentinel : legacySentinel),
}));

async function renderGate() {
  const mod = await import("@/app/chat/page");
  const Gate = mod.default;
  return render(<Gate />);
}

afterEach(() => {
  vi.clearAllMocks();
  vi.resetModules();
  dynamicCall = 0;
});

describe("chat route gate", () => {
  it("renders the legacy chat unchanged when CHAT_V2 is off", async () => {
    isChatV2Enabled.mockReturnValue(false);
    await renderGate();
    expect(screen.getByTestId("legacy-chat")).toBeInTheDocument();
    expect(screen.queryByTestId("v2-chat")).not.toBeInTheDocument();
    expect(legacySentinel).toHaveBeenCalled();
  });

  it("renders the v2 shell when CHAT_V2 is on", async () => {
    isChatV2Enabled.mockReturnValue(true);
    await renderGate();
    expect(screen.getByTestId("v2-chat")).toBeInTheDocument();
    expect(screen.queryByTestId("legacy-chat")).not.toBeInTheDocument();
  });
});
