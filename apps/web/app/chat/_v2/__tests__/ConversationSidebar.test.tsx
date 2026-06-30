import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";

import ConversationSidebar from "@/app/chat/_v2/components/ConversationSidebar";
import type { WorkspaceConversationItem } from "@/lib/workspace";

/**
 * Feature: clara-chat-redesign, task 6.1 — ConversationSidebar
 * (list / search / folders entry, virtualized). Requirement 2.4, 6.4, 7.1.
 *
 * jsdom has no layout, so `@tanstack/react-virtual` would otherwise window to
 * zero rows. We stub it to render every row deterministically, which lets us
 * assert list/selection/header behavior while the production component stays
 * virtualized (Requirement 7.1).
 */
vi.mock("@tanstack/react-virtual", () => ({
  useVirtualizer: ({ count }: { count: number }) => ({
    getTotalSize: () => count * 52,
    getVirtualItems: () =>
      Array.from({ length: count }, (_, index) => ({
        index,
        key: index,
        start: index * 52,
        size: 52,
      })),
    measureElement: () => undefined,
  }),
}));

function makeConversation(
  overrides: Partial<WorkspaceConversationItem> = {},
): WorkspaceConversationItem {
  const now = new Date().toISOString();
  return {
    conversation_id: 1,
    title: "Metformin question",
    preview: "Metformin question",
    query_id: null,
    message_count: 3,
    created_at: now,
    last_message_at: now,
    folder_id: null,
    channel_id: null,
    is_favorite: false,
    ...overrides,
  };
}

function baseProps() {
  return {
    conversations: [] as WorkspaceConversationItem[],
    activeId: null as number | null,
    isLoading: false,
    searchText: "",
    onSearchChange: vi.fn(),
    onSelect: vi.fn(),
    onNewChat: vi.fn(),
    onOpenFolders: vi.fn(),
    uiLanguage: "en" as const,
  };
}

describe("ConversationSidebar", () => {
  it("renders conversation rows with a day-bucket header (Req 2.4, 7.1)", () => {
    const props = baseProps();
    props.conversations = [
      makeConversation({ conversation_id: 1, title: "First chat" }),
      makeConversation({ conversation_id: 2, title: "Second chat" }),
    ];
    render(<ConversationSidebar {...props} />);

    expect(screen.getByText("First chat")).toBeInTheDocument();
    expect(screen.getByText("Second chat")).toBeInTheDocument();
    // Both rows are dated "now" → a single "Today" bucket header.
    expect(screen.getByText("Today")).toBeInTheDocument();
  });

  it("forwards typed search text (Req 6.4)", () => {
    const props = baseProps();
    render(<ConversationSidebar {...props} />);
    fireEvent.change(screen.getByLabelText("Search conversations"), {
      target: { value: "aspirin" },
    });
    expect(props.onSearchChange).toHaveBeenCalledWith("aspirin");
  });

  it("invokes selection when a conversation row is clicked", () => {
    const props = baseProps();
    const item = makeConversation({ conversation_id: 7, title: "Pick me" });
    props.conversations = [item];
    render(<ConversationSidebar {...props} />);
    fireEvent.click(screen.getByText("Pick me"));
    expect(props.onSelect).toHaveBeenCalledWith(item);
  });

  it("exposes a folders entry point that opens the workspace (Req 2.4, 6.4)", () => {
    const props = baseProps();
    render(<ConversationSidebar {...props} />);
    fireEvent.click(screen.getByRole("button", { name: /Folders & workspace/i }));
    expect(props.onOpenFolders).toHaveBeenCalledTimes(1);
  });

  it("hides the folders entry when no handler is provided", () => {
    const props = baseProps();
    render(<ConversationSidebar {...props} onOpenFolders={undefined} />);
    expect(
      screen.queryByRole("button", { name: /Folders & workspace/i }),
    ).not.toBeInTheDocument();
  });

  it("shows an empty state with a new-chat affordance", () => {
    const props = baseProps();
    render(<ConversationSidebar {...props} />);
    expect(screen.getByText("No conversations yet.")).toBeInTheDocument();
  });
});
