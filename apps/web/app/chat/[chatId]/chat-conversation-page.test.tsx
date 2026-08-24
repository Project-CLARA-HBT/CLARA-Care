import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

const legacySentinel = vi.fn(() => <div data-testid="legacy-chat">legacy</div>);
const v2Sentinel = vi.fn((props: { initialChatId?: string | number | null }) => (
  <div data-testid="v2-chat" data-chat-id={props.initialChatId}>
    v2 chat {props.initialChatId}
  </div>
));
const isChatV2Enabled = vi.fn();
let dynamicCall = 0;

vi.mock("next/navigation", () => ({
  useParams: () => ({ chatId: "101" }),
}));

vi.mock("@/app/chat/_legacy/page-legacy", () => ({ default: legacySentinel }));
vi.mock("@/app/chat/_v2/flag", () => ({ isChatV2Enabled }));
vi.mock("next/dynamic", () => ({
  default: () => (dynamicCall++ === 0 ? v2Sentinel : legacySentinel),
}));

async function renderConversationPage() {
  const mod = await import("@/app/chat/[chatId]/page");
  const Page = mod.default;
  return render(<Page />);
}

afterEach(() => {
  vi.clearAllMocks();
  vi.resetModules();
  dynamicCall = 0;
});

describe("Dynamic chat conversation route (/chat/[chatId])", () => {
  it("renders the legacy chat when CHAT_V2 flag is false", async () => {
    isChatV2Enabled.mockReturnValue(false);
    await renderConversationPage();
    expect(screen.getByTestId("legacy-chat")).toBeInTheDocument();
    expect(screen.queryByTestId("v2-chat")).not.toBeInTheDocument();
    expect(legacySentinel).toHaveBeenCalled();
  });

  it("renders the v2 shell with extracted initialChatId when CHAT_V2 flag is true", async () => {
    isChatV2Enabled.mockReturnValue(true);
    await renderConversationPage();
    const v2Element = screen.getByTestId("v2-chat");
    expect(v2Element).toBeInTheDocument();
    expect(v2Element).toHaveAttribute("data-chat-id", "101");
    expect(screen.queryByTestId("legacy-chat")).not.toBeInTheDocument();
  });
});
