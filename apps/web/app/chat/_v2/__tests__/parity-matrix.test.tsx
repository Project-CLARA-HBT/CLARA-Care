import { describe, expect, it, vi } from "vitest";
import { renderHook } from "@testing-library/react";
import fc from "fast-check";
import { existsSync, readFileSync, statSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { useConversations } from "@/app/chat/_v2/hooks/useConversations";
import { useWorkspace } from "@/app/chat/_v2/hooks/useWorkspace";
import {
  filterCommands,
  useCommandPalette,
} from "@/app/chat/_v2/hooks/useCommandPalette";
import { localWorkspaceSearch } from "@/app/chat/_v2/lib/chat-format";
import ConversationSidebar from "@/app/chat/_v2/components/ConversationSidebar";
import WorkspaceDrawer from "@/app/chat/_v2/components/WorkspaceDrawer";
import CommandPalette from "@/app/chat/_v2/components/CommandPalette";
import FlowTimeline from "@/app/chat/_v2/components/FlowTimeline";
import TelemetryPanelLazy from "@/app/chat/_v2/components/TelemetryPanelLazy";

/**
 * Feature: clara-chat-redesign, task 8.1 — parity checklist test matrix.
 *
 * Design Property **P3 (Parity)**: *every capability in the parity checklist
 * has a v2 implementation + test (Requirement 6).* This file is that checklist,
 * encoded as data. Each row of {@link PARITY_MATRIX} maps one user-facing
 * capability from Requirement 6 to:
 *
 *   1. its concrete v2 implementation (a hook method, pure helper, or
 *      component — verified to actually be present at runtime), and
 *   2. the co-located v2 test(s) that exercise it (verified to exist on disk
 *      and to reference the relevant Requirement 6 clause).
 *
 * The matrix is the single source of truth for "are we at parity yet?": if a
 * Requirement 6 capability is added or a covering test is removed/renamed, this
 * file fails, surfacing the parity gap before the flag is flipped (task 8.3).
 *
 * **Validates: Requirements 6.1, 6.2, 6.3, 6.4, 6.5, 6.6** (design Property P3).
 *
 * The workspace/research clients are mocked so the hooks can be instantiated in
 * isolation (no network) purely to assert their capability surface exists; this
 * is a structural parity check, not a behavioral one (the behavior lives in the
 * mapped tests).
 */

vi.mock("@/lib/workspace", () => ({
  listWorkspaceConversations: vi.fn(),
  updateWorkspaceConversation: vi.fn(),
  deleteWorkspaceConversation: vi.fn(),
  updateWorkspaceConversationMeta: vi.fn(),
  listWorkspaceNotes: vi.fn(),
  createWorkspaceNote: vi.fn(),
  deleteWorkspaceNote: vi.fn(),
  listWorkspaceShares: vi.fn(),
  createWorkspaceConversationShare: vi.fn(),
  revokeWorkspaceConversationShare: vi.fn(),
  exportWorkspaceConversation: vi.fn(),
  exportWorkspaceDocxFromMarkdown: vi.fn(),
  searchWorkspace: vi.fn(),
}));

vi.mock("@/lib/research", () => ({
  listResearchConversations: vi.fn(),
}));

const TESTS_DIR = dirname(fileURLToPath(import.meta.url));

/** A React component is either a plain function or a wrapped object (memo/lazy). */
function isComponent(value: unknown): boolean {
  return (
    value != null && (typeof value === "function" || typeof value === "object")
  );
}

/** Instantiate a hook once and return its public API for surface checks. */
function conversationsApi() {
  return renderHook(() => useConversations()).result.current;
}
function workspaceApi() {
  return renderHook(() => useWorkspace()).result.current;
}
function commandPaletteApi() {
  return renderHook(() => useCommandPalette([])).result.current;
}

type MappedTest = {
  /** Test file co-located in this `__tests__` directory. */
  file: string;
  /** Requirement-6 clause the test file must reference (e.g. "6.1"). */
  references: string;
};

type ParityCapability = {
  /** Requirement 6 clause, e.g. "6.1". */
  requirement: string;
  /** Human-readable capability name from the legacy chat. */
  capability: string;
  /** Throws/expects if the v2 implementation surface is missing. */
  verifyImplementation: () => void;
  /** The v2 test(s) that exercise this capability. */
  tests: MappedTest[];
};

/**
 * The parity checklist. Every Requirement 6 acceptance-criterion capability is
 * represented exactly once.
 */
const PARITY_MATRIX: ParityCapability[] = [
  // --- Requirement 6.1: conversation CRUD + favorites + folders -------------
  {
    requirement: "6.1",
    capability: "Conversation create",
    verifyImplementation: () =>
      expect(typeof conversationsApi().create).toBe("function"),
    tests: [{ file: "useConversations.test.tsx", references: "6.1" }],
  },
  {
    requirement: "6.1",
    capability: "Conversation select",
    verifyImplementation: () =>
      expect(typeof conversationsApi().select).toBe("function"),
    tests: [{ file: "useConversations.test.tsx", references: "6.1" }],
  },
  {
    requirement: "6.1",
    capability: "Conversation rename",
    verifyImplementation: () =>
      expect(typeof conversationsApi().rename).toBe("function"),
    tests: [{ file: "useConversations.test.tsx", references: "6.1" }],
  },
  {
    requirement: "6.1",
    capability: "Conversation delete",
    verifyImplementation: () =>
      expect(typeof conversationsApi().remove).toBe("function"),
    tests: [{ file: "useConversations.test.tsx", references: "6.1" }],
  },
  {
    requirement: "6.1",
    capability: "Conversation favorites",
    verifyImplementation: () =>
      expect(typeof conversationsApi().setFavorite).toBe("function"),
    tests: [{ file: "useConversations.test.tsx", references: "6.1" }],
  },
  {
    requirement: "6.1",
    capability: "Folder organization",
    verifyImplementation: () =>
      expect(typeof conversationsApi().setFolder).toBe("function"),
    tests: [{ file: "useConversations.test.tsx", references: "6.1" }],
  },

  // --- Requirement 6.2: notes, sharing, export ------------------------------
  {
    requirement: "6.2",
    capability: "Notes",
    verifyImplementation: () => {
      const ws = workspaceApi();
      expect(typeof ws.loadNotes).toBe("function");
      expect(typeof ws.saveNote).toBe("function");
      expect(typeof ws.removeNote).toBe("function");
      expect(isComponent(WorkspaceDrawer)).toBe(true);
    },
    tests: [
      { file: "useWorkspace.test.tsx", references: "6.2" },
      { file: "WorkspaceDrawer.test.tsx", references: "6.2" },
    ],
  },
  {
    requirement: "6.2",
    capability: "Sharing (expiry / rotation / revoke)",
    verifyImplementation: () => {
      const ws = workspaceApi();
      expect(typeof ws.share).toBe("function");
      expect(typeof ws.revokeShare).toBe("function");
      expect(isComponent(WorkspaceDrawer)).toBe(true);
    },
    tests: [
      { file: "useWorkspace.test.tsx", references: "6.2" },
      { file: "WorkspaceDrawer.test.tsx", references: "6.2" },
    ],
  },
  {
    requirement: "6.2",
    capability: "Export (markdown / docx)",
    verifyImplementation: () => {
      expect(typeof workspaceApi().exportConversation).toBe("function");
      expect(isComponent(WorkspaceDrawer)).toBe(true);
    },
    tests: [
      { file: "useWorkspace.test.tsx", references: "6.2" },
      { file: "WorkspaceDrawer.test.tsx", references: "6.2" },
    ],
  },

  // --- Requirement 6.3: command palette + actions ---------------------------
  {
    requirement: "6.3",
    capability: "Command palette and its actions",
    verifyImplementation: () => {
      const palette = commandPaletteApi();
      expect(typeof palette.open).toBe("function");
      expect(typeof palette.close).toBe("function");
      expect(typeof palette.execute).toBe("function");
      expect(typeof filterCommands).toBe("function");
      expect(isComponent(CommandPalette)).toBe(true);
    },
    tests: [{ file: "useCommandPalette.test.tsx", references: "6.3" }],
  },

  // --- Requirement 6.4: search across conversations -------------------------
  {
    requirement: "6.4",
    capability: "Search across conversations",
    verifyImplementation: () => {
      expect(typeof workspaceApi().search).toBe("function");
      expect(isComponent(ConversationSidebar)).toBe(true);
    },
    tests: [
      { file: "useWorkspace.test.tsx", references: "6.4" },
      { file: "ConversationSidebar.test.tsx", references: "6.4" },
    ],
  },

  // --- Requirement 6.5: local-fallback workspace behavior -------------------
  {
    requirement: "6.5",
    capability: "Local-fallback workspace behavior",
    verifyImplementation: () => {
      // useConversations exposes the fallback signal + local mutation surface.
      const conv = conversationsApi();
      expect("apiUnavailable" in conv).toBe(true);
      expect(typeof conv.upsertLocal).toBe("function");
      // useWorkspace degrades search to an in-memory scan via this helper.
      expect(typeof localWorkspaceSearch).toBe("function");
    },
    tests: [
      { file: "useConversations.test.tsx", references: "6.5" },
      { file: "useWorkspace.test.tsx", references: "6.5" },
    ],
  },

  // --- Requirement 6.6: telemetry/flow panels, admin-only detail ------------
  {
    requirement: "6.6",
    capability: "Telemetry/flow panels with admin-only detail",
    verifyImplementation: () => {
      expect(isComponent(TelemetryPanelLazy)).toBe(true);
      expect(isComponent(FlowTimeline)).toBe(true);
    },
    tests: [{ file: "TelemetryPanelLazy.test.tsx", references: "6.6" }],
  },
];

/** The Requirement 6 clauses that must each be covered by at least one row. */
const REQUIRED_CLAUSES = ["6.1", "6.2", "6.3", "6.4", "6.5", "6.6"];

describe("Requirement 6 parity matrix (Property P3)", () => {
  it("covers every Requirement 6 clause at least once", () => {
    const covered = new Set(PARITY_MATRIX.map((row) => row.requirement));
    for (const clause of REQUIRED_CLAUSES) {
      expect(covered.has(clause)).toBe(true);
    }
  });

  it("lists no duplicate capability names", () => {
    const names = PARITY_MATRIX.map((row) => row.capability);
    expect(new Set(names).size).toBe(names.length);
  });

  describe.each(PARITY_MATRIX)(
    "$requirement — $capability",
    ({ verifyImplementation, tests }) => {
      it("has a present v2 implementation", () => {
        verifyImplementation();
      });

      it.each(tests)(
        "is covered by $file (references Requirement $references)",
        ({ file, references }) => {
          const path = join(TESTS_DIR, file);
          expect(existsSync(path), `${file} should exist`).toBe(true);
          expect(statSync(path).size, `${file} should be non-empty`).toBeGreaterThan(0);
          const contents = readFileSync(path, "utf8");
          expect(
            contents.includes(references),
            `${file} should reference Requirement ${references}`,
          ).toBe(true);
        },
      );
    },
  );

  it("Property P3: every parity capability has both an implementation and an existing, on-point test", () => {
    fc.assert(
      fc.property(
        fc.integer({ min: 0, max: PARITY_MATRIX.length - 1 }),
        (index) => {
          const row = PARITY_MATRIX[index];

          // 1. The v2 implementation surface is present (throws if not).
          row.verifyImplementation();

          // 2. The capability maps to at least one test...
          expect(row.tests.length).toBeGreaterThan(0);

          // 3. ...and every mapped test exists and references its clause.
          for (const mapped of row.tests) {
            const path = join(TESTS_DIR, mapped.file);
            expect(existsSync(path)).toBe(true);
            const contents = readFileSync(path, "utf8");
            expect(contents.includes(mapped.references)).toBe(true);
          }
        },
      ),
      { numRuns: 200 },
    );
  });
});
