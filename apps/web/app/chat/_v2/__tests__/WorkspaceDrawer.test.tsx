import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import WorkspaceDrawer from "@/app/chat/_v2/components/WorkspaceDrawer";
import type { UseWorkspace } from "@/app/chat/_v2/hooks/useWorkspace";
import type {
  WorkspaceConversationShareListItem,
  WorkspaceNote,
} from "@/lib/workspace";

/**
 * Feature: clara-chat-redesign, task 6.2 — WorkspaceDrawer
 * (notes / shares with expiry/rotate/revoke + export md+docx) behind
 * progressive disclosure. Requirement 6.1, 6.2.
 */

function makeNote(overrides: Partial<WorkspaceNote> = {}): WorkspaceNote {
  const now = new Date().toISOString();
  return {
    id: 1,
    title: "Metformin note",
    content_markdown: "Take with food",
    summary: "Take with food",
    tags: [],
    is_pinned: false,
    conversation_id: null,
    created_at: now,
    updated_at: now,
    ...overrides,
  };
}

function makeShare(
  overrides: Partial<WorkspaceConversationShareListItem> = {},
): WorkspaceConversationShareListItem {
  const now = new Date().toISOString();
  return {
    share_id: 1,
    conversation_id: 7,
    conversation_title: "Aspirin chat",
    message_count: 3,
    last_message_at: now,
    is_active: true,
    expires_at: null,
    created_at: now,
    updated_at: now,
    ...overrides,
  };
}

function makeWorkspace(overrides: Partial<UseWorkspace> = {}): UseWorkspace {
  return {
    notes: [],
    shares: [],
    searchResults: null,
    loadNotes: vi.fn(async () => {}),
    loadShares: vi.fn(async () => {}),
    saveNote: vi.fn(async () => {}),
    removeNote: vi.fn(async () => {}),
    share: vi.fn(async () => null),
    revokeShare: vi.fn(async () => {}),
    exportConversation: vi.fn(async () => {}),
    search: vi.fn(async () => null),
    clearSearch: vi.fn(),
    ...overrides,
  };
}

function baseProps() {
  return {
    open: true,
    onClose: vi.fn(),
    uiLanguage: "en" as const,
    onCopyShareUrl: vi.fn(),
    activeConversationId: 7 as number | null,
    activeTitle: "Aspirin chat",
    activeTurns: [],
    apiUnavailable: false,
    onNotice: vi.fn(),
  };
}

describe("WorkspaceDrawer", () => {
  it("does not render when closed", () => {
    const props = baseProps();
    const { container } = render(
      <WorkspaceDrawer {...props} open={false} workspace={makeWorkspace()} />,
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("creates a note from the notes form (Req 6.2)", async () => {
    const props = baseProps();
    const workspace = makeWorkspace();
    render(<WorkspaceDrawer {...props} workspace={workspace} />);

    fireEvent.change(screen.getByLabelText("Note title"), {
      target: { value: "New note" },
    });
    fireEvent.change(screen.getByLabelText("Note content"), {
      target: { value: "Body text" },
    });
    fireEvent.change(screen.getByLabelText("Note tags"), {
      target: { value: "a, b" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save note" }));

    await waitFor(() =>
      expect(workspace.saveNote).toHaveBeenCalledWith({
        title: "New note",
        contentMarkdown: "Body text",
        tags: ["a", "b"],
        conversationId: 7,
      }),
    );
  });

  it("deletes a note (Req 6.2)", () => {
    const props = baseProps();
    const workspace = makeWorkspace({ notes: [makeNote({ id: 42 })] });
    render(<WorkspaceDrawer {...props} workspace={workspace} />);
    fireEvent.click(screen.getByRole("button", { name: "Delete" }));
    expect(workspace.removeNote).toHaveBeenCalledWith(42);
  });

  it("creates a share with the selected expiry (Req 6.2)", async () => {
    const props = baseProps();
    const workspace = makeWorkspace();
    render(<WorkspaceDrawer {...props} workspace={workspace} />);

    fireEvent.click(screen.getByRole("tab", { name: /Shares/ }));
    fireEvent.change(screen.getByLabelText("Link expiry"), {
      target: { value: "24" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create link" }));

    await waitFor(() =>
      expect(workspace.share).toHaveBeenCalledWith(7, {
        expiresInHours: 24,
        rotate: false,
      }),
    );
  });

  it("rotates and revokes an existing share (Req 6.2)", async () => {
    const props = baseProps();
    const workspace = makeWorkspace({ shares: [makeShare({ conversation_id: 7 })] });
    render(<WorkspaceDrawer {...props} workspace={workspace} />);

    fireEvent.click(screen.getByRole("tab", { name: /Shares/ }));
    fireEvent.click(screen.getByRole("button", { name: "Rotate" }));
    await waitFor(() =>
      expect(workspace.share).toHaveBeenCalledWith(7, {
        expiresInHours: 168,
        rotate: true,
      }),
    );

    fireEvent.click(screen.getByRole("button", { name: "Revoke" }));
    await waitFor(() => expect(workspace.revokeShare).toHaveBeenCalledWith(7));
  });

  it("exports the active conversation to markdown and docx (Req 6.2)", async () => {
    const props = baseProps();
    const workspace = makeWorkspace();
    render(<WorkspaceDrawer {...props} workspace={workspace} />);

    fireEvent.click(screen.getByRole("button", { name: "Markdown (.md)" }));
    await waitFor(() =>
      expect(workspace.exportConversation).toHaveBeenCalledWith(
        7,
        "markdown",
        [],
        "Aspirin chat",
      ),
    );

    fireEvent.click(screen.getByRole("button", { name: "Word (.docx)" }));
    await waitFor(() =>
      expect(workspace.exportConversation).toHaveBeenCalledWith(
        7,
        "docx",
        [],
        "Aspirin chat",
      ),
    );
  });

  it("disables share creation when the workspace API is unavailable (Req 6.5)", () => {
    const props = baseProps();
    const workspace = makeWorkspace();
    render(
      <WorkspaceDrawer {...props} workspace={workspace} apiUnavailable />,
    );
    fireEvent.click(screen.getByRole("tab", { name: /Shares/ }));
    expect(
      screen.queryByRole("button", { name: "Create link" }),
    ).not.toBeInTheDocument();
    expect(
      screen.getByText("Sharing is unavailable offline."),
    ).toBeInTheDocument();
  });
});
